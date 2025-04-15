import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer
from models import db, Resource, ResourceType, ResourceAllocation
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
    return jsonify({'status': 'healthy', 'service': 'resource-service'}), 200

@app.route('/resources', methods=['GET'])
def get_resources():
    try:
        # Optional query parameters for filtering
        resource_type_id = request.args.get('type_id', type=int)
        status = request.args.get('status')
        
        # Base query
        query = Resource.query
        
        # Apply filters if provided
        if resource_type_id:
            query = query.filter_by(resource_type_id=resource_type_id)
        if status:
            query = query.filter_by(status=status)
            
        resources = query.all()
        return jsonify([resource.to_dict() for resource in resources]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resources/<int:resource_id>', methods=['GET'])
def get_resource(resource_id):
    try:
        resource = Resource.query.get(resource_id)
        if not resource:
            return jsonify({'error': 'Resource not found'}), 404
        return jsonify(resource.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resources', methods=['POST'])
def create_resource():
    try:
        data = request.json
        
        # Basic validation
        required_fields = ['name', 'resource_type_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new resource
        new_resource = Resource(
            name=data['name'],
            description=data.get('description', ''),
            resource_type_id=data['resource_type_id'],
            status=data.get('status', 'available'),
            location=data.get('location', ''),
            capacity=data.get('capacity'),
            cost_per_hour=data.get('cost_per_hour', 0.0),
            owner_id=data.get('owner_id')
        )
        
        db.session.add(new_resource)
        db.session.commit()
        
        # Publish resource creation event to Kafka
        resource_created = {
            'event_type': 'resource_created',
            'resource_id': new_resource.resource_id,
            'name': new_resource.name
        }
        producer.produce(
            'resource-events', 
            key=str(new_resource.resource_id), 
            value=json.dumps(resource_created),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(new_resource.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/resources/<int:resource_id>', methods=['PUT'])
def update_resource(resource_id):
    try:
        resource = Resource.query.get(resource_id)
        if not resource:
            return jsonify({'error': 'Resource not found'}), 404
        
        data = request.json
        
        # Update resource fields
        if 'name' in data:
            resource.name = data['name']
        if 'description' in data:
            resource.description = data['description']
        if 'resource_type_id' in data:
            resource.resource_type_id = data['resource_type_id']
        if 'status' in data:
            resource.status = data['status']
        if 'location' in data:
            resource.location = data['location']
        if 'capacity' in data:
            resource.capacity = data['capacity']
        if 'cost_per_hour' in data:
            resource.cost_per_hour = data['cost_per_hour']
        
        db.session.commit()
        
        # Publish resource update event to Kafka
        resource_updated = {
            'event_type': 'resource_updated',
            'resource_id': resource.resource_id,
            'name': resource.name
        }
        producer.produce(
            'resource-events', 
            key=str(resource.resource_id), 
            value=json.dumps(resource_updated),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(resource.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/resource-types', methods=['GET'])
def get_resource_types():
    try:
        resource_types = ResourceType.query.all()
        return jsonify([{
            'resource_type_id': rt.resource_type_id,
            'name': rt.name,
            'description': rt.description
        } for rt in resource_types]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resources/<int:resource_id>/allocate', methods=['POST'])
def allocate_resource(resource_id):
    try:
        data = request.json
        
        # Basic validation
        required_fields = ['user_id', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        resource = Resource.query.get(resource_id)
        if not resource:
            return jsonify({'error': 'Resource not found'}), 404
        
        # Check if resource is available
        if resource.status != 'available':
            return jsonify({'error': 'Resource is not available for allocation'}), 400
        
        # Check for conflicting allocations
        conflicting_allocations = ResourceAllocation.query.filter_by(
            resource_id=resource_id,
            status='confirmed'
        ).filter(
            ((ResourceAllocation.start_time <= data['start_time']) & 
             (ResourceAllocation.end_time > data['start_time'])) |
            ((ResourceAllocation.start_time < data['end_time']) & 
             (ResourceAllocation.end_time >= data['end_time'])) |
            ((ResourceAllocation.start_time >= data['start_time']) & 
             (ResourceAllocation.end_time <= data['end_time']))
        ).count()
        
        if conflicting_allocations > 0:
            return jsonify({'error': 'Resource is already allocated during the requested time period'}), 409
        
        # Create allocation
        allocation = ResourceAllocation(
            resource_id=resource_id,
            user_id=data['user_id'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            purpose=data.get('purpose', ''),
            status='confirmed'
        )
        
        db.session.add(allocation)
        db.session.commit()
        
        # Publish allocation event to Kafka
        allocation_created = {
            'event_type': 'resource_allocated',
            'allocation_id': allocation.allocation_id,
            'resource_id': resource_id,
            'user_id': data['user_id']
        }
        producer.produce(
            'resource-allocations', 
            key=str(allocation.allocation_id), 
            value=json.dumps(allocation_created),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(allocation.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/allocations', methods=['GET'])
def get_allocations():
    try:
        # Optional query parameters for filtering
        resource_id = request.args.get('resource_id', type=int)
        user_id = request.args.get('user_id', type=int)
        status = request.args.get('status')
        
        # Base query
        query = ResourceAllocation.query
        
        # Apply filters if provided
        if resource_id:
            query = query.filter_by(resource_id=resource_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
            
        allocations = query.all()
        return jsonify([allocation.to_dict() for allocation in allocations]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        # Configure consumer
        consumer_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
            'group.id': 'resource-service-group',
            'auto.offset.reset': 'earliest'
        }
        
        consumer = Consumer(consumer_config)
        
        # Subscribe to relevant topics
        consumer.subscribe(['event-events', 'user-events', 'payment-events'])
        
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
                    if topic == 'event-events':
                        handle_event_message(message_value)
                    elif topic == 'user-events':
                        handle_user_message(message_value)
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

def handle_event_message(message_data):
    """Handle event-related messages"""
    try:
        event_type = message_data.get('event_type')
        event_id = message_data.get('event_id')
        
        if not event_type or not event_id:
            print("Missing event_type or event_id in message")
            return
        
        with app.app_context():
            # Handle event cancellation
            if event_type == 'event_cancelled':
                # Free up any resources allocated for this event
                allocations = ResourceAllocation.query.filter_by(
                    purpose=f"event:{event_id}"
                ).all()
                
                for allocation in allocations:
                    # Cancel the allocation
                    allocation.status = 'cancelled'
                    db.session.add(allocation)
                    
                    # Update resource status back to available
                    resource = Resource.query.get(allocation.resource_id)
                    if resource and resource.status == 'in_use':
                        resource.status = 'available'
                        db.session.add(resource)
                
                db.session.commit()
                print(f"Freed up resources for cancelled event {event_id}")
                
            # Handle event creation
            elif event_type == 'event_created':
                # Nothing to do here unless resources need to be pre-allocated
                pass
                
    except Exception as e:
        print(f"Error handling event message: {e}")
        with app.app_context():
            db.session.rollback()

def handle_user_message(message_data):
    """Handle user-related messages"""
    try:
        event_type = message_data.get('event_type')
        user_id = message_data.get('user_id')
        
        if not event_type or not user_id:
            print("Missing event_type or user_id in message")
            return
        
        with app.app_context():
            # Handle user deletion or deactivation
            if event_type == 'user_deleted' or event_type == 'user_deactivated':
                # Handle resource allocations for this user
                allocations = ResourceAllocation.query.filter_by(user_id=user_id).all()
                
                for allocation in allocations:
                    if event_type == 'user_deleted':
                        # Cancel the allocation
                        allocation.status = 'cancelled'
                        db.session.add(allocation)
                        
                        # Update resource status if currently in use
                        resource = Resource.query.get(allocation.resource_id)
                        if resource and resource.status == 'in_use':
                            resource.status = 'available'
                            db.session.add(resource)
                    else:  # user_deactivated
                        # Mark allocation as suspended
                        allocation.status = 'suspended'
                        db.session.add(allocation)
                
                db.session.commit()
                print(f"Updated allocations for {event_type} event for user {user_id}")
                
    except Exception as e:
        print(f"Error handling user message: {e}")
        with app.app_context():
            db.session.rollback()

def handle_payment_message(message_data):
    """Handle payment-related messages"""
    try:
        event_type = message_data.get('event_type')
        reference_type = message_data.get('reference_type')
        reference_id = message_data.get('reference_id')
        
        # Only process resource-related payments
        if reference_type != 'resource':
            return
            
        if not event_type or not reference_id:
            print("Missing event_type or reference_id in payment message")
            return
        
        with app.app_context():
            # Find the resource allocation
            allocation = ResourceAllocation.query.get(reference_id)
            
            if not allocation:
                print(f"Resource allocation not found for reference: {reference_id}")
                return
                
            # Handle payment completion
            if event_type == 'payment_completed':
                # Confirm the allocation
                allocation.status = 'confirmed'
                db.session.add(allocation)
                
                # Update resource status
                resource = Resource.query.get(allocation.resource_id)
                if resource:
                    resource.status = 'in_use'
                    db.session.add(resource)
                
                db.session.commit()
                print(f"Confirmed allocation {reference_id} after payment")
            
            # Handle payment refund
            elif event_type == 'payment_refunded':
                # Cancel the allocation
                allocation.status = 'cancelled'
                db.session.add(allocation)
                
                # Update resource status
                resource = Resource.query.get(allocation.resource_id)
                if resource and resource.status == 'in_use':
                    resource.status = 'available'
                    db.session.add(resource)
                
                db.session.commit()
                print(f"Cancelled allocation {reference_id} after refund")
                
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
    
    app.run(host='0.0.0.0', port=5003) 