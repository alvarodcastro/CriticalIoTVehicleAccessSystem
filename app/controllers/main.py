from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..database.models import Vehicle, AccessLog, Gate, Pagination
from datetime import datetime
from .. import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    # Get recent access logs
    recent_logs = db.get_access_logs(limit=10)
    
    # Get gate statuses
    gates_data = db.list_gates()
    gates = [Gate(g) for g in gates_data]
    
    # Get statistics
    stats = db.get_dashboard_stats()
    stats['total_gates'] = len(gates)  # Añadir total_gates al diccionario de stats
    
    return render_template('main/dashboard.html',
                         logs=recent_logs,
                         gates=gates,
                         stats=stats)

@main_bp.route('/vehicles')
@login_required
def list_vehicles():
    vehicles_data = db.list_vehicles()
    vehicles = [Vehicle(v) for v in vehicles_data]
    return render_template('main/vehicles.html', vehicles=vehicles)

@main_bp.route('/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if request.method == 'POST':
        plate_number = request.form.get('plate_number')
        owner_name = request.form.get('owner_name')
        valid_from = datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d')
        valid_until = request.form.get('valid_until')
        if valid_until:
            valid_until = datetime.strptime(valid_until, '%Y-%m-%d')
        
        if db.get_vehicle_by_plate(plate_number):
            flash('Vehicle already exists')
            return redirect(url_for('main.add_vehicle'))
        
        success, errors = db.add_vehicle(plate_number, owner_name, valid_from, valid_until)
        if not success:
            flash(f'Error adding vehicle: {errors}')
            return redirect(url_for('main.add_vehicle'))
        
        flash('Vehicle added successfully')
        return redirect(url_for('main.list_vehicles'))
    
    return render_template('main/add_vehicle.html')

@main_bp.route('/vehicles/<string:plate_number>/edit', methods=['GET', 'POST'])
@login_required
def edit_vehicle(plate_number):
    vehicle_data = db.get_vehicle_by_plate(plate_number)
    if not vehicle_data:
        flash('Vehicle not found')
        return redirect(url_for('main.list_vehicles'))
    
    vehicle = Vehicle(vehicle_data)
    if request.method == 'POST':
        try:
            # Preparar los datos
            owner_name = request.form.get('owner_name')
            is_authorized = request.form.get('is_authorized') == 'on'
            valid_from = datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d')
            valid_until = request.form.get('valid_until')
            if valid_until:
                valid_until = datetime.strptime(valid_until, '%Y-%m-%d')            
            
            success, error = db.update_vehicle(plate_number, owner_name, is_authorized, valid_from, valid_until)
            if not success:
                raise Exception(error)
            
            flash('Vehicle updated successfully', 'success')
            return redirect(url_for('main.list_vehicles'))
            
        except ValueError as e:
            flash(f'Error validating data: {str(e)}', 'danger')
            return render_template('main/edit_vehicle.html', vehicle=vehicle)               
            
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
            return render_template('main/edit_vehicle.html', vehicle=vehicle)
    
    return render_template('main/edit_vehicle.html', vehicle=vehicle)

@main_bp.route('/access-logs')
@login_required
def access_logs():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    result = db.get_paginated_access_logs(page, per_page)
    if result is None:
        flash('Error retrieving access logs', 'error')
        return redirect(url_for('main.dashboard'))
    
    logs = [AccessLog(log) for log in result['logs']]
    pagination = Pagination(logs, result['page'], result['per_page'], result['total'])
    return render_template('main/access_logs.html', logs=pagination)

@main_bp.route('/gates', methods=['GET'])
@login_required
def gates():
    gates_data = db.list_gates()
    gates = [Gate(g) for g in gates_data]
    return render_template('main/gates.html', gates=gates)

@main_bp.route('/gates/add', methods=['POST'])
@login_required
def add_gate():
    gate_id = request.form.get('gate_id')
    location = request.form.get('location')
    
    if db.get_gate(gate_id):
        flash('Gate ID already exists')
        return redirect(url_for('main.gates'))
    
    success, errors = db.add_gate(gate_id, location)
    if success:
        flash('Gate added successfully')
    else:
        flash(f'Error adding gate: {errors}')
    return redirect(url_for('main.gates'))

@main_bp.route('/gates/<gate_id>/delete', methods=['POST'])
@login_required
def delete_gate(gate_id):
    if db.delete_gate(gate_id):
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 500

@main_bp.route('/gates/<gate_id>/sync', methods=['POST'])
@login_required
def sync_gate(gate_id):
    if db.sync_gate(gate_id):
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 500