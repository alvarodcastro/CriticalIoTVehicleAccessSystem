import time

import paho.mqtt.client as mqtt

BROKER = "localhost"  # Public test broker
PORT = 1883

TOPIC_GATE_STATUS = "gate/1/status"
TOPIC_GATE_ACCESS = "gate/1/access"
TOPIC_GATE_SYNC = "gate/1/sync"
TOPIC_SERVER_RESPONSE = "server/response/{gate_id}"

USERNAME = "user"  # Replace with actual username
PASSWORD = "user123"  # Replace with actual password

MESSAGE = "Hello from MQTT test client!"

def main():
    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)  # Set authentication credentials

    client.connect(BROKER, PORT, 60)
    client.loop_start()
    for i in range(5):
        msg = f"{MESSAGE} #{i+1}"
        client.publish(TOPIC_GATE_STATUS, msg)
        print(f"Sent: {msg}")
        time.sleep(1)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()