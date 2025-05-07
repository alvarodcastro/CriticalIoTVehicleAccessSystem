import os
from app import create_app
from werkzeug.security import generate_password_hash
from app.database.models import User, db

app = create_app()

def create_admin_if_not_exists():
    """Create default admin user if no users exist"""
    with app.app_context():
        if User.query.first() is None:
            admin = User(
                username="admin",
                password_hash=generate_password_hash("admin123"),  # Change this password in production
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created")

if __name__ == "__main__":
    # Ensure the models directory exists
    os.makedirs(os.path.join("app", "models"), exist_ok=True)
    
    # Create admin user if needed
    create_admin_if_not_exists()
    
    # Start the application
    app.run(host='0.0.0.0', port=5000, debug=True)