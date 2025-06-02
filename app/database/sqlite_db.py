import sqlite3
from datetime import datetime, timedelta
import uuid
import os
import pytz

# Configurar la zona horaria de España
TIMEZONE = pytz.timezone('Europe/Madrid')

class SQLiteDB:
    def __init__(self, db_path):
        """Initialize SQLite database"""
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _init_db(self):
        """Initialize database with schema"""
        self._ensure_db_dir()  # Asegurarnos de que el directorio existe
        with sqlite3.connect(self.db_path) as conn:
            # Create vehicles table
            conn.execute('''
            CREATE TABLE IF NOT EXISTS authorized_vehicles (
                plate_number TEXT PRIMARY KEY,
                owner_name TEXT,
                valid_from DATETIME,
                valid_until DATETIME,
                is_authorized BOOLEAN DEFAULT TRUE,
                last_sync DATETIME
            )''')

            # Create access logs table for storing pending logs
            conn.execute('''
            CREATE TABLE IF NOT EXISTS pending_logs (
                id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                plate_number TEXT,
                gate_id TEXT,
                access_granted BOOLEAN,
                confidence_score REAL,
                accessing BOOLEAN DEFAULT FALSE,
                sync_status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0
            )''')

            # Create sync control table
            conn.execute('''
            CREATE TABLE IF NOT EXISTS sync_control (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_sync DATETIME,
                sync_version INTEGER DEFAULT 0
            )''')

            # Initialize sync control if not exists
            conn.execute('''
            INSERT OR IGNORE INTO sync_control (id, last_sync, sync_version)
            VALUES (1, CURRENT_TIMESTAMP, 0)
            ''')

            # Create indices for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_plate ON authorized_vehicles(plate_number)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sync_status ON pending_logs(sync_status)')

    def get_vehicle_by_plate_number(self, plate_number):
        """Get vehicle details by plate number"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM authorized_vehicles 
                WHERE plate_number = ?
            ''', (plate_number,))
            vehicle = cursor.fetchone()
            return vehicle if vehicle else None

    def get_vehicle_last_sync_time(self):
        """Get the last sync time of the vehicle database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # para acceder por nombre de columna
            cursor = conn.execute('SELECT last_sync FROM authorized_vehicles ORDER BY last_sync DESC LIMIT 1')
            result = cursor.fetchone()
            return result['last_sync'] if result else None

    def is_vehicle_in_parking(self, plate_number):
        """Check if a vehicle is currently in parking"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM pending_logs 
                WHERE plate_number = ?
                ORDER BY timestamp DESC
            ''', (plate_number,))
            vehicle = cursor.fetchone()
            print("DEBUG: vehicle instance:", vehicle['timestamp'], vehicle['accessing'])  # Debugging line
            accessing = vehicle['accessing'] if vehicle and vehicle['accessing'] else False
            return accessing
        
    def is_vehicle_authorized(self, plate_number):
        """Check if a vehicle is authorized"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT is_authorized, valid_from, valid_until 
                FROM authorized_vehicles 
                WHERE plate_number = ?
            ''', (plate_number,))
            vehicle = cursor.fetchone()

            if not vehicle:
                return False
            if not vehicle['is_authorized']:
                return False

            # Obtener la hora actual en la zona horaria de España
            now = datetime.now(TIMEZONE)

            # Convertir las fechas de la base de datos a la zona horaria de España
            valid_from = datetime.fromisoformat(vehicle['valid_from']).astimezone(TIMEZONE) if vehicle['valid_from'] else None

            if valid_from and now < valid_from:
                return False

            if vehicle['valid_until']:
                valid_until = datetime.fromisoformat(vehicle['valid_until']).astimezone(TIMEZONE)
                if now > valid_until:
                    return False

            return True

    def create_access_log(self, plate_number, gate_id, access_granted, accessing, confidence_score=None):
        """Create a new access log entry for later synchronization"""
        with sqlite3.connect(self.db_path) as conn:
            log_id = str(uuid.uuid4())
            now = datetime.now(TIMEZONE)
            conn.execute('''
                INSERT INTO pending_logs (id, plate_number, gate_id, access_granted, confidence_score, timestamp, accessing)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (log_id, plate_number, gate_id, access_granted, confidence_score, now.isoformat(), accessing))
            return log_id

    def get_pending_logs(self, limit=50, max_retries=3):
        """Get logs that need to be synchronized"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM pending_logs
                WHERE sync_status = 'pending'
                AND retry_count < ?
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (max_retries, limit))
            return cursor.fetchall()    
            
    def update_sync_version(self, new_version):
        """Update the local sync version"""
        try:
            sync_version = int(new_version)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE sync_control
                    SET sync_version = ?, last_sync = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (sync_version,))
        except (ValueError, TypeError) as e:
            print(f"Error converting sync_version to integer: {new_version}, error: {e}")
            raise

    def get_sync_info(self):
        """Get current sync version and timestamp"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM sync_control WHERE id = 1')
            return cursor.fetchone()    
            
    def update_vehicles(self, vehicles):
        """Update local vehicle database from sync data"""
        with sqlite3.connect(self.db_path) as conn:
            for vehicle in vehicles:
                conn.execute('''
                    INSERT OR REPLACE INTO authorized_vehicles 
                    (plate_number, owner_name, valid_from, valid_until, is_authorized, last_sync)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    vehicle['plate_number'],
                    vehicle.get('owner_name', ''),
                    vehicle['valid_from'],
                    vehicle['valid_until'],
                    vehicle['is_authorized'],
                    datetime.now(TIMEZONE).isoformat()
                ))

    def mark_logs_synced(self, log_ids):
        """Mark logs as successfully synchronized"""
        with sqlite3.connect(self.db_path) as conn:
            log_ids_str = ','.join(['?'] * len(log_ids))
            conn.execute(f'''
                UPDATE pending_logs 
                SET sync_status = 'synced'
                WHERE id IN ({log_ids_str})
            ''', log_ids)

    def increment_retry_count(self, log_ids):
        """Increment retry count for failed sync attempts"""
        with sqlite3.connect(self.db_path) as conn:
            log_ids_str = ','.join(['?'] * len(log_ids))
            conn.execute(f'''
                UPDATE pending_logs 
                SET retry_count = retry_count + 1
                WHERE id IN ({log_ids_str})
            ''', log_ids)

    def clean_old_logs(self, days=7):
        """Remove old synced logs (SAFE)"""
        with sqlite3.connect(self.db_path) as conn:
            # Calcular la fecha límite en Python y formatearla
            limit_date = datetime.now() - timedelta(days=days)
            limit_date_str = limit_date.strftime('%Y-%m-%d %H:%M:%S')

            conn.execute('''
                DELETE FROM pending_logs 
                WHERE sync_status = 'synced'
                AND timestamp < ?
            ''', (limit_date_str,))