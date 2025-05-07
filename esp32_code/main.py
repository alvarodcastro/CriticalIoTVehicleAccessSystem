import machine
import network
import time
import camera
import json
import _thread
from umqtt.simple import MQTTClient
import ubinascii
import os

# Get configuration from environment
WIFI_SSID = os.getenv('WIFI_SSID')
WIFI_PASSWORD = os.getenv('WIFI_PASSWORD')
MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
GATE_ID = os.getenv('GATE_ID')

# Pin Configuration from environment
SERVO_PIN = int(os.getenv('SERVO_PIN', '13'))
IR_SENSOR_PIN = int(os.getenv('IR_SENSOR_PIN', '14'))
STATUS_LED_PIN = int(os.getenv('STATUS_LED_PIN', '2'))
OFFLINE_BUTTON_PIN = int(os.getenv('OFFLINE_BUTTON_PIN', '15'))

# MQTT Topics
TOPIC_STATUS = f"gate/{GATE_ID}/status"
TOPIC_ACCESS = f"gate/{GATE_ID}/access"
TOPIC_SYNC = f"gate/{GATE_ID}/sync"
TOPIC_SERVER_RESPONSE = f"server/response/{GATE_ID}"

# Initialize Hardware
servo = machine.PWM(machine.Pin(SERVO_PIN), freq=50)
ir_sensor = machine.Pin(IR_SENSOR_PIN, machine.Pin.IN)
status_led = machine.Pin(STATUS_LED_PIN, machine.Pin.OUT)
offline_button = machine.Pin(OFFLINE_BUTTON_PIN, machine.Pin.IN, machine.PULL_UP)

# Initialize camera
camera.init(0, format=camera.JPEG)

# Global variables
mqtt_client = None
authorized_vehicles = {}
last_sync_time = 0
is_connected = False
vehicle_present = False
last_detection_time = 0
DETECTION_COOLDOWN = 5  # seconds between detections

def init_hardware():
    """Initialize hardware components"""
    # Set servo to closed position
    servo.duty(40)
    # Set status LED off
    status_led.off()

def connect_wifi():
    """Connect to WiFi network"""
    if not WIFI_SSID or not WIFI_PASSWORD:
        print("WiFi credentials not configured")
        return False
        
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print('Connecting to WiFi...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        attempt = 0
        while not wlan.isconnected() and attempt < 10:
            status_led.value(not status_led.value())
            time.sleep(1)
            attempt += 1
    
    if wlan.isconnected():
        print('Connected to WiFi')
        status_led.on()
        return True
    else:
        print('WiFi connection failed')
        status_led.off()
        return False

def mqtt_callback(topic, msg):
    """Handle incoming MQTT messages"""
    global authorized_vehicles, last_sync_time
    
    try:
        topic = topic.decode('utf-8')
        payload = json.loads(msg.decode('utf-8'))
        
        if topic == TOPIC_SERVER_RESPONSE:
            if 'vehicles' in payload:
                # Handle sync response
                authorized_vehicles = {v['plate_number']: v for v in payload['vehicles']}
                last_sync_time = time.time()
                save_cache()
            elif 'access_granted' in payload:
                # Handle access response
                if payload['access_granted']:
                    open_gate()
    except Exception as e:
        print('Error processing message:', e)

def connect_mqtt():
    """Connect to MQTT broker"""
    global mqtt_client, is_connected
    
    try:
        client_id = ubinascii.hexlify(machine.unique_id())
        mqtt_client = MQTTClient(client_id, MQTT_BROKER,
                               port=MQTT_PORT,
                               user=MQTT_USER,
                               password=MQTT_PASSWORD,
                               keepalive=30)
        
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(TOPIC_SERVER_RESPONSE)
        
        is_connected = True
        print('Connected to MQTT broker')
        publish_status('online')
        return True
    except Exception as e:
        print('MQTT connection failed:', e)
        is_connected = False
        return False

def publish_status(status):
    """Publish gate status"""
    if mqtt_client and is_connected:
        try:
            payload = json.dumps({'status': status})
            mqtt_client.publish(TOPIC_STATUS, payload)
        except:
            pass

def request_access():
    """Capture image and request access"""
    if not is_connected:
        return False
    
    try:
        # Capture image
        buf = camera.capture()
        # Convert to base64
        b64_img = ubinascii.b2a_base64(buf)
        
        # Send access request
        payload = json.dumps({
            'image': b64_img.decode('utf-8'),
            'timestamp': time.time()
        })
        mqtt_client.publish(TOPIC_ACCESS, payload)
        return True
    except Exception as e:
        print('Error requesting access:', e)
        return False

def sync_vehicles():
    """Request vehicle list sync"""
    if not is_connected:
        return False
    
    try:
        payload = json.dumps({
            'last_sync': last_sync_time
        })
        mqtt_client.publish(TOPIC_SYNC, payload)
        return True
    except:
        return False

def save_cache():
    """Save authorized vehicles to local storage"""
    try:
        with open('vehicle_cache.json', 'w') as f:
            json.dump({
                'timestamp': last_sync_time,
                'vehicles': authorized_vehicles
            }, f)
    except:
        print('Error saving cache')

def load_cache():
    """Load authorized vehicles from local storage"""
    global authorized_vehicles, last_sync_time
    try:
        with open('vehicle_cache.json', 'r') as f:
            data = json.load(f)
            authorized_vehicles = data['vehicles']
            last_sync_time = data['timestamp']
    except:
        print('No cache found or error loading cache')

def check_offline_access(plate_number):
    """Check if vehicle is authorized in offline mode"""
    if plate_number in authorized_vehicles:
        vehicle = authorized_vehicles[plate_number]
        if not vehicle.get('valid_until') or time.time() < time.mktime(time.strptime(vehicle['valid_until'])):
            return True
    return False

def open_gate():
    """Open the gate"""
    servo.duty(115)  # Open position
    time.sleep(2)
    servo.duty(77)   # Stop
    time.sleep(5)    # Keep open
    servo.duty(40)   # Close position
    time.sleep(2)
    servo.duty(77)   # Stop

def check_vehicle_presence():
    """Check if a vehicle is present using IR sensor"""
    return not ir_sensor.value()  # Assumes sensor is LOW when vehicle is present

def mqtt_loop():
    """Background MQTT loop"""
    global is_connected
    while True:
        if is_connected:
            try:
                mqtt_client.check_msg()
                time.sleep(0.1)
            except Exception as e:
                is_connected = False
                print('MQTT Error:', e)
                try:
                    mqtt_client.disconnect()
                except:
                    pass
                time.sleep(5)
                connect_mqtt()
        time.sleep(0.1)

def main():
    """Main function"""
    global is_connected, last_detection_time, vehicle_present
    
    # Initialize hardware
    init_hardware()
    
    # Load cached vehicle list
    load_cache()
    
    # Start MQTT loop in background thread
    _thread.start_new_thread(mqtt_loop, ())
    
    # Main loop
    while True:
        # Try to maintain WiFi and MQTT connections
        if connect_wifi():
            if not is_connected:
                connect_mqtt()
            
            # Sync vehicles periodically (every 5 minutes)
            if time.time() - last_sync_time > 300:
                sync_vehicles()
        
        # Check for vehicle presence
        current_presence = check_vehicle_presence()
        current_time = time.time()
        
        # Handle vehicle detection with cooldown
        if current_presence and not vehicle_present and current_time - last_detection_time > DETECTION_COOLDOWN:
            vehicle_present = True
            last_detection_time = current_time
            
            if is_connected:
                request_access()
            else:
                # Offline mode - allow access with button press
                if not offline_button.value():
                    open_gate()
        
        # Reset vehicle presence when vehicle leaves
        if not current_presence and vehicle_present:
            vehicle_present = False
        
        time.sleep(0.1)

if __name__ == '__main__':
    main()