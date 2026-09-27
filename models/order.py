"""
Order and OrderItem models.
"""

from datetime import datetime
from extensions import db


class Order(db.Model):
    __tablename__ = 'orders'

    # Status constants
    STATUS_PENDING           = 'pending'
    STATUS_CONFIRMED         = 'confirmed'
    STATUS_PROCESSING        = 'processing'
    STATUS_SHIPPED           = 'shipped'
    STATUS_DELIVERED         = 'delivered'
    STATUS_CANCELLED         = 'cancelled'
    STATUS_REFUNDED          = 'refunded'
    STATUS_RETURN_REQUESTED  = 'return_requested'
    STATUS_RETURNED          = 'returned'

    id              = db.Column(db.Integer, primary_key=True)
    order_number    = db.Column(db.String(32), unique=True, nullable=False, index=True)

    # Customer info (denormalised so it survives user deletion)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    first_name      = db.Column(db.String(64), nullable=False)
    last_name       = db.Column(db.String(64), nullable=False)
    email           = db.Column(db.String(120), nullable=False)
    phone           = db.Column(db.String(32))

    # Shipping address
    address_line1   = db.Column(db.String(256), nullable=False)
    address_line2   = db.Column(db.String(256))
    city            = db.Column(db.String(64), nullable=False)
    state           = db.Column(db.String(64))
    postal_code     = db.Column(db.String(16), nullable=False)
    country         = db.Column(db.String(64), nullable=False, default='India')

    # Financials
    subtotal        = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_cost   = db.Column(db.Numeric(10, 2), default=0)
    tax             = db.Column(db.Numeric(10, 2), default=0)
    total           = db.Column(db.Numeric(10, 2), nullable=False)

    # Payment
    payment_status  = db.Column(db.String(32), default='pending', nullable=False)
    razorpay_order_id   = db.Column(db.String(128))
    razorpay_payment_id = db.Column(db.String(128))

    # Status & notes
    status          = db.Column(db.String(32), default=STATUS_PENDING, nullable=False)
    notes           = db.Column(db.Text)
    tracking_number = db.Column(db.String(64))
    tracking_status = db.Column(db.String(64))           # human-readable tracking status
    delivered_at    = db.Column(db.DateTime, nullable=True)   # when order was delivered
    tracking_events = db.Column(db.Text)                  # JSON list of tracking events
    estimated_delivery = db.Column(db.DateTime)

    # Timestamps
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy='dynamic',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order {self.order_number}>'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def full_address(self):
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts += [self.city, self.state, self.postal_code, self.country]
        return ', '.join(p for p in parts if p)

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items)

    @staticmethod
    def generate_order_number():
        import uuid, time
        return f'FB-{int(time.time())}-{str(uuid.uuid4())[:4].upper()}'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id          = db.Column(db.Integer, primary_key=True)
    order_id    = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)

    # Snapshot of product at purchase time
    product_name  = db.Column(db.String(120), nullable=False)
    product_image = db.Column(db.String(256))
    price         = db.Column(db.Numeric(10, 2), nullable=False)
    quantity      = db.Column(db.Integer, nullable=False, default=1)

    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'

    @property
    def subtotal(self):
        return self.price * self.quantity


class OrderTracking(db.Model):
    """
    Event log for an order's journey.
    Each row = one tracking event (status change, location update, courier scan).
    Admin adds these; customer sees them as a timeline.
    """
    __tablename__ = 'order_tracking'

    # All possible status values (superset of Order.STATUS_*)
    STATUS_PENDING      = 'pending'
    STATUS_CONFIRMED    = 'confirmed'
    STATUS_PROCESSING   = 'processing'
    STATUS_PACKED       = 'packed'
    STATUS_HANDED_TO_COURIER = 'handed_to_courier'
    STATUS_IN_TRANSIT   = 'in_transit'
    STATUS_OUT_FOR_DELIVERY = 'out_for_delivery'
    STATUS_DELIVERED    = 'delivered'
    STATUS_ATTEMPTED    = 'delivery_attempted'
    STATUS_EXCEPTION    = 'exception'
    STATUS_RETURN_REQUESTED = 'return_requested'
    STATUS_RETURNED         = 'returned'

    STATUS_LABELS = {
        'pending':            'Order Placed',
        'confirmed':          'Order Confirmed',
        'processing':         'Being Prepared',
        'packed':             'Packed & Ready',
        'handed_to_courier':  'Handed to Courier',
        'in_transit':         'In Transit',
        'out_for_delivery':   'Out for Delivery',
        'delivered':          'Delivered',
        'delivery_attempted': 'Delivery Attempted',
        'exception':          'Shipment Exception',
        'returned':           'Returned to Seller',
    }

    STATUS_ICONS = {
        'pending':            '🛒',
        'confirmed':          '✅',
        'processing':         '⚙️',
        'packed':             '📦',
        'handed_to_courier':  '🤝',
        'in_transit':         '🚀',
        'out_for_delivery':   '🚚',
        'delivered':          '🎉',
        'delivery_attempted': '🔔',
        'exception':          '⚠️',
        'returned':           '↩️',
    }

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)

    status     = db.Column(db.String(40), nullable=False)
    location   = db.Column(db.String(200))    # e.g. "Mumbai Hub", "Delhi Warehouse"
    message    = db.Column(db.Text)           # e.g. "Package scanned at sorting facility"
    is_public  = db.Column(db.Boolean, default=True)   # admin-only events can be hidden
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # which admin added
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order   = db.relationship('Order',
                              backref=db.backref('tracking_events_log',
                                                 lazy='dynamic',
                                                 order_by='OrderTracking.timestamp.desc()'))
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def label(self):
        return self.STATUS_LABELS.get(self.status, self.status.replace('_', ' ').title())

    @property
    def icon(self):
        return self.STATUS_ICONS.get(self.status, '📍')

    @classmethod
    def log(cls, order_id, status, message='', location='', created_by=None, timestamp=None):
        """Helper to add a tracking event and flush to DB."""
        event = cls(
            order_id=order_id,
            status=status,
            message=message,
            location=location,
            created_by=created_by,
            timestamp=timestamp or datetime.utcnow(),
        )
        db.session.add(event)
        return event
