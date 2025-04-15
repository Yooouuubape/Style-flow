import os
import json
import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import jwt
from datetime import datetime
from functools import wraps
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Environment variables for service URLs
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://auth:5000')
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://user:5001')
EVENT_SERVICE_URL = os.getenv('EVENT_SERVICE_URL', 'http://event:5002')
RESOURCE_SERVICE_URL = os.getenv('RESOURCE_SERVICE_URL', 'http://resource:5003')
CLIENT_SERVICE_URL = os.getenv('CLIENT_SERVICE_URL', 'http://client:5004')
PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://payment:5005')

# Kafka configuration
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
API_REQUEST_TOPIC = 'api.request'
API_RESPONSE_TOPIC = 'api.response'

# Helper functions
def validate_token(token):
    """Validate JWT token with auth service"""
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/validate-token",
            json={"token": token},
            timeout=5
        )
        return response.json(), response.status_code
    except requests.RequestException as e:
        print(f"Error validating token: {e}")
        return {"valid": False, "message": "Error validating token"}, 500

def token_required(f):
    """Decorator for routes that require a valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Missing or invalid token'}), 401

        token = auth_header.split(' ')[1]
        
        # Validate token with auth service
        result, status_code = validate_token(token)
        
        if status_code != 200 or not result.get('valid', False):
            return jsonify({'message': result.get('message', 'Invalid token')}), status_code
        
        # Add user_id and role to kwargs for the route function
        kwargs['user_id'] = result.get('user_id')
        kwargs['role'] = result.get('role')
        
        return f(*args, **kwargs)
    
    return decorated

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

def proxy_request(target_url, method=None, headers=None, params=None, data=None):
    """Proxy request to a microservice"""
    if headers is None:
        headers = {}
    
    # Remove host header to avoid conflicts
    if 'Host' in headers:
        del headers['Host']
    
    method = method or request.method
    
    try:
        response = requests.request(
            method=method,
            url=target_url,
            headers=headers,
            params=params or request.args,
            json=data or (request.get_json() if request.is_json else None),
            timeout=10
        )
        
        return Response(
            response=response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except requests.RequestException as e:
        print(f"Error proxying request: {e}")
        return jsonify({'message': 'Error connecting to service'}), 503

# Routes for authentication service
@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    url = f"{AUTH_SERVICE_URL}/register"
    
    # Log API request
    request_data = request.get_json() if request.is_json else {}
    # Remove sensitive data like password
    if 'password' in request_data:
        request_data['password'] = '******'
    
    publish_event(API_REQUEST_TOPIC, 
                key={"path": "/api/auth/register", "method": "POST"},
                data={"timestamp": datetime.utcnow().isoformat(), "data": request_data})
    
    return proxy_request(url)

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    url = f"{AUTH_SERVICE_URL}/login"
    
    # Log API request (without sensitive data)
    request_data = request.get_json() if request.is_json else {}
    if 'password' in request_data:
        request_data['password'] = '******'
    
    publish_event(API_REQUEST_TOPIC, 
                key={"path": "/api/auth/login", "method": "POST"},
                data={"timestamp": datetime.utcnow().isoformat(), "data": request_data})
    
    return proxy_request(url)

@app.route('/api/auth/profile', methods=['GET'])
@token_required
def auth_profile(user_id, role):
    url = f"{AUTH_SERVICE_URL}/profile"
    return proxy_request(url, headers=request.headers)

@app.route('/api/auth/change-password', methods=['PUT'])
@token_required
def auth_change_password(user_id, role):
    url = f"{AUTH_SERVICE_URL}/change-password"
    return proxy_request(url, headers=request.headers)

# Routes for user service
@app.route('/api/users', methods=['GET'])
@token_required
def get_users(user_id, role):
    url = f"{USER_SERVICE_URL}/users"
    return proxy_request(url, headers=request.headers)

@app.route('/api/users/<user_id>', methods=['GET'])
@token_required
def get_user(user_id, role, user_id_param):
    url = f"{USER_SERVICE_URL}/users/{user_id_param}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/users/<user_id>', methods=['PUT'])
@token_required
def update_user(user_id, role, user_id_param):
    url = f"{USER_SERVICE_URL}/users/{user_id_param}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/users/<user_id>/password', methods=['PUT'])
@token_required
def change_user_password(user_id, role, user_id_param):
    url = f"{USER_SERVICE_URL}/users/{user_id_param}/password"
    return proxy_request(url, headers=request.headers)

@app.route('/api/users/<user_id>', methods=['DELETE'])
@token_required
def delete_user(user_id, role, user_id_param):
    url = f"{USER_SERVICE_URL}/users/{user_id_param}"
    return proxy_request(url, headers=request.headers)

# Routes for event service
@app.route('/api/events', methods=['GET'])
@token_required
def get_events(user_id, role):
    url = f"{EVENT_SERVICE_URL}/events"
    return proxy_request(url, headers=request.headers)

@app.route('/api/events/<event_id>', methods=['GET'])
@token_required
def get_event(user_id, role, event_id):
    url = f"{EVENT_SERVICE_URL}/events/{event_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/events', methods=['POST'])
@token_required
def create_event(user_id, role):
    url = f"{EVENT_SERVICE_URL}/events"
    return proxy_request(url, headers=request.headers)

@app.route('/api/events/<event_id>', methods=['PUT'])
@token_required
def update_event(user_id, role, event_id):
    url = f"{EVENT_SERVICE_URL}/events/{event_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/events/<event_id>/participants', methods=['POST'])
@token_required
def add_participant(user_id, role, event_id):
    url = f"{EVENT_SERVICE_URL}/events/{event_id}/participants"
    return proxy_request(url, headers=request.headers)

@app.route('/api/events/<event_id>', methods=['DELETE'])
@token_required
def delete_event(user_id, role, event_id):
    url = f"{EVENT_SERVICE_URL}/events/{event_id}"
    return proxy_request(url, headers=request.headers)

# Routes for resource service
@app.route('/api/resources', methods=['GET'])
@token_required
def get_resources(user_id, role):
    url = f"{RESOURCE_SERVICE_URL}/resources"
    return proxy_request(url, headers=request.headers)

@app.route('/api/resources/<resource_id>', methods=['GET'])
@token_required
def get_resource(user_id, role, resource_id):
    url = f"{RESOURCE_SERVICE_URL}/resources/{resource_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/resources', methods=['POST'])
@token_required
def create_resource(user_id, role):
    url = f"{RESOURCE_SERVICE_URL}/resources"
    return proxy_request(url, headers=request.headers)

@app.route('/api/resources/<resource_id>', methods=['PUT'])
@token_required
def update_resource(user_id, role, resource_id):
    url = f"{RESOURCE_SERVICE_URL}/resources/{resource_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/resources/<resource_id>', methods=['DELETE'])
@token_required
def delete_resource(user_id, role, resource_id):
    url = f"{RESOURCE_SERVICE_URL}/resources/{resource_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/resources/<resource_id>/availability', methods=['GET'])
@token_required
def check_availability(user_id, role, resource_id):
    url = f"{RESOURCE_SERVICE_URL}/resources/{resource_id}/availability"
    return proxy_request(url, headers=request.headers)

# Routes for client service
@app.route('/api/clients', methods=['GET'])
@token_required
def get_clients(user_id, role):
    url = f"{CLIENT_SERVICE_URL}/clients"
    return proxy_request(url, headers=request.headers)

@app.route('/api/clients/<client_id>', methods=['GET'])
@token_required
def get_client(user_id, role, client_id):
    url = f"{CLIENT_SERVICE_URL}/clients/{client_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/clients', methods=['POST'])
@token_required
def create_client(user_id, role):
    url = f"{CLIENT_SERVICE_URL}/clients"
    return proxy_request(url, headers=request.headers)

@app.route('/api/clients/<client_id>', methods=['PUT'])
@token_required
def update_client(user_id, role, client_id):
    url = f"{CLIENT_SERVICE_URL}/clients/{client_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/clients/<client_id>/interactions', methods=['POST'])
@token_required
def add_interaction(user_id, role, client_id):
    url = f"{CLIENT_SERVICE_URL}/clients/{client_id}/interactions"
    return proxy_request(url, headers=request.headers)

@app.route('/api/clients/<client_id>/interactions', methods=['GET'])
@token_required
def get_interactions(user_id, role, client_id):
    url = f"{CLIENT_SERVICE_URL}/clients/{client_id}/interactions"
    return proxy_request(url, headers=request.headers)

@app.route('/api/clients/<client_id>', methods=['DELETE'])
@token_required
def delete_client(user_id, role, client_id):
    url = f"{CLIENT_SERVICE_URL}/clients/{client_id}"
    return proxy_request(url, headers=request.headers)

# Routes for payment service
@app.route('/api/payments', methods=['GET'])
@token_required
def get_payments(user_id, role):
    url = f"{PAYMENT_SERVICE_URL}/payments"
    return proxy_request(url, headers=request.headers)

@app.route('/api/payments/<payment_id>', methods=['GET'])
@token_required
def get_payment(user_id, role, payment_id):
    url = f"{PAYMENT_SERVICE_URL}/payments/{payment_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/payments', methods=['POST'])
@token_required
def create_payment(user_id, role):
    url = f"{PAYMENT_SERVICE_URL}/payments"
    return proxy_request(url, headers=request.headers)

@app.route('/api/payments/<payment_id>/process', methods=['POST'])
@token_required
def process_payment(user_id, role, payment_id):
    url = f"{PAYMENT_SERVICE_URL}/payments/{payment_id}/process"
    return proxy_request(url, headers=request.headers)

@app.route('/api/payments/<payment_id>', methods=['PUT'])
@token_required
def update_payment(user_id, role, payment_id):
    url = f"{PAYMENT_SERVICE_URL}/payments/{payment_id}"
    return proxy_request(url, headers=request.headers)

@app.route('/api/payments/<payment_id>/refund', methods=['POST'])
@token_required
def refund_payment(user_id, role, payment_id):
    url = f"{PAYMENT_SERVICE_URL}/payments/{payment_id}/refund"
    return proxy_request(url, headers=request.headers)

# Health check endpoint
@app.route('/api/health-check', methods=['GET'])
def health_check():
    services = {
        'auth': AUTH_SERVICE_URL,
        'user': USER_SERVICE_URL,
        'event': EVENT_SERVICE_URL,
        'resource': RESOURCE_SERVICE_URL,
        'client': CLIENT_SERVICE_URL,
        'payment': PAYMENT_SERVICE_URL
    }
    
    results = {}
    for name, url in services.items():
        try:
            response = requests.get(f"{url}/health", timeout=2)
            results[name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'code': response.status_code
            }
        except requests.RequestException:
            results[name] = {'status': 'unreachable', 'code': None}
    
    overall_status = 'healthy' if all(r['status'] == 'healthy' for r in results.values()) else 'degraded'
    
    return jsonify({
        'status': overall_status,
        'message': 'Masters Pro Scheduling API Gateway',
        'services': results
    }), 200

def start_kafka_consumer():
    """Start a Kafka consumer to listen for events from other services"""
    try:
        consumer = KafkaConsumer(
            API_RESPONSE_TOPIC,
            bootstrap_servers=kafka_bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda v: json.loads(v.decode('utf-8')),
            group_id='gateway-service-group',
            auto_offset_reset='latest'
        )
        
        # Process messages
        for message in consumer:
            print(f"Received message: {message.value} from topic {message.topic}")
            
            # Gateway can use this to update cache, metrics, or trigger actions
            # For example, invalidate cache when a resource is updated
    except Exception as e:
        print(f"Error in Kafka consumer: {e}")

# Start Kafka consumer in a separate thread
consumer_thread = Thread(target=start_kafka_consumer)
consumer_thread.daemon = True

if __name__ == '__main__':
    # Start Kafka consumer
    consumer_thread.start()
    
    # Run Flask app
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False) 