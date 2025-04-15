from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class Resource(db.Model):
    __tablename__ = 'resources'
    
    resource_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    resource_type_id = db.Column(db.Integer, db.ForeignKey('resource_types.resource_type_id'))
    status = db.Column(db.String(50), default='available')  # available, in_use, maintenance, retired
    location = db.Column(db.String(255))
    capacity = db.Column(db.Integer)
    cost_per_hour = db.Column(db.Float, default=0.0)
    owner_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = db.Column(JSONB)
    
    # Relationships
    allocations = db.relationship('ResourceAllocation', backref='resource', lazy=True)
    
    def __repr__(self):
        return f'<Resource {self.name}>'
        
    def to_dict(self):
        """Convert Resource object to dictionary for serialization"""
        return {
            'resource_id': self.resource_id,
            'name': self.name,
            'description': self.description,
            'resource_type_id': self.resource_type_id,
            'status': self.status,
            'location': self.location,
            'capacity': self.capacity,
            'cost_per_hour': self.cost_per_hour,
            'owner_id': self.owner_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata
        }


class ResourceType(db.Model):
    __tablename__ = 'resource_types'
    
    resource_type_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    resources = db.relationship('Resource', backref='resource_type', lazy=True)
    
    def __repr__(self):
        return f'<ResourceType {self.name}>'


class ResourceAllocation(db.Model):
    __tablename__ = 'resource_allocations'
    
    allocation_id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.resource_id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')  # pending, confirmed, cancelled, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = db.Column(JSONB)
    
    def __repr__(self):
        return f'<ResourceAllocation {self.allocation_id} for resource {self.resource_id}>'
        
    def to_dict(self):
        """Convert ResourceAllocation object to dictionary for serialization"""
        return {
            'allocation_id': self.allocation_id,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'purpose': self.purpose,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata
        } 