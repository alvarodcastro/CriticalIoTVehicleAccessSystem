import paho.mqtt.client as mqtt
import json
from datetime import datetime
import base64
import os
from dotenv import load_dotenv
import requests

try:
    from .database.models import Gate, Vehicle, AccessLog, db
except ImportError:
    print("Database models not found. Ensure you are running this in the correct context.")

# MQTT Topics
TOPIC_GATE_STATUS = "gate/+/status"
TOPIC_GATE_ACCESS = "gate/+/access"
TOPIC_GATE_SYNC = "gate/+/sync"
TOPIC_SERVER_RESPONSE = "server/response/{gate_id}"

# YOLO API Configuration
YOLO_API_URL = os.getenv('YOLO_API_URL')

# Global MQTT client
mqtt_client = None

load_dotenv()

def process_image_with_yolo(image_data, url=None):
    """
    Process an image using the YOLO API service
    
    Args:
        image_data (bytes): Raw image data in bytes
        
    Returns:
        tuple: (plate_text, confidence) from the ANPR service
    """
    try:
        if url is None:
            # Prepare the image file for the request
            files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            
            # Make request to YOLO API
            response = requests.post(f"{YOLO_API_URL}/api/anpr", files=files)
        else:
            # Make request to YOLO API
            print(f"Processing image from URL: {url}")
            response = requests.get(f"{YOLO_API_URL}/api/anpr/url", params={'image': url})
        
        if response.status_code == 200:
            result = response.json()
            print(f"YOLO API Response: {result}")
            return result['plate_text'], result['confidence']
        else:
            print(f"Error from YOLO API: {response.text}")
            return 'UNKNOWN', 0.0
               
    except Exception as e:
        print(f"Error processing image with YOLO API: {e}")
        return 'UNKNOWN', 0.0

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
        topic = message.topic
        payload = json.loads(message.payload.decode("utf-8"))

        print(f"Received message on {topic}")

        
        # Extract gate_id from topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 3:
            return
        
        gate_id = topic_parts[1]
        action = topic_parts[2]

        # Create app context for database operations
        with client.app.app_context():
            if action == 'status':
                print(f"Handling gate status for gate {gate_id}")
                handle_gate_status(gate_id, payload)
            elif action == 'access':
                print(f"Handling gate access for gate {gate_id}")
                handle_gate_access(gate_id, payload)
            elif action == 'sync':
                print(f"Handling gate sync for gate {gate_id}")
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

def handle_gate_access(gate_id, payload, url=None):
    """Handle access requests from gates"""
    with mqtt_client.app.app_context():
        # Process image with YOLO API
        image_data = None
        if url is None:
            # Decode base64 image data
            image_data = base64.b64decode(payload['image'])
        
        plate_text, confidence = process_image_with_yolo(image_data, url=url)
        print(f"Detected plate: {plate_text} with confidence: {confidence}")


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
        print(f"Sending response to gate {gate_id}: {is_authorized}")
        response_topic = TOPIC_SERVER_RESPONSE.format(gate_id=gate_id)
        response = {
            'plate_number': plate_text,
            'access_granted': is_authorized,
            'confidence': confidence,
            'timestamp': datetime.utcnow().isoformat()
        }
        mqtt_client.publish(response_topic, json.dumps(response))

# TODO: complete vehicle list should NOT be sent to the gate
# TODO: sync should be done periodically accessing to cloud service
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
