import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer
from models import db, Client, ClientContact, ClientActivity
from threading import Thread
from datetime import datetime

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
    return jsonify({'status': 'healthy', 'service': 'client-service'}), 200

@app.route('/clients', methods=['GET'])
def get_clients():
    try:
        # Optional query parameters for filtering
        status = request.args.get('status')
        
        # Base query
        query = Client.query
        
        # Apply filters if provided
        if status:
            query = query.filter_by(status=status)
            
        clients = query.all()
        return jsonify([client.to_dict() for client in clients]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        return jsonify(client.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clients', methods=['POST'])
def create_client():
    try:
        data = request.json
        
        # Basic validation
        required_fields = ['name', 'email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if client already exists
        existing_client = Client.query.filter_by(email=data['email']).first()
        if existing_client:
            return jsonify({'error': 'Client with this email already exists'}), 409
        
        # Create new client
        new_client = Client(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone', ''),
            company=data.get('company', ''),
            address=data.get('address', ''),
            status=data.get('status', 'active'),
            source=data.get('source', 'direct'),
            notes=data.get('notes', '')
        )
        
        db.session.add(new_client)
        db.session.commit()
        
        # Publish client creation event to Kafka
        client_created = {
            'event_type': 'client_created',
            'client_id': new_client.client_id,
            'name': new_client.name,
            'email': new_client.email
        }
        producer.produce(
            'client-events', 
            key=str(new_client.client_id), 
            value=json.dumps(client_created),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(new_client.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.json
        
        # Update client fields
        if 'name' in data:
            client.name = data['name']
        if 'email' in data:
            client.email = data['email']
        if 'phone' in data:
            client.phone = data['phone']
        if 'company' in data:
            client.company = data['company']
        if 'address' in data:
            client.address = data['address']
        if 'status' in data:
            client.status = data['status']
        if 'source' in data:
            client.source = data['source']
        if 'notes' in data:
            client.notes = data['notes']
        
        db.session.commit()
        
        # Publish client update event to Kafka
        client_updated = {
            'event_type': 'client_updated',
            'client_id': client.client_id,
            'name': client.name,
            'email': client.email
        }
        producer.produce(
            'client-events', 
            key=str(client.client_id), 
            value=json.dumps(client_updated),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(client.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/clients/<int:client_id>/contacts', methods=['GET'])
def get_client_contacts(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        contacts = ClientContact.query.filter_by(client_id=client_id).all()
        return jsonify([contact.to_dict() for contact in contacts]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clients/<int:client_id>/contacts', methods=['POST'])
def add_client_contact(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.json
        
        # Basic validation
        required_fields = ['name', 'email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new contact
        new_contact = ClientContact(
            client_id=client_id,
            name=data['name'],
            email=data['email'],
            phone=data.get('phone', ''),
            position=data.get('position', ''),
            is_primary=data.get('is_primary', False),
            notes=data.get('notes', '')
        )
        
        db.session.add(new_contact)
        db.session.commit()
        
        return jsonify(new_contact.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/clients/<int:client_id>/activity', methods=['GET'])
def get_client_activity(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        activities = ClientActivity.query.filter_by(client_id=client_id).order_by(ClientActivity.timestamp.desc()).all()
        return jsonify([activity.to_dict() for activity in activities]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clients/<int:client_id>/activity', methods=['POST'])
def log_client_activity(client_id):
    try:
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.json
        
        # Basic validation
        if 'activity_type' not in data:
            return jsonify({'error': 'activity_type is required'}), 400
        
        # Create new activity log
        new_activity = ClientActivity(
            client_id=client_id,
            activity_type=data['activity_type'],
            description=data.get('description', ''),
            user_id=data.get('user_id'),
            metadata=data.get('metadata', {})
        )
        
        db.session.add(new_activity)
        db.session.commit()
        
        return jsonify(new_activity.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        # Configure consumer
        consumer_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
            'group.id': 'client-service-group',
            'auto.offset.reset': 'earliest'
        }
        
        consumer = Consumer(consumer_config)
        
        # Subscribe to relevant topics
        consumer.subscribe(['user-events', 'event-events', 'payment-events'])
        
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
                    if topic == 'user-events':
                        handle_user_message(message_value)
                    elif topic == 'event-events':
                        handle_event_message(message_value)
                    elif topic == 'payment-events':
                        handle_payment_message(message_value)
                    
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

def handle_user_message(message_data):
    """Handle user-related messages"""
    try:
        event_type = message_data.get('event_type')
        user_id = message_data.get('user_id')
        
        if not event_type or not user_id:
            print("Missing event_type or user_id in message")
            return
        
        with app.app_context():
            # Find client associated with this user
            client = Client.query.filter_by(email=message_data.get('email')).first()
            
            if not client:
                # This might be a new user that's not yet a client
                if event_type == 'user_created':
                    # Optionally create a client record automatically
                    # This depends on the business logic
                    pass
                return
            
            # Handle user deletion or deactivation
            if event_type == 'user_deleted':
                # Log client activity
                activity = ClientActivity(
                    client_id=client.client_id,
                    activity_type='account_deleted',
                    description='User account was deleted',
                    user_id=user_id
                )
                db.session.add(activity)
                
                # Optionally update client status
                client.status = 'inactive'
                db.session.add(client)
                db.session.commit()
                
            elif event_type == 'user_deactivated':
                # Log client activity
                activity = ClientActivity(
                    client_id=client.client_id,
                    activity_type='account_deactivated',
                    description='User account was deactivated',
                    user_id=user_id
                )
                db.session.add(activity)
                
                # Update client status
                client.status = 'inactive'
                db.session.add(client)
                db.session.commit()
                
            elif event_type == 'user_updated':
                # Log client activity
                activity = ClientActivity(
                    client_id=client.client_id,
                    activity_type='account_updated',
                    description='User account was updated',
                    user_id=user_id
                )
                db.session.add(activity)
                db.session.commit()
                
    except Exception as e:
        print(f"Error handling user message: {e}")
        with app.app_context():
            db.session.rollback()

def handle_event_message(message_data):
    """Handle event-related messages"""
    try:
        event_type = message_data.get('event_type')
        event_id = message_data.get('event_id')
        
        if not event_type or not event_id:
            print("Missing event_type or event_id in message")
            return
        
        with app.app_context():
            # Find clients associated with this event
            # This is a simplified example - in a real system, you would have a way
            # to find all clients associated with an event
            if event_type in ['event_created', 'event_updated', 'event_cancelled']:
                # This could trigger notifications to relevant clients
                # Or update client activity logs
                print(f"Received {event_type} for event {event_id} - would notify relevant clients")
                
    except Exception as e:
        print(f"Error handling event message: {e}")
        with app.app_context():
            db.session.rollback()

def handle_payment_message(message_data):
    """Handle payment-related messages"""
    try:
        event_type = message_data.get('event_type')
        user_id = message_data.get('user_id')
        
        if not event_type or not user_id:
            print("Missing event_type or user_id in payment message")
            return
        
        with app.app_context():
            # Find client associated with this user
            # This assumes there's a one-to-one mapping between users and clients
            # In a real system, this might be more complex
            client = Client.query.filter_by(email=message_data.get('email')).first()
            
            if not client:
                print(f"No client found for user {user_id}")
                return
                
            # Log payment activity
            if event_type == 'payment_completed':
                activity = ClientActivity(
                    client_id=client.client_id,
                    activity_type='payment_made',
                    description=f"Payment of {message_data.get('amount')} {message_data.get('currency')} for {message_data.get('reference_type')}",
                    user_id=user_id,
                    metadata={
                        'amount': message_data.get('amount'),
                        'currency': message_data.get('currency'),
                        'reference_type': message_data.get('reference_type'),
                        'reference_id': message_data.get('reference_id')
                    }
                )
                db.session.add(activity)
                db.session.commit()
                
            elif event_type == 'payment_refunded':
                activity = ClientActivity(
                    client_id=client.client_id,
                    activity_type='payment_refunded',
                    description=f"Refund of {message_data.get('amount')} {message_data.get('currency')} for {message_data.get('reference_type')}",
                    user_id=user_id,
                    metadata={
                        'amount': message_data.get('amount'),
                        'currency': message_data.get('currency'),
                        'reference_type': message_data.get('reference_type'),
                        'reference_id': message_data.get('reference_id')
                    }
                )
                db.session.add(activity)
                db.session.commit()
                
    except Exception as e:
        print(f"Error handling payment message: {e}")
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
    
    app.run(host='0.0.0.0', port=5004) 