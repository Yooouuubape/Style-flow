from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class Client(db.Model):
    __tablename__ = 'clients'
    
    client_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    company = db.Column(db.String(255))
    address = db.Column(db.Text)
    status = db.Column(db.String(50), default='active')  # active, inactive, potential, former
    source = db.Column(db.String(100))  # direct, referral, website, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text)
    
    # Relationships
    contacts = db.relationship('ClientContact', backref='client', lazy=True)
    activities = db.relationship('ClientActivity', backref='client', lazy=True)
    
    def __repr__(self):
        return f'<Client {self.name}>'
        
    def to_dict(self):
        """Convert Client object to dictionary for serialization"""
        return {
            'client_id': self.client_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'address': self.address,
            'status': self.status,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'notes': self.notes
        }


class ClientContact(db.Model):
    __tablename__ = 'client_contacts'
    
    contact_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    position = db.Column(db.String(100))
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<ClientContact {self.name} for client {self.client_id}>'
        
    def to_dict(self):
        """Convert ClientContact object to dictionary for serialization"""
        return {
            'contact_id': self.contact_id,
            'client_id': self.client_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'position': self.position,
            'is_primary': self.is_primary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'notes': self.notes
        }


class ClientActivity(db.Model):
    __tablename__ = 'client_activities'
    
    activity_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # call, email, meeting, contract, etc.
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer)  # The user who logged the activity
    metadata = db.Column(JSONB)
    
    def __repr__(self):
        return f'<ClientActivity {self.activity_type} for client {self.client_id}>'
        
    def to_dict(self):
        """Convert ClientActivity object to dictionary for serialization"""
        return {
            'activity_id': self.activity_id,
            'client_id': self.client_id,
            'activity_type': self.activity_type,
            'description': self.description,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'metadata': self.metadata
        } 