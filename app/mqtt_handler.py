import paho.mqtt.client as mqtt
import json
from datetime import datetime
import base64
import os
from dotenv import load_dotenv

try:
    from .database.models import Gate, Vehicle, AccessLog, db
except ImportError:
    print("Database models not found. Ensure you are running this in the correct context.")

# MQTT Topics
TOPIC_GATE_STATUS = "gate/+/status"
TOPIC_GATE_ACCESS = "gate/+/access"
TOPIC_GATE_SYNC = "gate/+/sync"
TOPIC_SERVER_RESPONSE = "server/response/{gate_id}"

# Flag to check if ANPR is available
ANPR_AVAILABLE = False
try:
    import cv2
    import numpy as np
    from .anpr import detect_and_recognize
    ANPR_AVAILABLE = True
except ImportError:
    print("ANPR functionality not available - running in basic mode")

# Global MQTT client
mqtt_client = None

load_dotenv()

def init_mqtt(app):
    """Initialize MQTT with application context"""
    global mqtt_client
    
    # Get MQTT configuration from environment
    broker_url = os.getenv('MQTT_BROKER_URL', 'localhost')
    broker_port = int(os.getenv('MQTT_BROKER_PORT', 1883))
    username = os.getenv('MQTT_USERNAME', '')
    password = os.getenv('MQTT_PASSWORD', '')
    
    # Initialize MQTT client
    client_id = f'anpr_server_{os.getpid()}'
    mqtt_client = mqtt.Client(client_id=client_id)
    
    # Set auth if provided
    if username and password:
        mqtt_client.username_pw_set(username, password)
    
    # Store app context for handlers
    mqtt_client.app = app
    
    # Set up callbacks
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    # Connect to broker
    try:
        mqtt_client.connect(broker_url, broker_port, keepalive=60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback for when the client connects to the broker"""
    if rc == 0:
        print('Connected to MQTT broker')
        client.subscribe(TOPIC_GATE_STATUS)
        print('Subscribed to gate status topic')
        client.subscribe(TOPIC_GATE_ACCESS)
        print('Subscribed to gate access topic')
        client.subscribe(TOPIC_GATE_SYNC)
        print('Subscribed to gate sync topic')
    else:
        print(f'Bad connection. Code: {rc}')

def on_message(client, userdata, message):
    """Callback for when a message is received"""
    try:
        print(f"Received message on {message.topic}: {message.payload.decode()}")

        topic = message.topic
        payload = json.loads(message.payload.decode())
        
        print(f"Received message on topic {topic}: {payload}")
        
        # Extract gate_id from topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 3:
            return
        
        gate_id = topic_parts[1]
        action = topic_parts[2]

        # Create app context for database operations
        with client.app.app_context():
            if action == 'status':
                handle_gate_status(gate_id, payload)
            elif action == 'access':
                handle_gate_access(gate_id, payload)
            elif action == 'sync':
                handle_gate_sync(gate_id, payload)
    except Exception as e:
        print(f"Error processing message: {e}")

def handle_gate_status(gate_id, payload):
    """Handle gate status updates"""
    with mqtt_client.app.app_context():
        gate = Gate.query.filter_by(gate_id=gate_id).first()
        if gate:
            gate.status = payload.get('status', 'offline')
            gate.last_online = datetime.utcnow()
            db.session.commit()

def handle_gate_access(gate_id, payload):
    """Handle access requests from gates"""
    with mqtt_client.app.app_context():
        if ANPR_AVAILABLE:
            # ANPR processing
            image_data = base64.b64decode(payload['image'])
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            processed_image, plate_text, confidence = detect_and_recognize(image)
        else:
            # Fallback mode - use provided plate number if available
            plate_text = payload.get('plate_number', 'UNKNOWN')
            confidence = 1.0 if plate_text != 'UNKNOWN' else 0.0

        # Check authorization
        is_authorized = False
        vehicle = Vehicle.query.filter_by(plate_number=plate_text).first()
        if vehicle and vehicle.is_authorized and vehicle.is_currently_valid():
            is_authorized = True

        # Log access attempt
        log = AccessLog(
            plate_number=plate_text,
            gate_id=gate_id,
            access_granted=is_authorized,
            confidence_score=confidence
        )
        db.session.add(log)
        db.session.commit()

        # Send response back to gate
        response_topic = TOPIC_SERVER_RESPONSE.format(gate_id=gate_id)
        response = {
            'plate_number': plate_text,
            'access_granted': is_authorized,
            'confidence': confidence,
            'timestamp': datetime.utcnow().isoformat()
        }
        mqtt_client.publish(response_topic, json.dumps(response))


# TODO: complete vehicle list should NOT be sent to the gate
def handle_gate_sync(gate_id, payload):
    """Handle gate synchronization requests"""
    with mqtt_client.app.app_context():
        # Get all authorized vehicles
        vehicles = Vehicle.query.filter_by(is_authorized=True).all()
        vehicle_list = [{
            'plate_number': v.plate_number,
            'valid_until': v.valid_until.isoformat() if v.valid_until else None
        } for v in vehicles]

        # Update gate sync time
        gate = Gate.query.filter_by(gate_id=gate_id).first()
        if gate:
            gate.local_cache_updated = datetime.utcnow()
            db.session.commit()

        # Send response
        response_topic = TOPIC_SERVER_RESPONSE.format(gate_id=gate_id)
        response = {
            'vehicles': vehicle_list,
            'timestamp': datetime.utcnow().isoformat()
        }
        mqtt_client.publish(response_topic, json.dumps(response))

if __name__ == "__main__":
    init_mqtt(None)  # Initialize with dummy app context for testing