import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from confluent_kafka import Producer, Consumer
from models import db, Payment, PaymentMethod, Transaction
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
    return jsonify({'status': 'healthy', 'service': 'payment-service'}), 200

@app.route('/payments', methods=['GET'])
def get_payments():
    try:
        # Optional query parameters for filtering
        user_id = request.args.get('user_id', type=int)
        status = request.args.get('status')
        
        # Base query
        query = Payment.query
        
        # Apply filters if provided
        if user_id:
            query = query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
            
        payments = query.all()
        return jsonify([payment.to_dict() for payment in payments]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payments/<int:payment_id>', methods=['GET'])
def get_payment(payment_id):
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        return jsonify(payment.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payments', methods=['POST'])
def create_payment():
    try:
        data = request.json
        
        # Basic validation
        required_fields = ['user_id', 'amount', 'payment_method_id', 'reference_type', 'reference_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create payment record
        payment = Payment(
            user_id=data['user_id'],
            amount=data['amount'],
            currency=data.get('currency', 'USD'),
            payment_method_id=data['payment_method_id'],
            status='pending',
            reference_type=data['reference_type'],  # e.g., 'order', 'subscription', 'event'
            reference_id=data['reference_id'],
            description=data.get('description', '')
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # Create transaction record
        transaction = Transaction(
            payment_id=payment.payment_id,
            transaction_type='payment',
            amount=data['amount'],
            status='pending',
            processor_reference=str(uuid.uuid4())  # Mock external reference
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # In a real system, you would process the payment with a payment gateway here
        # For this example, we'll simulate success
        
        # Update transaction and payment status
        transaction.status = 'completed'
        payment.status = 'completed'
        payment.processed_at = datetime.utcnow()
        db.session.commit()
        
        # Publish payment event to Kafka
        payment_completed = {
            'event_type': 'payment_completed',
            'payment_id': payment.payment_id,
            'reference_type': payment.reference_type,
            'reference_id': payment.reference_id,
            'amount': float(payment.amount),
            'currency': payment.currency,
            'user_id': payment.user_id
        }
        producer.produce(
            'payment-events', 
            key=str(payment.payment_id), 
            value=json.dumps(payment_completed),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify(payment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/payment-methods', methods=['GET'])
def get_payment_methods():
    try:
        user_id = request.args.get('user_id', type=int)
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
            
        payment_methods = PaymentMethod.query.filter_by(user_id=user_id).all()
        return jsonify([pm.to_dict() for pm in payment_methods]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payment-methods', methods=['POST'])
def add_payment_method():
    try:
        data = request.json
        
        # Basic validation
        required_fields = ['user_id', 'method_type', 'details']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
                
        # Create new payment method
        payment_method = PaymentMethod(
            user_id=data['user_id'],
            method_type=data['method_type'],  # e.g., 'credit_card', 'paypal', 'bank_account'
            details=data['details'],  # Should be encrypted in production
            is_default=data.get('is_default', False),
            nickname=data.get('nickname', '')
        )
        
        # If this is marked as default, unset any existing defaults
        if payment_method.is_default:
            existing_defaults = PaymentMethod.query.filter_by(
                user_id=data['user_id'], 
                is_default=True
            ).all()
            for pm in existing_defaults:
                pm.is_default = False
        
        db.session.add(payment_method)
        db.session.commit()
        
        return jsonify(payment_method.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/payments/<int:payment_id>/refund', methods=['POST'])
def refund_payment(payment_id):
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
            
        # Check if payment is already refunded
        if payment.status == 'refunded':
            return jsonify({'error': 'Payment already refunded'}), 400
            
        # Check if payment is in a state that can be refunded
        if payment.status != 'completed':
            return jsonify({'error': 'Payment cannot be refunded in its current state'}), 400
            
        data = request.json
        refund_amount = data.get('amount', payment.amount)  # Default to full refund
        
        if float(refund_amount) > float(payment.amount):
            return jsonify({'error': 'Refund amount exceeds payment amount'}), 400
        
        # Create refund transaction
        refund_transaction = Transaction(
            payment_id=payment.payment_id,
            transaction_type='refund',
            amount=refund_amount,
            status='completed',
            processor_reference=str(uuid.uuid4())  # Mock external reference
        )
        
        db.session.add(refund_transaction)
        
        # Update payment status
        payment.status = 'refunded'
        db.session.commit()
        
        # Publish refund event to Kafka
        refund_completed = {
            'event_type': 'payment_refunded',
            'payment_id': payment.payment_id,
            'reference_type': payment.reference_type,
            'reference_id': payment.reference_id,
            'amount': float(refund_amount),
            'currency': payment.currency,
            'user_id': payment.user_id
        }
        producer.produce(
            'payment-events', 
            key=str(payment.payment_id), 
            value=json.dumps(refund_completed),
            callback=delivery_report
        )
        producer.flush()
        
        return jsonify({'message': 'Payment refunded successfully', 'payment': payment.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/transactions', methods=['GET'])
def get_transactions():
    try:
        payment_id = request.args.get('payment_id', type=int)
        
        if not payment_id:
            return jsonify({'error': 'payment_id is required'}), 400
            
        transactions = Transaction.query.filter_by(payment_id=payment_id).all()
        return jsonify([tx.to_dict() for tx in transactions]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        # Configure consumer
        consumer_config = {
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
            'group.id': 'payment-service-group',
            'auto.offset.reset': 'earliest'
        }
        
        consumer = Consumer(consumer_config)
        
        # Subscribe to relevant topics
        consumer.subscribe(['user-events', 'event-events', 'resource-events', 'client-events'])
        
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
                    elif topic == 'resource-events':
                        handle_resource_message(message_value)
                    elif topic == 'client-events':
                        handle_client_message(message_value)
                    
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
            # Handle user deletion
            if event_type == 'user_deleted':
                # Find payment methods for this user and delete them
                payment_methods = PaymentMethod.query.filter_by(user_id=user_id).all()
                
                for method in payment_methods:
                    db.session.delete(method)
                
                db.session.commit()
                print(f"Deleted all payment methods for user {user_id}")
                
            # Handle user deactivation
            elif event_type == 'user_deactivated':
                # Find pending payments and cancel them
                pending_payments = Payment.query.filter_by(
                    user_id=user_id, 
                    status='pending'
                ).all()
                
                for payment in pending_payments:
                    payment.status = 'cancelled'
                    db.session.add(payment)
                    
                    # Add a transaction record for the cancellation
                    transaction = Transaction(
                        payment_id=payment.payment_id,
                        transaction_type='cancel',
                        amount=payment.amount,
                        status='completed',
                        processor_reference=str(uuid.uuid4())
                    )
                    db.session.add(transaction)
                
                db.session.commit()
                print(f"Cancelled pending payments for deactivated user {user_id}")
                
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
            # Handle event cancellation
            if event_type == 'event_cancelled':
                # Find payments related to this event
                payments = Payment.query.filter_by(
                    reference_type='event',
                    reference_id=event_id
                ).all()
                
                for payment in payments:
                    # For completed payments, process a refund
                    if payment.status == 'completed':
                        # Create refund transaction
                        refund_transaction = Transaction(
                            payment_id=payment.payment_id,
                            transaction_type='refund',
                            amount=payment.amount,
                            status='completed',
                            processor_reference=str(uuid.uuid4())
                        )
                        
                        db.session.add(refund_transaction)
                        
                        # Update payment status
                        payment.status = 'refunded'
                        db.session.add(payment)
                        
                        # Publish refund event to Kafka
                        refund_completed = {
                            'event_type': 'payment_refunded',
                            'payment_id': payment.payment_id,
                            'reference_type': payment.reference_type,
                            'reference_id': payment.reference_id,
                            'amount': float(payment.amount),
                            'currency': payment.currency,
                            'user_id': payment.user_id
                        }
                        producer.produce(
                            'payment-events', 
                            key=str(payment.payment_id), 
                            value=json.dumps(refund_completed),
                            callback=delivery_report
                        )
                        producer.flush()
                    
                    # For pending payments, just cancel them
                    elif payment.status == 'pending':
                        payment.status = 'cancelled'
                        db.session.add(payment)
                
                db.session.commit()
                print(f"Processed refunds/cancellations for event {event_id}")
                
    except Exception as e:
        print(f"Error handling event message: {e}")
        with app.app_context():
            db.session.rollback()

def handle_resource_message(message_data):
    """Handle resource-related messages"""
    try:
        event_type = message_data.get('event_type')
        resource_id = message_data.get('resource_id')
        
        if not event_type or not resource_id:
            print("Missing event_type or resource_id in message")
            return
        
        with app.app_context():
            # Handle resource unavailability
            if event_type in ['resource_unavailable', 'resource_maintenance']:
                # Find payments related to this resource that are pending
                payments = Payment.query.filter_by(
                    reference_type='resource',
                    reference_id=resource_id,
                    status='pending'
                ).all()
                
                for payment in payments:
                    # Cancel pending payments
                    payment.status = 'cancelled'
                    db.session.add(payment)
                    
                    # Add transaction record
                    transaction = Transaction(
                        payment_id=payment.payment_id,
                        transaction_type='cancel',
                        amount=payment.amount,
                        status='completed',
                        processor_reference=str(uuid.uuid4())
                    )
                    db.session.add(transaction)
                
                db.session.commit()
                print(f"Cancelled pending payments for unavailable resource {resource_id}")
                
    except Exception as e:
        print(f"Error handling resource message: {e}")
        with app.app_context():
            db.session.rollback()

def handle_client_message(message_data):
    """Handle client-related messages"""
    try:
        event_type = message_data.get('event_type')
        client_id = message_data.get('client_id')
        
        if not event_type or not client_id:
            print("Missing event_type or client_id in message")
            return
        
        # This service might not need to do much with client events
        # but we can log them for future reference
        print(f"Received client event: {event_type} for client {client_id}")
                
    except Exception as e:
        print(f"Error handling client message: {e}")

# Start Kafka consumer in a separate thread
consumer_thread = Thread(target=start_kafka_consumer)
consumer_thread.daemon = True

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Start Kafka consumer thread
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5005) 