from flask_login import UserMixin
from datetime import datetime
from .. import login_manager

class User(UserMixin):    
    def __init__(self, data):
        if hasattr(data, '_xxx_values'):  # Es un Row de BigQuery
            values = data._xxx_values
            self.id = str(values[0])  # El ID está en la primera posición
            self.username = values[1]
            self.password = values[2]
            self.is_admin = values[3]
            self.created_at = values[4]
        else:  # Es un diccionario
            self.id = str(data['id'])
            self.username = data['username']
            self.password = data['password']
            self.is_admin = data['is_admin']
            self.created_at = data['created_at']
        
    def get_id(self):
        return str(self.id)

class Vehicle:
    def __init__(self, data):
        if hasattr(data, '_xxx_values'):
            values = data._xxx_values
            self.id = str(values[0])
            self.plate_number = values[1]
            self.owner_name = values[2]
            self.is_authorized = values[3]
            self.valid_from = values[4]
            self.valid_until = values[5]
            self.last_sync = values[6]
        else:
            self.id = data['id'] if 'id' in data else None
            self.plate_number = data['plate_number']
            self.owner_name = data['owner_name']
            self.is_authorized = data['is_authorized']
            self.valid_from = data['valid_from']
            self.valid_until = data['valid_until']
            self.last_sync = data['last_sync']
    
    def is_currently_valid(self):
        now = datetime.utcnow()
        
        if isinstance(self.valid_from, str):
            self.valid_from = datetime.fromisoformat(self.valid_from)
        
        if self.valid_until and isinstance(self.valid_until, str):
            self.valid_until = datetime.fromisoformat(self.valid_until)
        
        if not self.is_authorized:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return now >= self.valid_from

class AccessLog:
    def __init__(self, data=None, plate_number=None, gate_id=None, 
                 access_granted=None, confidence_score=None, accessing=False):
        if data:
            self.id = data['id'] if 'id' in data else None
            self.plate_number = data['plate_number']
            self.timestamp = data['timestamp']
            self.access_granted = data['access_granted']
            self.confidence_score = data.get('confidence_score')
            self.gate_id = data['gate_id']
            self.image_path = data.get('image_path')
            self.accessing = data.get('accessing', False)
        else:
            self.id = None
            self.plate_number = plate_number
            self.gate_id = gate_id
            self.access_granted = access_granted
            self.confidence_score = confidence_score
            self.timestamp = datetime.utcnow()
            self.image_path = None
            self.accessing = accessing

class Gate:
    def __init__(self, data):
        if hasattr(data, '_xxx_values'):
            values = data._xxx_values
            self.id = str(values[0])
            self.gate_id = values[1]
            self.location = values[2]
            self.last_online = values[3]
            self.status = values[4]
            self.local_cache_updated = values[5]
        else:
            self.id = data['id'] if 'id' in data else None
            self.gate_id = data['gate_id']
            self.location = data.get('location')
            self.last_online = data.get('last_online')
            self.status = data.get('status', 'offline')
            self.local_cache_updated = data.get('local_cache_updated')

class Pagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = (total + per_page - 1) // per_page

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1

    @property
    def next_num(self):
        return self.page + 1

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        """Helper function to generate page numbers for pagination"""
        last = 0
        for num in range(1, self.pages + 1):
            # If num is within left_edge pages from start
            if num <= left_edge:
                yield num
                last = num
            # If num is within left_current pages before current page
            elif num > self.page - left_current - 1 and num < self.page + right_current:
                if last + 1 != num:
                    yield None
                yield num
                last = num
            # If num is within right_edge pages from end
            elif num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num
            elif last + 1 < num:
                yield None
                last = None

@login_manager.user_loader
def load_user(user_id):
    from .. import db
    
    try:
        result = db.get_user_by_id(user_id)
        if result:
            user = User(result)
            return user
    except Exception as e:
        print(f"Error loading user: {e}")
    print(f"User {user_id} not found")
    return None