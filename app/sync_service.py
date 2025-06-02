import os
import time
import json
from datetime import datetime
import paho.mqtt.client as mqtt
from app.database.sqlite_db import SQLiteDB
import logging
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv('MQTT_BROKER_URL')
MQTT_PORT = int(os.getenv('MQTT_BROKER_PORT'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
GATE_ID = os.getenv('GATE_ID', 'EC:64:C9:AC:C9:A4')
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 300)) 
DB_PATH = os.getenv('LOCAL_DATABASE_URL')

class SyncService:
    def __init__(self):
        """Initialize sync service"""
        self.db = SQLiteDB(DB_PATH)
        self.mqtt_client = None
        self.setup_mqtt()

    def setup_mqtt(self):
        """Set up MQTT client"""
        try:
            client_id = f'gate_sync_{GATE_ID}_{int(time.time())}'
            self.mqtt_client = mqtt.Client(client_id=client_id)

            # Set MQTT callbacks
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_disconnect = self.on_disconnect

            # Set credentials if provided
            if MQTT_USERNAME and MQTT_PASSWORD:
                self.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

            # Connect to broker
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            
            logger.info(f"MQTT client initialized with ID: {client_id}")
        except Exception as e:
            logger.error(f"Error setting up MQTT: {e}")
            raise

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to sync response topics
            topics = [
                f"gate/{GATE_ID}/sync/response",
                f"gate/{GATE_ID}/sync/logs/ack"
            ]
            for topic in topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        logger.warning(f"Disconnected from MQTT broker with code: {rc}")
        if rc != 0:
            logger.info("Attempting to reconnect...")
            time.sleep(5)
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.debug(f"Received message on {msg.topic}: {payload}")

            if msg.topic.endswith('/sync/response'):
                self.handle_sync_response(payload)
            elif msg.topic.endswith('/sync/logs/ack'):
                self.handle_logs_ack(payload)

        except json.JSONDecodeError:
            logger.error(f"Failed to decode message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def handle_sync_response(self, payload):
        """Handle vehicle list sync response"""
        try:
            vehicles = payload.get('vehicles', [])
            sync_version = payload.get('sync_version')
            
            if vehicles and sync_version:
                self.db.update_vehicles(vehicles)
                self.db.update_sync_version(sync_version)
                logger.info(f"Synchronized {len(vehicles)} vehicles to version {sync_version}")
            
        except Exception as e:
            logger.error(f"Error handling sync response: {e}")

    def handle_logs_ack(self, payload):
        """Handle acknowledgment of synced logs"""
        try:
            if payload.get('status') == 'success':
                log_ids = payload.get('log_ids', [])
                if log_ids:
                    self.db.mark_logs_synced(log_ids)
                    logger.info(f"Marked {len(log_ids)} logs as synced")
            else:
                log_ids = payload.get('log_ids', [])
                if log_ids:
                    self.db.increment_retry_count(log_ids)
                    logger.warning(f"Sync failed for {len(log_ids)} logs")
                
        except Exception as e:
            logger.error(f"Error handling logs acknowledgment: {e}")

    def request_sync(self):
        """Request vehicle list synchronization"""
        try:
            sync_info = self.db.get_sync_info()
            request = {
                'gate_id': GATE_ID,
                'sync_version': sync_info['sync_version']
            }
            topic = f"gate/{GATE_ID}/sync/request"
            self.mqtt_client.publish(topic, json.dumps(request))
            logger.info(f"Requested sync with version {sync_info['sync_version']}")
            
        except Exception as e:
            logger.error(f"Error requesting sync: {e}")

    def sync_pending_logs(self):
        """Sync pending access logs to server"""
        try:
            pending_logs = self.db.get_pending_logs()
            if not pending_logs:
                return

            logs_payload = {
                'gate_id': GATE_ID,
                'logs': [{
                    'id': log['id'],
                    'plate_number': log['plate_number'],
                    'gate_id': log['gate_id'],
                    'access_granted': log['access_granted'],
                    'confidence_score': log['confidence_score'],
                    'timestamp': log['timestamp']
                } for log in pending_logs]
            }

            topic = f"gate/{GATE_ID}/sync/logs"
            self.mqtt_client.publish(topic, json.dumps(logs_payload))
            logger.info(f"Sent {len(pending_logs)} logs for synchronization")

        except Exception as e:
            logger.error(f"Error syncing logs: {e}")

    def run(self):
        """Main service loop"""
        logger.info("Starting sync service...")
        
        while True:
            try:
                # Perform periodic sync
                self.request_sync()
                self.sync_pending_logs()
                
                # Clean old synced logs
                self.db.clean_old_logs()
                
                # Wait for next sync interval
                time.sleep(SYNC_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                time.sleep(10)  # Wait before retrying

if __name__ == '__main__':
    service = SyncService()
    service.run()
