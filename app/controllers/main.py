from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..database.models import Vehicle, AccessLog, Gate, db
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    # Get recent access logs
    recent_logs = AccessLog.query.order_by(AccessLog.timestamp.desc()).limit(10).all()
    
    # Get gate statuses
    gates = Gate.query.all()
    
    # Get statistics
    stats = {
        'vehicle_count': Vehicle.query.filter_by(is_authorized=True).count(),
        'online_gates': Gate.query.filter_by(status='online').count(),
        'total_gates': len(gates),
        'today_accesses': AccessLog.query.filter(
            AccessLog.timestamp >= datetime.utcnow().date()
        ).count()
    }
    
    return render_template('main/dashboard.html',
                         logs=recent_logs,
                         gates=gates,
                         stats=stats)

@main_bp.route('/vehicles')
@login_required
def list_vehicles():
    vehicles = Vehicle.query.all()
    return render_template('main/vehicles.html', vehicles=vehicles)

@main_bp.route('/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if request.method == 'POST':
        plate_number = request.form.get('plate_number')
        owner_name = request.form.get('owner_name')
        valid_from = datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d')
        valid_until = request.form.get('valid_until')
        print(f"Valid until: {valid_until}")
        if valid_until:
            valid_until = datetime.strptime(valid_until, '%Y-%m-%d')
        else:
            valid_until = None
        
        if Vehicle.query.filter_by(plate_number=plate_number).first():
            flash('Vehicle already exists')
            return redirect(url_for('main.add_vehicle'))
        
        vehicle = Vehicle(
            plate_number=plate_number,
            owner_name=owner_name,
            is_authorized=True,
            valid_from=valid_from,
            valid_until=valid_until,
            last_sync=datetime.utcnow()
        )
        db.session.add(vehicle)
        db.session.commit()
        
        flash('Vehicle added successfully')
        return redirect(url_for('main.list_vehicles'))
    
    return render_template('main/add_vehicle.html')

@main_bp.route('/vehicles/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)
    
    if request.method == 'POST':
        vehicle.owner_name = request.form.get('owner_name')
        vehicle.is_authorized = request.form.get('is_authorized') == 'on'
        vehicle.valid_from = datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d')
        valid_until = request.form.get('valid_until')
        vehicle.valid_until = datetime.strptime(valid_until, '%Y-%m-%d') if valid_until else None
        vehicle.last_sync = datetime.utcnow()
        
        db.session.commit()
        flash('Vehicle updated successfully')
        return redirect(url_for('main.list_vehicles'))
    
    return render_template('main/edit_vehicle.html', vehicle=vehicle)

@main_bp.route('/access-logs')
@login_required
def access_logs():
    page = request.args.get('page', 1, type=int)
    logs = AccessLog.query.order_by(AccessLog.timestamp.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('main/access_logs.html', logs=logs)

@main_bp.route('/gates', methods=['GET'])
@login_required
def gates():
    gates = Gate.query.all()
    return render_template('main/gates.html', gates=gates)

@main_bp.route('/gates/add', methods=['POST'])
@login_required
def add_gate():
    gate_id = request.form.get('gate_id')
    location = request.form.get('location')
    
    if Gate.query.filter_by(gate_id=gate_id).first():
        flash('Gate ID already exists')
        return redirect(url_for('main.gates'))
    
    gate = Gate(
        gate_id=gate_id,
        location=location,
        status='offline'
    )
    db.session.add(gate)
    db.session.commit()
    
    flash('Gate added successfully')
    return redirect(url_for('main.gates'))

@main_bp.route('/gates/<gate_id>/delete', methods=['POST'])
@login_required
def delete_gate(gate_id):
    gate = Gate.query.filter_by(gate_id=gate_id).first_or_404()
    db.session.delete(gate)
    db.session.commit()
    return jsonify({'status': 'success'})

@main_bp.route('/gates/<gate_id>/sync', methods=['POST'])
@login_required
def sync_gate(gate_id):
    gate = Gate.query.filter_by(gate_id=gate_id).first_or_404()
    gate.local_cache_updated = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success'})