import os
import json
import secrets
import string
from pathlib import Path

def generate_secret_key(length=32):
    """Generate a secure secret key"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_mqtt_password(length=16):
    """Generate a secure MQTT password"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_config():
    """Create configuration files for both server and ESP32"""
    # Get user input
    print("Access Control System Configuration Generator")
    print("-" * 40)
    
    # Server configuration
    print("\nServer Configuration:")
    mqtt_broker_url = input("MQTT Broker IP (default: localhost): ") or "localhost"
    mqtt_broker_port = input("MQTT Broker Port (default: 1883): ") or "1883"
    mqtt_user = input("MQTT Username (default: mqtt_user): ") or "mqtt_user"
    mqtt_password = input("MQTT Password (leave empty to generate): ") or generate_mqtt_password()
    
    # Generate server .env file
    env_content = f"""SECRET_KEY={generate_secret_key()}
DATABASE_URL=sqlite:///access_control.db
DEBUG=False
UPLOAD_FOLDER=app/static/debug_images

# MQTT Configuration
MQTT_BROKER_URL={mqtt_broker_url}
MQTT_BROKER_PORT={mqtt_broker_port}
MQTT_USERNAME={mqtt_user}
MQTT_PASSWORD={mqtt_password}
MQTT_KEEPALIVE=60
MQTT_TLS_ENABLED=False"""

    with open('.env', 'w') as f:
        f.write(env_content)
    print("\nServer .env file created successfully!")

    # ESP32 configuration
    print("\nESP32 Configuration:")
    wifi_ssid = input("WiFi SSID: ")
    wifi_password = input("WiFi Password: ")
    gate_id = input("Gate ID (e.g., gate_001): ")
    
    esp32_config = {
        'wifi': {
            'ssid': wifi_ssid,
            'password': wifi_password
        },
        'mqtt': {
            'broker': mqtt_broker_url,
            'port': int(mqtt_broker_port),
            'user': mqtt_user,
            'password': mqtt_password
        },
        'gate': {
            'id': gate_id
        },
        'pins': {
            'servo': 13,
            'ir_sensor': 14,
            'status_led': 2,
            'offline_button': 15
        }
    }

    # Create ESP32 configuration
    esp32_dir = Path('esp32_code')
    esp32_dir.mkdir(exist_ok=True)
    
    with open(esp32_dir / 'config.json', 'w') as f:
        json.dump(esp32_config, f, indent=4)
    
    # Generate Mosquitto configuration
    mosquitto_conf = f"""# Mosquitto MQTT Broker configuration
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type all"""

    with open('mosquitto.conf', 'w') as f:
        f.write(mosquitto_conf)

    print("\nConfiguration files generated successfully!")
    print("\nNext steps:")
    print("1. Copy mosquitto.conf to /etc/mosquitto/conf.d/ on the MQTT broker")
    print(f"2. Create MQTT user: mosquitto_passwd -c /etc/mosquitto/passwd {mqtt_user}")
    print("3. Update ESP32 with the generated configuration")
    print("4. Restart the MQTT broker and the application")

if __name__ == "__main__":
    create_config()