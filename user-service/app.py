import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer
import bcrypt
from models import db, User, UserActivity, UserIntegration
from threading import Thread

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)

# Initialize Kafka producer
kafka_config = {
    'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
}
producer = Producer(kafka_config)

# Kafka message delivery callback
def delivery_report(err, msg):
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}]')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'user-service'}), 200

@app.route('/users', methods=['GET'])
def get_users():
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(user.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.json
        # Basic validation
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 409
        
        # Hash password
        password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create new user
        new_user = User(
            email=data['email'],
            password_hash=password_hash,
            full_name=data.get('full_name', ''),
            role_id=data.get('role_id', 1)  # Default to regular user role
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Publish user creation event to Kafka
        user_created_event = {
            'event_type': 'user_created',
            'user_id': new_user.user_id,
            'email': new_user.email
        }
        producer.produce(
            'user-events', 
            key=str(new_user.user_id), 
            value=json.dumps(user_created_event),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.json
        
        # Update user fields
        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'role_id' in data:
            user.role_id = data['role_id']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'password' in data:
            user.password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        db.session.commit()
        
        # Publish user update event to Kafka
        user_updated_event = {
            'event_type': 'user_updated',
            'user_id': user.user_id
        }
        producer.produce(
            'user-events', 
            key=str(user.user_id), 
            value=json.dumps(user_updated_event),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/users/<int:user_id>/integrations', methods=['GET'])
def get_user_integrations(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        integrations = UserIntegration.query.filter_by(user_id=user_id).all()
        return jsonify([{
            'integration_id': integration.integration_id,
            'service_name': integration.service_name,
            'external_id': integration.external_id,
            'created_at': integration.created_at.isoformat() if integration.created_at else None,
            'updated_at': integration.updated_at.isoformat() if integration.updated_at else None
        } for integration in integrations]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users/<int:user_id>/activity', methods=['GET'])
def get_user_activity(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        activities = UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.timestamp.desc()).limit(50).all()
        return jsonify([{
            'activity_id': activity.activity_id,
            'action_type': activity.action_type,
            'timestamp': activity.timestamp.isoformat() if activity.timestamp else None,
            'metadata': activity.metadata
        } for activity in activities]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        # Configure consumer
        consumer_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
            'group.id': 'user-service-group',
            'auto.offset.reset': 'earliest'
        }
        
        consumer = Consumer(consumer_config)
        
        # Subscribe to relevant topics
        consumer.subscribe(['auth.user.registered', 'user.role_changed', 'user.deactivated'])
        
        # Process messages
        while True:
            try:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                
                if msg.error():
                    print(f"Consumer error: {msg.error()}")
                    continue
                
                # Parse message
                try:
                    message_value = json.loads(msg.value().decode('utf-8'))
                    topic = msg.topic()
                    print(f"Received message: {message_value} from topic {topic}")
                    
                    # Handle different message types based on topic
                    if topic == 'auth.user.registered':
                        process_user_registration(message_value)
                    elif topic == 'user.role_changed':
                        process_role_change(message_value)
                    elif topic == 'user.deactivated':
                        process_user_deactivation(message_value)
                    
                except json.JSONDecodeError as e:
                    print(f"Error decoding message: {e}")
                    
            except Exception as e:
                print(f"Error processing message: {e}")
                
    except Exception as e:
        print(f"Error setting up Kafka consumer: {e}")
    finally:
        # Close consumer when exiting
        try:
            consumer.close()
        except Exception as e:
            print(f"Error closing consumer: {e}")

def process_user_registration(message_data):
    """Process user registration message from auth service"""
    try:
        # Extract user data from message
        user_id = message_data.get('user_id')
        email = message_data.get('email')
        full_name = message_data.get('full_name')
        role_id = message_data.get('role_id')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"User already exists with email {email}")
            return
        
        # Create user record in user service database
        new_user = User(
            user_id=user_id,
            email=email,
            full_name=full_name,
            role_id=role_id,
            is_active=True
        )
        
        with app.app_context():
            db.session.add(new_user)
            db.session.commit()
            print(f"User created from auth service registration: {user_id}")
            
            # Log user activity
            activity = UserActivity(
                user_id=user_id,
                action_type='user_registered',
                metadata={'source': 'auth_service'}
            )
            db.session.add(activity)
            db.session.commit()
    
    except Exception as e:
        print(f"Error processing user registration message: {e}")
        with app.app_context():
            db.session.rollback()

def process_role_change(message_data):
    """Process user role change message"""
    try:
        user_id = message_data.get('user_id')
        new_role_id = message_data.get('role_id')
        
        if not user_id or not new_role_id:
            print("Missing user_id or role_id in role change message")
            return
        
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                print(f"User not found for role change: {user_id}")
                return
            
            user.role_id = new_role_id
            db.session.commit()
            print(f"Updated role for user {user_id} to {new_role_id}")
            
            # Log user activity
            activity = UserActivity(
                user_id=user_id,
                action_type='role_changed',
                metadata={'new_role_id': new_role_id}
            )
            db.session.add(activity)
            db.session.commit()
    
    except Exception as e:
        print(f"Error processing role change message: {e}")
        with app.app_context():
            db.session.rollback()

def process_user_deactivation(message_data):
    """Process user deactivation message"""
    try:
        user_id = message_data.get('user_id')
        
        if not user_id:
            print("Missing user_id in deactivation message")
            return
        
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                print(f"User not found for deactivation: {user_id}")
                return
            
            user.is_active = False
            db.session.commit()
            print(f"Deactivated user {user_id}")
            
            # Log user activity
            activity = UserActivity(
                user_id=user_id,
                action_type='account_deactivated',
                metadata={'reason': message_data.get('reason', 'not specified')}
            )
            db.session.add(activity)
            db.session.commit()
    
    except Exception as e:
        print(f"Error processing user deactivation message: {e}")
        with app.app_context():
            db.session.rollback()

# Start Kafka consumer in a separate thread
consumer_thread = Thread(target=start_kafka_consumer)
consumer_thread.daemon = True

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Start Kafka consumer thread
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5001) 