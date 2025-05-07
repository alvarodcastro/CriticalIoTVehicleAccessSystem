import json
import os

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except:
        print("Error loading config.json")
        return None

# Load configuration
config = load_config()
if config:
    # Make configuration available globally
    os.environ['WIFI_SSID'] = config['wifi']['ssid']
    os.environ['WIFI_PASSWORD'] = config['wifi']['password']
    os.environ['MQTT_BROKER'] = config['mqtt']['broker']
    os.environ['MQTT_PORT'] = str(config['mqtt']['port'])
    os.environ['MQTT_USER'] = config['mqtt']['user']
    os.environ['MQTT_PASSWORD'] = config['mqtt']['password']
    os.environ['GATE_ID'] = config['gate']['id']
    
    # Set pin configurations
    os.environ['SERVO_PIN'] = str(config['pins']['servo'])
    os.environ['IR_SENSOR_PIN'] = str(config['pins']['ir_sensor'])
    os.environ['STATUS_LED_PIN'] = str(config['pins']['status_led'])
    os.environ['OFFLINE_BUTTON_PIN'] = str(config['pins']['offline_button'])
    
    print("Configuration loaded successfully")