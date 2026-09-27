"""
In-platform buyer ↔ seller messaging.
Thread = one conversation between a customer and a company (optionally linked to a product).
Message = individual message within a thread.
"""
from datetime import datetime
from extensions import db


class MessageThread(db.Model):
    __tablename__ = 'message_threads'

    id          = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)  # optional context

    subject     = db.Column(db.String(200), nullable=False)
    is_open     = db.Column(db.Boolean, default=True)

    # Unread counts
    unread_customer = db.Column(db.Integer, default=0)  # messages seller sent that customer hasn't read
    unread_seller   = db.Column(db.Integer, default=0)  # messages customer sent that seller hasn't read

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('User',    foreign_keys=[customer_id],
                               backref=db.backref('message_threads', lazy='dynamic'))
    company  = db.relationship('Company', backref=db.backref('message_threads', lazy='dynamic'))
    product  = db.relationship('Product', backref=db.backref('message_threads', lazy='dynamic'))
    messages = db.relationship('Message', backref='thread', lazy='dynamic',
                               order_by='Message.created_at', cascade='all, delete-orphan')

    @property
    def last_message(self):
        return self.messages.order_by(Message.created_at.desc()).first()

    @property
    def message_count(self):
        return self.messages.count()


class Message(db.Model):
    __tablename__ = 'messages'

    id        = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('message_threads.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    body      = db.Column(db.Text, nullable=False)
    is_read   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id],
                             backref=db.backref('sent_messages', lazy='dynamic'))
