from flask import Blueprint, request, jsonify
from flask_login import login_required
from ..database.models import Vehicle, AccessLog, Gate
from datetime import datetime
import cv2
import numpy as np
from ..anpr import detect_and_recognize
from ..mqtt_handler import mqtt_client as mqtt
from .. import db
from google.cloud import bigquery

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
    vehicle_data = db.get_vehicle_by_plate(plate_text)
    is_authorized = False
    
    if vehicle_data:
        vehicle = Vehicle(vehicle_data)
        if vehicle.is_authorized:
            if vehicle.valid_until is None or vehicle.valid_until > datetime.utcnow():
                is_authorized = True
    
    # Log the access attempt
    success = db.create_access_log(
        plate_number=plate_text,
        gate_id=gate_id,
        access_granted=is_authorized,
        confidence_score=confidence
    )
    
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
        
    gate = db.get_gate(gate_id)
    if not gate:
        return jsonify({'error': 'Gate not found'}), 404
    
    # Get authorized vehicles
    vehicles_data = db.get_authorized_vehicles()
    vehicle_list = [{
        'plate_number': v.plate_number,
        'valid_until': v.valid_until.isoformat() if v.valid_until else None
    } for v in [Vehicle(v) for v in vehicles_data]]
    
    # Update gate sync time
    db.update_gate_status(gate_id, gate.status, datetime.utcnow())
    
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
    query = f"SELECT * FROM `{db.get_table_ref('Gate')}`"
    gates_data = list(db.client.query(query).result())
    gates = [Gate(g) for g in gates_data]
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
    
    # Construct query with filters
    query = f"""
        SELECT * FROM `{db.get_table_ref('AccessLog')}`
        WHERE 1=1
        {f"AND gate_id = @gate_id" if gate_id else ""}
        {f"AND timestamp >= @start_date" if start_date else ""}
        {f"AND timestamp <= @end_date" if end_date else ""}
        ORDER BY timestamp DESC
        LIMIT @limit
    """
    
    # Set up query parameters
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("limit", "INTEGER", limit)
        ]
    )
    if gate_id:
        job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("gate_id", "STRING", gate_id)
        )
    if start_date:
        job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", start_date)
        )
    if end_date:
        job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", end_date)
        )
    
    logs_data = list(db.client.query(query, job_config=job_config).result())
    
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
    gate = db.get_gate(gate_id)
    if not gate:
        return jsonify({'error': 'Gate not found'}), 404
    
    # Send manual override command via MQTT
    topic = f"gate/{gate_id}/control"
    mqtt.publish(topic, {'action': 'open'})
    
    # Log the manual override
    success = db.create_access_log(
        plate_number='MANUAL_OVERRIDE',
        gate_id=gate_id,
        access_granted=True,
        confidence_score=1.0
    )
    
    return jsonify({'status': 'success' if success else 'error'})

@api_bp.route('/api/gate_status', methods=['POST'])
def update_gate_status():
    """Update gate status via HTTP (fallback if MQTT fails)"""
    data = request.json
    gate_id = data.get('gate_id')
    status = data.get('status')
    
    if not gate_id or not status:
        return jsonify({'error': 'Missing required fields'}), 400
        
    gate = db.get_gate(gate_id)
    if gate:
        success = db.update_gate_status(gate_id, status, datetime.utcnow())
        return jsonify({'status': 'success' if success else 'error'})
    
    # If gate doesn't exist, create it
    table_ref = db.get_table_ref('Gate')
    rows_to_insert = [{
        'gate_id': gate_id,
        'status': status,
        'last_online': datetime.utcnow().isoformat()
    }]
    errors = db.client.insert_rows_json(table_ref, rows_to_insert)
    return jsonify({'status': 'success' if not errors else 'error'})