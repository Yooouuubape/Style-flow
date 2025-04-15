from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class Event(db.Model):
    __tablename__ = 'events'
    
    event_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(255))
    capacity = db.Column(db.Integer)
    price = db.Column(db.Float, default=0.0)
    category_id = db.Column(db.Integer, db.ForeignKey('event_categories.category_id'))
    organizer_id = db.Column(db.Integer)
    status = db.Column(db.String(50), default='scheduled')  # scheduled, active, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    registrations = db.relationship('EventRegistration', backref='event', lazy=True)
    
    def __repr__(self):
        return f'<Event {self.title}>'
        
    def to_dict(self):
        """Convert Event object to dictionary for serialization"""
        return {
            'event_id': self.event_id,
            'title': self.title,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'location': self.location,
            'capacity': self.capacity,
            'price': self.price,
            'category_id': self.category_id,
            'organizer_id': self.organizer_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class EventRegistration(db.Model):
    __tablename__ = 'event_registrations'
    
    registration_id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')  # pending, confirmed, cancelled
    payment_status = db.Column(db.String(50), default='unpaid')  # unpaid, paid, refunded
    ticket_type = db.Column(db.String(50), default='standard')  # standard, vip, early_bird
    metadata = db.Column(JSONB)
    
    def __repr__(self):
        return f'<EventRegistration {self.registration_id} for event {self.event_id}>'
        
    def to_dict(self):
        """Convert EventRegistration object to dictionary for serialization"""
        return {
            'registration_id': self.registration_id,
            'event_id': self.event_id,
            'user_id': self.user_id,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'status': self.status,
            'payment_status': self.payment_status,
            'ticket_type': self.ticket_type,
            'metadata': self.metadata
        }


class EventCategory(db.Model):
    __tablename__ = 'event_categories'
    
    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('event_categories.category_id'))
    
    # Relationships
    events = db.relationship('Event', backref='category', lazy=True)
    subcategories = db.relationship('EventCategory', backref=db.backref('parent', remote_side=[category_id]))
    
    def __repr__(self):
        return f'<EventCategory {self.name}>' 