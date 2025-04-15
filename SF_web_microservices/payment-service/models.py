from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class Payment(db.Model):
    __tablename__ = 'payments'
    
    payment_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_methods.payment_method_id'))
    status = db.Column(db.String(50), default='pending')  # pending, completed, failed, refunded
    reference_type = db.Column(db.String(50), nullable=False)  # order, subscription, event
    reference_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='payment', lazy=True)
    
    def __repr__(self):
        return f'<Payment {self.payment_id} for {self.reference_type} {self.reference_id}>'
        
    def to_dict(self):
        """Convert Payment object to dictionary for serialization"""
        return {
            'payment_id': self.payment_id,
            'user_id': self.user_id,
            'amount': str(self.amount),
            'currency': self.currency,
            'payment_method_id': self.payment_method_id,
            'status': self.status,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }


class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    payment_method_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    method_type = db.Column(db.String(50), nullable=False)  # credit_card, paypal, bank_account
    details = db.Column(JSONB, nullable=False)  # Stored securely in production
    is_default = db.Column(db.Boolean, default=False)
    nickname = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    payments = db.relationship('Payment', backref='payment_method', lazy=True)
    
    def __repr__(self):
        return f'<PaymentMethod {self.payment_method_id} for user {self.user_id}>'
        
    def to_dict(self):
        """Convert PaymentMethod object to dictionary for serialization"""
        # Mask sensitive data
        masked_details = {}
        if self.method_type == 'credit_card' and 'card_number' in self.details:
            masked_details = self.details.copy()
            masked_details['card_number'] = '*' * 12 + self.details['card_number'][-4:]
        else:
            masked_details = self.details
            
        return {
            'payment_method_id': self.payment_method_id,
            'user_id': self.user_id,
            'method_type': self.method_type,
            'details': masked_details,
            'is_default': self.is_default,
            'nickname': self.nickname,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    transaction_id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.payment_id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # payment, refund, chargeback
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), nullable=False)  # pending, completed, failed
    processor_reference = db.Column(db.String(255))  # Reference from payment processor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(JSONB)
    
    def __repr__(self):
        return f'<Transaction {self.transaction_id} for payment {self.payment_id}>'
        
    def to_dict(self):
        """Convert Transaction object to dictionary for serialization"""
        return {
            'transaction_id': self.transaction_id,
            'payment_id': self.payment_id,
            'transaction_type': self.transaction_type,
            'amount': str(self.amount),
            'status': self.status,
            'processor_reference': self.processor_reference,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'metadata': self.metadata
        } 