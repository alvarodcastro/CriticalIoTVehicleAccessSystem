from flask_login import UserMixin
from datetime import datetime
from .. import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), unique=True, nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    is_authorized = db.Column(db.Boolean, default=True)
    valid_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime)
    last_sync = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_currently_valid(self):
        now = datetime.utcnow()
        if not self.is_authorized:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return now >= self.valid_from

class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    access_granted = db.Column(db.Boolean, nullable=False)
    confidence_score = db.Column(db.Float)
    gate_id = db.Column(db.String(20), nullable=False)
    image_path = db.Column(db.String(200))
    
    def __init__(self, plate_number, gate_id, access_granted, confidence_score=None):
        self.plate_number = plate_number
        self.gate_id = gate_id
        self.access_granted = access_granted
        self.confidence_score = confidence_score

class Gate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gate_id = db.Column(db.String(20), unique=True, nullable=False)
    location = db.Column(db.String(100))
    last_online = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='offline')  # online, offline, maintenance
    local_cache_updated = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))