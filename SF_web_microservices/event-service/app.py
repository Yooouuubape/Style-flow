import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer
from models import db, Event, EventRegistration, EventCategory
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
    return jsonify({'status': 'healthy', 'service': 'event-service'}), 200

@app.route('/events', methods=['GET'])
def get_events():
    try:
        # Optional query parameters for filtering
        category_id = request.args.get('category_id', type=int)
        status = request.args.get('status')
        
        # Base query
        query = Event.query
        
        # Apply filters if provided
        if category_id:
            query = query.filter_by(category_id=category_id)
        if status:
            query = query.filter_by(status=status)
            
        events = query.all()
        return jsonify([event.to_dict() for event in events]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    try:
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        return jsonify(event.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/events', methods=['POST'])
def create_event():
    try:
        data = request.json
        
        # Basic validation
        required_fields = ['title', 'description', 'start_date', 'end_date', 'category_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new event
        new_event = Event(
            title=data['title'],
            description=data['description'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            location=data.get('location', ''),
            capacity=data.get('capacity'),
            price=data.get('price', 0.0),
            category_id=data['category_id'],
            organizer_id=data.get('organizer_id'),
            status=data.get('status', 'scheduled')
        )
        
        db.session.add(new_event)
        db.session.commit()
        
        # Publish event creation event to Kafka
        event_created = {
            'event_type': 'event_created',
            'event_id': new_event.event_id,
            'title': new_event.title
        }
        producer.produce(
            'event-events', 
            key=str(new_event.event_id), 
            value=json.dumps(event_created),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(new_event.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    try:
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        data = request.json
        
        # Update event fields
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'start_date' in data:
            event.start_date = data['start_date']
        if 'end_date' in data:
            event.end_date = data['end_date']
        if 'location' in data:
            event.location = data['location']
        if 'capacity' in data:
            event.capacity = data['capacity']
        if 'price' in data:
            event.price = data['price']
        if 'category_id' in data:
            event.category_id = data['category_id']
        if 'status' in data:
            event.status = data['status']
        
        db.session.commit()
        
        # Publish event update event to Kafka
        event_updated = {
            'event_type': 'event_updated',
            'event_id': event.event_id,
            'title': event.title
        }
        producer.produce(
            'event-events', 
            key=str(event.event_id), 
            value=json.dumps(event_updated),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(event.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    try:
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Instead of hard delete, update status to 'cancelled'
        event.status = 'cancelled'
        db.session.commit()
        
        # Publish event cancellation event to Kafka
        event_cancelled = {
            'event_type': 'event_cancelled',
            'event_id': event.event_id,
            'title': event.title
        }
        producer.produce(
            'event-events', 
            key=str(event.event_id), 
            value=json.dumps(event_cancelled),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify({'message': 'Event cancelled successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/categories', methods=['GET'])
def get_categories():
    try:
        categories = EventCategory.query.all()
        return jsonify([{
            'category_id': category.category_id,
            'name': category.name,
            'description': category.description
        } for category in categories]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/events/<int:event_id>/registrations', methods=['GET'])
def get_event_registrations(event_id):
    try:
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        registrations = EventRegistration.query.filter_by(event_id=event_id).all()
        return jsonify([reg.to_dict() for reg in registrations]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/events/<int:event_id>/register', methods=['POST'])
def register_for_event(event_id):
    try:
        data = request.json
        
        if not data.get('user_id'):
            return jsonify({'error': 'user_id is required'}), 400
        
        event = Event.query.get(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Check if user is already registered
        existing_reg = EventRegistration.query.filter_by(
            event_id=event_id, 
            user_id=data['user_id']
        ).first()
        
        if existing_reg:
            return jsonify({'error': 'User already registered for this event'}), 409
        
        # Check if event has capacity
        if event.capacity is not None:
            current_registrations = EventRegistration.query.filter_by(
                event_id=event_id,
                status='confirmed'
            ).count()
            
            if current_registrations >= event.capacity:
                return jsonify({'error': 'Event has reached maximum capacity'}), 400
        
        # Create registration
        registration = EventRegistration(
            event_id=event_id,
            user_id=data['user_id'],
            registration_date=data.get('registration_date'),
            status='confirmed',
            ticket_type=data.get('ticket_type', 'standard')
        )
        
        db.session.add(registration)
        db.session.commit()
        
        # Publish registration event to Kafka
        registration_created = {
            'event_type': 'registration_created',
            'registration_id': registration.registration_id,
            'event_id': event_id,
            'user_id': data['user_id']
        }
        producer.produce(
            'event-registrations', 
            key=str(registration.registration_id), 
            value=json.dumps(registration_created),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(registration.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        # Configure consumer
        consumer_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
            'group.id': 'event-service-group',
            'auto.offset.reset': 'earliest'
        }
        
        consumer = Consumer(consumer_config)
        
        # Subscribe to relevant topics
        consumer.subscribe(['user-events', 'payment-events', 'resource-events'])
        
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
                        handle_user_event(message_value)
                    elif topic == 'payment-events':
                        handle_payment_event(message_value)
                    elif topic == 'resource-events':
                        handle_resource_event(message_value)
                    
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

def handle_user_event(message_data):
    """Handle user-related events"""
    try:
        event_type = message_data.get('event_type')
        user_id = message_data.get('user_id')
        
        if not event_type or not user_id:
            print("Missing event_type or user_id in message")
            return
        
        with app.app_context():
            # Handle user deletion or deactivation
            if event_type == 'user_deleted' or event_type == 'user_deactivated':
                # Find all event registrations for this user
                registrations = EventRegistration.query.filter_by(user_id=user_id).all()
                
                for registration in registrations:
                    # Update registration status based on event type
                    if event_type == 'user_deleted':
                        # Either delete the registration or mark as cancelled
                        db.session.delete(registration)
                    else:  # user_deactivated
                        registration.status = 'suspended'
                        db.session.add(registration)
                
                db.session.commit()
                print(f"Updated registrations for {event_type} event for user {user_id}")
                
            # You can handle other user events as needed
    except Exception as e:
        print(f"Error handling user event: {e}")
        with app.app_context():
            db.session.rollback()

def handle_payment_event(message_data):
    """Handle payment-related events"""
    try:
        event_type = message_data.get('event_type')
        reference_type = message_data.get('reference_type')
        reference_id = message_data.get('reference_id')
        
        # Only process event-related payments
        if reference_type != 'event':
            return
            
        if not event_type or not reference_id:
            print("Missing event_type or reference_id in payment message")
            return
        
        with app.app_context():
            # Handle payment completion
            if event_type == 'payment_completed':
                # Find the event registration
                registration = EventRegistration.query.filter_by(registration_id=reference_id).first()
                
                if not registration:
                    print(f"Registration not found for payment completion: {reference_id}")
                    return
                
                # Update registration status
                registration.status = 'confirmed'
                registration.payment_status = 'paid'
                db.session.add(registration)
                db.session.commit()
                print(f"Updated registration {reference_id} to confirmed after payment")
            
            # Handle payment refund
            elif event_type == 'payment_refunded':
                # Find the event registration
                registration = EventRegistration.query.filter_by(registration_id=reference_id).first()
                
                if not registration:
                    print(f"Registration not found for payment refund: {reference_id}")
                    return
                
                # Update registration status
                registration.status = 'refunded'
                registration.payment_status = 'refunded'
                db.session.add(registration)
                db.session.commit()
                print(f"Updated registration {reference_id} to refunded")
                
    except Exception as e:
        print(f"Error handling payment event: {e}")
        with app.app_context():
            db.session.rollback()

def handle_resource_event(message_data):
    """Handle resource-related events"""
    try:
        event_type = message_data.get('event_type')
        resource_id = message_data.get('resource_id')
        
        if not event_type or not resource_id:
            print("Missing event_type or resource_id in resource message")
            return
            
        with app.app_context():
            # If a resource becomes unavailable, update related events
            if event_type == 'resource_unavailable' or event_type == 'resource_maintenance':
                # Find events using this resource
                events = Event.query.filter_by(location=f"resource:{resource_id}").all()
                
                for event in events:
                    # Add a note about resource unavailability
                    notes = event.description or ""
                    notes += f"\n\nNOTE: The resource for this event is currently unavailable. Status will be updated."
                    event.description = notes
                    
                    # Optionally change event status
                    if event_type == 'resource_unavailable':
                        event.status = 'pending_resource'
                    
                    db.session.add(event)
                
                db.session.commit()
                print(f"Updated events for {event_type} on resource {resource_id}")
                
    except Exception as e:
        print(f"Error handling resource event: {e}")
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
    
    app.run(host='0.0.0.0', port=5002) 