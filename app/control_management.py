import re
import threading
import json
from typing import Dict, Tuple, List, Optional


import paho.mqtt.client as mqtt

BROKER = "localhost"  # Public test broker
PORT = 1883

USERNAME = "user"  # Replace with actual username
PASSWORD = "user123"  # Replace with actual password

# Default identifier ranges for sensor categories (inclusive)
# Adjust as your network evolves.
SENSOR_ID_RANGES: Dict[str, Tuple[int, int]] = {
	"airQuality": (0x500, 0x599),
	"gas": (0x600, 0x699),
	"isSlotOccupied": (0x700, 0x799),
	"barrierCommand": (0x200, 0x299),
	"isBarrierOpen": (0x300, 0x399),
}


class SerialCANReceiver:
	"""Simple CAN-over-Serial line reader.

	Reads ASCII lines from a serial port. Attempts to parse lines containing
	CAN fields: identifier (ID), DLC (data length), and data bytes.

	Supported line formats (flexible, case-insensitive):
	- "ID=0x036 DLC=2 DATA=00 FF"
	- "ID: 54 DLC: 8 DATA: AA BB CC DD EE FF 00 11"
	- "ID 0x321 DLC 2 DATA 01, 02, 03"

	If a line can't be parsed, it will be printed verbatim.
	"""

	def __init__(
		self,
		port: str,
		baudrate: int = 115200,
		timeout: float = 1.0,
		sensor_id_ranges: Optional[Dict[str, Tuple[int, int]]] = None,
		mqtt_client: Optional[object] = None,
	) -> None:

		self.port = port
		self.baudrate = baudrate
		self.timeout = timeout
		self.sensor_id_ranges = sensor_id_ranges or SENSOR_ID_RANGES
		self.mqtt_client = mqtt_client
		self._stop_evt = threading.Event()
		self._thread: Optional[threading.Thread] = None
		# Use a generic type to avoid import-time typing issues if pyserial isn't installed yet
		self._ser: Optional[object] = None
		# Track state for boolean sensors to avoid redundant publishing
		self._sensor_states: Dict[int, bool] = {}
		
		# Configure MQTT callback if client is provided
		if self.mqtt_client:
			self.mqtt_client.on_message = self._on_mqtt_message

		# Precompile regexes for performance and flexibility
		# Matches ID=0x123 or ID: 291 or ID 0x123
		self._id_re = re.compile(r"\bID\s*[:=]?\s*(0x[0-9A-Fa-f]+|\d+)\b", re.IGNORECASE)
		self._dlc_re = re.compile(r"\bDLC\s*[:=]?\s*(\d+)\b", re.IGNORECASE)
		# DATA section: bytes separated by spaces or commas, hex preferred but decimal allowed
		self._data_re = re.compile(r"\bDATA\s*[:=]?\s*([0-9A-Fa-f\s,]+)\b", re.IGNORECASE)

	def start(self) -> None:
		if self._thread and self._thread.is_alive():
			return
		self._stop_evt.clear()
		# Import pyserial lazily to avoid workspace analysis errors when not installed yet
		try:
			import serial as _serial  # type: ignore
		except ImportError as exc:  # pragma: no cover
			raise RuntimeError(
				"pyserial not installed. Please add 'pyserial' to requirements and install."
			) from exc
		self._ser = _serial.Serial(self.port, self.baudrate, timeout=self.timeout)
		self._thread = threading.Thread(target=self._run, name="SerialCANReceiver", daemon=True)
		self._thread.start()
		print(f"[Serial] Listening on {self.port} @ {self.baudrate} baud")
		
		# Subscribe to actuator commands if MQTT client is configured
		if self.mqtt_client:
			self.mqtt_client.subscribe("gate/+/actuators")
			print("[MQTT] Subscribed to gate/+/actuators")

	def stop(self) -> None:
		self._stop_evt.set()
		if self._thread:
			self._thread.join(timeout=2.0)
		if self._ser:
			try:
				self._ser.close()
			except Exception:
				pass

	def _run(self) -> None:
		assert self._ser is not None
		while not self._stop_evt.is_set():
			try:
				raw = self._ser.readline()
				if not raw:
					continue
				line = raw.decode(errors="replace").strip()
			except Exception as exc:
				print(f"[Serial] Read error: {exc}")
				break

			parsed = self._parse_can_line(line)
			if parsed is None:
				# Not a CAN-formatted line, print as-is for visibility
				if line[:3] == "LED":
					# Suppress noisy LED status lines
					continue
				else:
					print(f"[Serial] {line}")
					continue

			can_id, dlc, data_bytes = parsed
			category = self._categorize(can_id)
			id_str = f"0x{can_id:03X}"
			data_hex = " ".join(f"{b:02X}" for b in data_bytes)
			print(
				f"[CAN] ID={id_str} category={category} DLC={dlc} DATA=[{data_hex}]"
			)

			# Publish to MQTT if client is configured
			if self.mqtt_client and category != "unknown":
				# print(f"[MQTT] Publishing CAN ID={id_str} to MQTT")
				self._publish_to_mqtt(can_id, category, data_bytes)

	def _parse_can_line(self, line: str) -> Optional[Tuple[int, int, List[int]]]:
		"""Attempt to parse a CAN line into (id, dlc, data_bytes)."""
		id_match = self._id_re.search(line)
		dlc_match = self._dlc_re.search(line)
		data_match = self._data_re.search(line)

		if not (id_match and dlc_match and data_match):
			return None

		# Parse ID (hex or decimal)
		id_str = id_match.group(1)
		try:
			can_id = int(id_str, 16) if id_str.lower().startswith("0x") else int(id_str)
		except ValueError:
			return None

		# Parse DLC
		try:
			dlc = int(dlc_match.group(1))
		except ValueError:
			return None

		# Parse DATA bytes (space/comma separated, hex preferred)
		data_field = data_match.group(1)
		tokens = [t for t in re.split(r"[\s,]+", data_field.strip()) if t]
		data_bytes: List[int] = []
		for t in tokens:
			tt = t.lower()
			try:
				val = int(tt, 16) if re.fullmatch(r"0x?[0-9a-f]+", tt) else int(tt)
			except ValueError:
				# Skip non-byte tokens gracefully
				continue
			if 0 <= val <= 255:
				data_bytes.append(val)

		# Respect DLC: truncate or pad with zeros
		if dlc < len(data_bytes):
			data_bytes = data_bytes[:dlc]
		elif dlc > len(data_bytes):
			data_bytes.extend([0] * (dlc - len(data_bytes)))

		return can_id, dlc, data_bytes

	def _categorize(self, can_id: int) -> str:
		for name, (lo, hi) in self.sensor_id_ranges.items():
			if lo <= can_id <= hi:
				return name
		return "unknown"

	def _send_can_message(self, can_id: int, data_bytes: List[int]) -> None:
		"""Send a CAN message over serial."""
		if not self._ser:
			print("[Serial] Cannot send: serial port not open")
			return
		
		try:
			# Required format: TX <ID> <DATA>\r\n
			# ID is sent in decimal as per example `TX 201 1E`.
			# DATA is hex with uppercase, concatenated if multiple bytes.
			data_hex_concat = "".join(f"{b:02X}" for b in data_bytes) if data_bytes else ""
			message = f"TX {can_id} {data_hex_concat}\r\n"
			self._ser.write(message.encode('ascii'))
			print(f"[Serial] Sent CAN message: {message.strip()}")
		except Exception as exc:
			print(f"[Serial] Send error: {exc}")

	def _on_mqtt_message(self, client, userdata, msg) -> None:
		"""Handle incoming MQTT messages for actuator commands."""
		try:
			topic = msg.topic
			payload = json.loads(msg.payload.decode())
			
			# Extract gate_id from topic gate/{gate_id}/actuators
			parts = topic.split("/")
			if len(parts) != 3 or parts[0] != "gate" or parts[2] != "actuators":
				print(f"[MQTT] Invalid topic format: {topic}")
				return
			
			gate_id = int(parts[1])
			
			# Check if payload contains barrierCommand
			if "barrierCommand" not in payload:
				print(f"[MQTT] No barrierCommand in payload: {payload}")
				return
			
			command = payload["barrierCommand"]
			if not isinstance(command, bool):
				print(f"[MQTT] barrierCommand must be boolean, got: {type(command)}")
				return
			
			# Calculate CAN ID from gate_id and barrierCommand range
			lo, hi = self.sensor_id_ranges.get("barrierCommand", (0, 0))
			can_id = lo + gate_id
			
			# Validate CAN ID is within range
			if can_id < lo or can_id > hi:
				print(f"[MQTT] Gate ID {gate_id} results in CAN ID 0x{can_id:03X} outside barrierCommand range")
				return
			
			# Convert boolean to data byte: True -> 0x01, False -> 0x00
			data_byte = 0x01 if command else 0x00
			
			print(f"[MQTT] Received barrier command: gate_id={gate_id}, command={command}, CAN_ID=0x{can_id:03X}")
			
			# Send CAN message over serial
			self._send_can_message(can_id, [data_byte])
			
		except json.JSONDecodeError as exc:
			print(f"[MQTT] JSON decode error: {exc}")
		except ValueError as exc:
			print(f"[MQTT] Value error: {exc}")
		except Exception as exc:
			print(f"[MQTT] Message handling error: {exc}")

	def _publish_to_mqtt(self, can_id: int, category: str, data_bytes: List[int]) -> None:
		"""Publish CAN message to MQTT topic gate/{system_id}/sensors."""
		try:
			# Calculate system_id by subtracting the lower bound of the category range
			lo, hi = self.sensor_id_ranges.get(category, (0, 0))
			system_id = can_id - lo

			# Create JSON payload with sensor category as key and data as value
			data_hex = " ".join(f"{b:02X}" for b in data_bytes)
			
			# For boolean sensors, convert to true/false
			if category == "isSlotOccupied" or category == "isBarrierOpen":
				data_value = (data_hex == "01")
				# Check if state has changed
				if can_id in self._sensor_states and self._sensor_states[can_id] == data_value:
					# State unchanged, skip publishing
					return
				# Update stored state
				self._sensor_states[can_id] = data_value
				payload = {
					category: {can_id: data_value}
			}
			# For airQuality and gas sensors, convert hex bytes to integer
			elif category == "airQuality" or category == "gas":
				# Combine bytes into a single integer (big-endian)
				data_value = int("".join(f"{b:02X}" for b in data_bytes), 16) if data_bytes else 0
				if category == "gas":
					# Example conversion for gas sensor
					data_value = float(data_value)/100
				payload = {
					category: data_value
				}
			else:
				data_value = data_hex
				payload = {
				category: data_value
				}	
			
			

			# Publish to topic
			topic = f"gate/{system_id}/sensors"
			payload_json = json.dumps(payload)
			self.mqtt_client.publish(topic, payload_json)
			print(f"[MQTT] Published to {topic}: {payload_json}")
		except Exception as exc:
			print(f"[MQTT] Publish error: {exc}")


def run_serial_can_logger(
	port: str,
	baudrate: int = 115200,
	sensor_id_ranges: Optional[Dict[str, Tuple[int, int]]] = None,
	mqtt_client: Optional[object] = None,
) -> SerialCANReceiver:
	"""Convenience runner: starts a background receiver that prints to terminal.

	Returns the receiver instance so callers can stop it later.
	"""
	receiver = SerialCANReceiver(
		port=port, baudrate=baudrate, sensor_id_ranges=sensor_id_ranges, mqtt_client=mqtt_client
	)
	receiver.start()
	return receiver


if __name__ == "__main__":
	# Quick manual run: update COM port as needed
	# Example formats accepted:
	#   ID=0x036 DLC=2 DATA=00 FF
	#   ID: 54 DLC: 8 DATA: AA BB CC DD EE FF 00 11
	import os
	com_port = os.getenv("SERIAL_PORT", "COM8")
	baud = int(os.getenv("SERIAL_BAUD", "115200"))

	client = mqtt.Client()
	client.username_pw_set(USERNAME, PASSWORD)

	try:
		client.connect(BROKER, PORT, 60)
		client.loop_start()
		print("[MQTT] Connected to broker")
	except Exception as e:
		print(f"[MQTT] Connection error: {e}")
		client = None

	print("Starting Serial CAN logger. Press Ctrl+C to stop.")
	rcv = None
	try:
		rcv = run_serial_can_logger(com_port, baud, mqtt_client=client)
		# Keep main thread alive while background thread runs
		threading.Event().wait()
	except KeyboardInterrupt:
		print("\n[Serial] Received Ctrl+C, stopping...")
	finally:
		if rcv is not None:
			try:
				rcv.stop()
				print("[Serial] Connection closed successfully.")
			except Exception as e:
				print(f"[Serial] Error closing connection: {e}")
