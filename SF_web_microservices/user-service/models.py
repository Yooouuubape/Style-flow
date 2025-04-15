from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    full_name = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        """Convert User object to dictionary for serialization"""
        return {
            'user_id': self.user_id,
            'email': self.email,
            'full_name': self.full_name,
            'role_id': self.role_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    
    activity_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    action_type = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    meta_data = db.Column(JSONB)
    
    def __repr__(self):
        return f'<UserActivity {self.action_type} by user {self.user_id}>'

class UserIntegration(db.Model):
    __tablename__ = 'user_integrations'
    
    integration_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    service_name = db.Column(db.String(50), nullable=False)
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    external_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserIntegration {self.service_name} for user {self.user_id}>' 