from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ..database.models import User
from .. import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        username_error = None
        password_error = None
        
        user_data = db.get_user_by_username(username)
        if not username:
            username_error = 'Username is required'
        elif not password:
            password_error = 'Password is required'
        elif not user_data or not check_password_hash(user_data['password'], password):
            username_error = 'Incorrect credentials'
            password_error = 'Incorrect credentials'
        
        if username_error or password_error:
            flash('Login failed. Please check your credentials.', 'danger')
            return render_template('auth/login.html', 
                                username_error=username_error, 
                                password_error=password_error) 
        
        user = User(user_data)
        success = login_user(user, remember=remember)
        
        if not success:
            flash('Error logging in. Please try again.', 'danger')
            return render_template('auth/login.html')
            
        flash('Welcome back, {}!'.format(user.username), 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_admin:
        flash('Unauthorized')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin') == 'on'
        
        if db.get_user_by_username(username):
            flash('Username already exists')
            return redirect(url_for('auth.create_user'))
        
        success = db.create_user(
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=is_admin
        )
        
        if success:
            flash('User created successfully')
        else:
            flash('Error creating user')
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth/create_user.html')