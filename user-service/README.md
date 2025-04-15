# User Management Service

A microservice for managing user accounts within the Style Flow platform.

## Features

- User registration and management
- RESTful API for CRUD operations
- Kafka integration for event-driven communication
- PostgreSQL database for data persistence
- Health check endpoint

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/users` | GET | Get all users |
| `/users/<user_id>` | GET | Get user by ID |
| `/users` | POST | Create a new user |
| `/users/<user_id>` | PUT | Update an existing user |
| `/users/<user_id>` | DELETE | Delete a user (soft delete) |

## Kafka Topics

The service publishes to the following Kafka topics:
- `user.created` - Published when a new user is created
- `user.updated` - Published when a user is updated
- `user.deleted` - Published when a user is deleted
- `auth.user.created` - Published to notify auth service about new user

The service subscribes to:
- `auth.user.registered` - Handles user registrations from the auth service

## Database Schema

The User model includes:
- `id` - Primary key
- `username` - Unique username
- `email` - Unique email address
- `password` - Password (should be hashed in production)
- `first_name` - User's first name
- `last_name` - User's last name
- `phone` - Optional phone number
- `role` - User role (default: "user")
- `created_at` - Timestamp when the user was created
- `updated_at` - Timestamp when the user was last updated
- `is_active` - Flag indicating if the user is active

## Setup and Installation

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Set up environment variables:
```
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

3. Run the service:
```
python app.py
```

Or with Gunicorn:
```
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

## Testing

Run tests with pytest:
```
pytest
``` 