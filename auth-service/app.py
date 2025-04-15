import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
import time

from models import db, User, Role

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://{0}:{1}@{2}:{3}/{4}'.format(
    os.getenv('DB_USERNAME'),
    os.getenv('DB_PASSWORD'),
    os.getenv('DB_HOST'),
    os.getenv('DB_PORT'),
    os.getenv('DB_NAME')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Initialize SQLAlchemy
db.init_app(app)

# Create Kafka producer
kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
producer = None
try:
    producer = KafkaProducer(
        bootstrap_servers=kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
except Exception as e:
    print(f"Error creating Kafka producer: {e}")

# Define Kafka topics
USER_CREATED_TOPIC = 'user.created'
USER_UPDATED_TOPIC = 'user.updated'
USER_AUTHENTICATED_TOPIC = 'user.authenticated'
USER_PASSWORD_CHANGED_TOPIC = 'user.password_changed'

# Helper functions
def generate_token(user_id, role_name):
    """Generate a JWT token for the user"""
    payload = {
        'exp': datetime.utcnow() + datetime.timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400))),
        'iat': datetime.utcnow(),
        'sub': user_id,
        'role': role_name
    }
    return jwt.encode(payload, os.getenv('JWT_SECRET_KEY'), algorithm='HS256')

def hash_password(password):
    """Generate a hashed version of the password"""
    return generate_password_hash(password)

def verify_password(hashed_password, password):
    """Check if the provided password matches the hashed password"""
    return check_password_hash(hashed_password, password)

def publish_event(topic, key, data):
    """Publish event to Kafka"""
    if producer:
        try:
            future = producer.send(topic, key=key, value=data)
            producer.flush()
            print(f"Published event to {topic}: {data}")
            return future
        except Exception as e:
            print(f"Error publishing to Kafka: {e}")
            return None
    return None

# API Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'auth-service'}), 200

@app.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['email', 'password', 'full_name']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'User already exists with this email'}), 409
    
    # Get default client role
    client_role = Role.query.filter_by(role_name='client').first()
    if not client_role:
        return jsonify({'message': 'Error with role configuration'}), 500
    
    # Create new user
    new_user = User(
        email=data['email'],
        password_hash=hash_password(data['password']),
        full_name=data['full_name'],
        role_id=client_role.role_id,
        created_at=datetime.utcnow(),
        is_active=True
    )
    
    # Save to database
    db.session.add(new_user)
    db.session.commit()
    
    # Generate token
    token = generate_token(new_user.user_id, 'client')

    # Publish to Kafka
    user_data = new_user.to_dict()
    publish_event(USER_CREATED_TOPIC, key={"user_id": new_user.user_id}, data=user_data)
    
    return jsonify({
        'message': 'User registered successfully',
        'token': token,
        'user': user_data
    }), 201

@app.route('/login', methods=['POST'])
def login():
    """Authenticate a user and return a token"""
    data = request.get_json()
    
    # Validate required fields
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'message': 'Missing email or password'}), 400
    
    # Find user by email
    user = User.query.filter_by(email=data['email']).first()
    
    # Check if user exists and password is correct
    if not user or not verify_password(user.password_hash, data['password']):
        return jsonify({'message': 'Invalid email or password'}), 401
    
    # Check if user is active
    if not user.is_active:
        return jsonify({'message': 'Account is deactivated. Please contact support.'}), 403
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Get role name
    role_name = user.role.role_name if user.role else 'client'
    
    # Generate token
    token = generate_token(user.user_id, role_name)

    # Publish to Kafka
    user_data = user.to_dict()
    publish_event(USER_AUTHENTICATED_TOPIC, key={"user_id": user.user_id}, data=user_data)
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user_data
    }), 200

@app.route('/profile', methods=['GET'])
def get_profile():
    """Get the profile of the authenticated user"""
    # Get token from header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'message': 'Missing or invalid token'}), 401

    token = auth_header.split(' ')[1]
    
    try:
        # Decode token
        payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
        user_id = payload['sub']
        
        # Get user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        return jsonify(user.to_dict()), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token expired. Please log in again.'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token. Please log in again.'}), 401

@app.route('/change-password', methods=['PUT'])
def change_password():
    """Change the password of the authenticated user"""
    # Get token from header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'message': 'Missing or invalid token'}), 401

    token = auth_header.split(' ')[1]
    
    try:
        # Decode token
        payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
        user_id = payload['sub']
        
        data = request.get_json()
        
        # Validate required fields
        if not data or 'current_password' not in data or 'new_password' not in data:
            return jsonify({'message': 'Missing current or new password'}), 400
        
        # Find user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Verify current password
        if not verify_password(user.password_hash, data['current_password']):
            return jsonify({'message': 'Current password is incorrect'}), 401
        
        # Update password
        user.password_hash = hash_password(data['new_password'])
        db.session.commit()

        # Publish to Kafka
        user_data = user.to_dict()
        publish_event(USER_PASSWORD_CHANGED_TOPIC, key={"user_id": user.user_id}, data=user_data)
        
        return jsonify({'message': 'Password changed successfully'}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token expired. Please log in again.'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token. Please log in again.'}), 401

@app.route('/validate-token', methods=['POST'])
def validate_token():
    """Validate a JWT token"""
    data = request.get_json()
    
    if not data or 'token' not in data:
        return jsonify({'message': 'Missing token'}), 400
    
    token = data['token']
    
    try:
        # Decode token
        payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
        
        # Return decoded information
        return jsonify({
            'valid': True,
            'user_id': payload['sub'],
            'role': payload['role'],
            'expires': payload['exp']
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'message': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'valid': False, 'message': 'Invalid token'}), 401

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda v: json.loads(v.decode('utf-8')),
            group_id='auth-service-group',
            auto_offset_reset='earliest'
        )
        
        # Subscribe to relevant topics
        # Example: consumer.subscribe(['user.role_changed', 'user.deactivated'])
        
        # Process messages
        for message in consumer:
            print(f"Received message: {message.value} from topic {message.topic}")
            
            # Handle different message types
            if message.topic == 'user.role_changed':
                # Update user's role
                pass
            elif message.topic == 'user.deactivated':
                # Deactivate user
                pass
    except Exception as e:
        print(f"Error in Kafka consumer: {e}")

# Start Kafka consumer in a separate thread
consumer_thread = Thread(target=start_kafka_consumer)
consumer_thread.daemon = True

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        
        # Create default roles if they don't exist
        admin_role = Role.query.filter_by(role_name='admin').first()
        manager_role = Role.query.filter_by(role_name='manager').first()
        client_role = Role.query.filter_by(role_name='client').first()
        
        if not admin_role:
            admin_role = Role(
                role_name='admin', 
                permissions={"can_edit_events": True, "can_view_reports": True, "can_manage_users": True}
            )
            db.session.add(admin_role)
        
        if not manager_role:
            manager_role = Role(
                role_name='manager',
                permissions={"can_edit_events": True, "can_view_reports": True, "can_manage_users": False}
            )
            db.session.add(manager_role)
        
        if not client_role:
            client_role = Role(
                role_name='client',
                permissions={"can_edit_events": False, "can_view_reports": False, "can_manage_users": False}
            )
            db.session.add(client_role)
        
        # Create admin user if it doesn't exist
        admin_user = User.query.filter_by(email='admin@masterspro.com').first()
        if not admin_user:
            admin_user = User(
                email='admin@masterspro.com',
                password_hash=hash_password('Admin123!'),
                full_name='Admin User',
                role_id=admin_role.role_id if admin_role else None,
                created_at=datetime.utcnow(),
                is_active=True
            )
            db.session.add(admin_user)
        
        db.session.commit()
    
    # Start Kafka consumer
    consumer_thread.start()
    
    # Run Flask app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 