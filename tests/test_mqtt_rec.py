import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
USERNAME = "user"  # Replace with actual username
PASSWORD = "user123"  # Replace with actual password

TOPIC_GATE_STATUS = "gate/1/status"

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected with result code " + str(rc))
    client.subscribe(TOPIC_GATE_STATUS)
    print(f"Subscribed to {TOPIC_GATE_STATUS}")

def on_message(client, userdata, msg):
    print(f"Received message on {msg.topic}: {msg.payload.decode()}")

def main():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.username_pw_set(USERNAME, PASSWORD)  # Set authentication credentials
    client.connect(BROKER, PORT)
    client.loop_start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()