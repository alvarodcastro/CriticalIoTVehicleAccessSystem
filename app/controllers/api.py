from flask import Blueprint, request, jsonify
from flask_login import login_required
from ..database.models import Vehicle, AccessLog, Gate, db
from datetime import datetime
import cv2
import numpy as np
from ..anpr import detect_and_recognize
from ..mqtt_handler import mqtt_client as mqtt

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/check_access', methods=['POST'])
def check_access():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    gate_id = request.form.get('gate_id')
    if not gate_id:
        return jsonify({'error': 'No gate_id provided'}), 400

    # Process the image
    image_file = request.files['image']
    img_array = np.frombuffer(image_file.read(), np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    # Use ANPR to detect plate
    processed_image, plate_text, confidence = detect_and_recognize(img)
    
    # Check if vehicle is authorized
    vehicle = Vehicle.query.filter_by(plate_number=plate_text).first()
    is_authorized = False
    
    if vehicle and vehicle.is_authorized:
        if vehicle.valid_until is None or vehicle.valid_until > datetime.utcnow():
            is_authorized = True
    
    # Log the access attempt
    access_log = AccessLog(
        plate_number=plate_text,
        access_granted=is_authorized,
        confidence_score=confidence,
        gate_id=gate_id
    )
    db.session.add(access_log)
    db.session.commit()
    
    return jsonify({
        'plate_number': plate_text,
        'access_granted': is_authorized,
        'confidence': confidence
    })

@api_bp.route('/api/sync_vehicles')
@login_required
def sync_vehicles():
    """Trigger vehicle list synchronization for a specific gate"""
    gate_id = request.args.get('gate_id')
    if not gate_id:
        return jsonify({'error': 'Gate ID required'}), 400
        
    gate = Gate.query.filter_by(gate_id=gate_id).first()
    if not gate:
        return jsonify({'error': 'Gate not found'}), 404
    
    # Get authorized vehicles
    vehicles = Vehicle.query.filter_by(is_authorized=True).all()
    vehicle_list = [{
        'plate_number': v.plate_number,
        'valid_until': v.valid_until.isoformat() if v.valid_until else None
    } for v in vehicles]
    
    # Update gate sync time
    gate.local_cache_updated = datetime.utcnow()
    db.session.commit()
    
    # Publish to MQTT topic
    response = {
        'vehicles': vehicle_list,
        'timestamp': datetime.utcnow().isoformat()
    }
    topic = f"server/response/{gate_id}"
    mqtt.publish(topic, response)
    
    return jsonify({'status': 'success', 'count': len(vehicle_list)})

@api_bp.route('/api/gates')
@login_required
def list_gates():
    """Get list of all gates and their status"""
    gates = Gate.query.all()
    return jsonify([{
        'id': g.id,
        'gate_id': g.gate_id,
        'status': g.status,
        'location': g.location,
        'last_online': g.last_online.isoformat() if g.last_online else None,
        'local_cache_updated': g.local_cache_updated.isoformat() if g.local_cache_updated else None
    } for g in gates])

@api_bp.route('/api/access_logs')
@login_required
def get_access_logs():
    """Get access logs with optional filtering"""
    gate_id = request.args.get('gate_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 100, type=int)
    
    query = AccessLog.query
    
    if gate_id:
        query = query.filter_by(gate_id=gate_id)
    if start_date:
        query = query.filter(AccessLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AccessLog.timestamp <= end_date)
        
    logs = query.order_by(AccessLog.timestamp.desc()).limit(limit).all()
    
    return jsonify([{
        'id': log.id,
        'timestamp': log.timestamp.isoformat(),
        'plate_number': log.plate_number,
        'gate_id': log.gate_id,
        'access_granted': log.access_granted,
        'confidence_score': log.confidence_score,
        'image_path': log.image_path
    } for log in logs])

@api_bp.route('/api/manual_override/<gate_id>', methods=['POST'])
@login_required
def manual_override(gate_id):
    """Manually trigger gate operation"""
    gate = Gate.query.filter_by(gate_id=gate_id).first()
    if not gate:
        return jsonify({'error': 'Gate not found'}), 404
    
    # Send manual override command via MQTT
    topic = f"gate/{gate_id}/control"
    mqtt.publish(topic, {'action': 'open'})
    
    # Log the manual override
    log = AccessLog(
        plate_number='MANUAL_OVERRIDE',
        gate_id=gate_id,
        access_granted=True,
        confidence_score=1.0
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@api_bp.route('/api/gate_status', methods=['POST'])
def update_gate_status():
    """Update gate status via HTTP (fallback if MQTT fails)"""
    data = request.json
    gate_id = data.get('gate_id')
    status = data.get('status')
    
    if not gate_id or not status:
        return jsonify({'error': 'Missing required fields'}), 400
        
    gate = Gate.query.filter_by(gate_id=gate_id).first()
    if gate:
        gate.status = status
        gate.last_online = datetime.utcnow()
        db.session.commit()
        return jsonify({'status': 'success'})
    
    return jsonify({'error': 'Gate not found'}), 404