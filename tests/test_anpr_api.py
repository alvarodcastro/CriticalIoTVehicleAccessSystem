import unittest
from app import create_app, db
from app.database.models import Vehicle, AccessLog, Gate, User
from datetime import datetime, timedelta

class TestANPRSystem(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        
        # Create test user
        from werkzeug.security import generate_password_hash
        test_user = User(
            username='test_admin',
            password_hash=generate_password_hash('test123'),
            is_admin=True
        )
        db.session.add(test_user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self):
        return self.client.post('/login', data={
            'username': 'test_admin',
            'password': 'test123'
        }, follow_redirects=True)

    def test_vehicle_authorization(self):
        # Create test vehicle
        vehicle = Vehicle(
            plate_number='ABC123',
            owner_name='Test Owner',
            is_authorized=True,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(vehicle)
        db.session.commit()

        # Create test gate
        gate = Gate(gate_id='test_gate', status='online')
        db.session.add(gate)
        db.session.commit()

        # Test vehicle authorization
        self.assertTrue(vehicle.is_currently_valid())

        # Test expired vehicle
        vehicle.valid_until = datetime.utcnow() - timedelta(days=1)
        db.session.commit()
        self.assertFalse(vehicle.is_currently_valid())

    def test_api_endpoints(self):
        self.login()
        
        # Test vehicle creation
        response = self.client.post('/vehicles/add', data={
            'plate_number': 'XYZ789',
            'owner_name': 'API Test',
            'valid_from': datetime.utcnow().strftime('%Y-%m-%d'),
            'valid_until': (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d')
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Verify vehicle was created
        vehicle = Vehicle.query.filter_by(plate_number='XYZ789').first()
        self.assertIsNotNone(vehicle)
        self.assertEqual(vehicle.owner_name, 'API Test')

    def test_gate_status_update(self):
        # Create test gate
        gate = Gate(gate_id='test_gate', status='offline')
        db.session.add(gate)
        db.session.commit()

        # Test gate status update
        response = self.client.post('/api/gate_status', json={
            'gate_id': 'test_gate',
            'status': 'online'
        })
        self.assertEqual(response.status_code, 200)

        # Verify gate status was updated
        gate = Gate.query.filter_by(gate_id='test_gate').first()
        self.assertEqual(gate.status, 'online')

if __name__ == '__main__':
    unittest.main()