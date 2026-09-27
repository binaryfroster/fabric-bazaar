"""
Delivery Partner system.

DeliveryPartner — profile record for a delivery role user.
DeliveryAssignment — which delivery partner is assigned to which order.
"""
from datetime import datetime
from extensions import db


class DeliveryPartner(db.Model):
    __tablename__ = 'delivery_partners'

    VEHICLE_BIKE      = 'Bike'
    VEHICLE_SCOOTER   = 'Scooter'
    VEHICLE_AUTO      = 'Auto'
    VEHICLE_VAN       = 'Van'
    VEHICLE_TRUCK     = 'Truck'

    STATUS_AVAILABLE  = 'available'
    STATUS_BUSY       = 'busy'
    STATUS_OFFLINE    = 'offline'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    phone        = db.Column(db.String(20))
    vehicle_type = db.Column(db.String(32), default=VEHICLE_BIKE)
    vehicle_no   = db.Column(db.String(32))          # e.g. MH01AB1234
    area         = db.Column(db.String(120))          # Service area / city zone
    status       = db.Column(db.String(20), default=STATUS_AVAILABLE)
    is_active    = db.Column(db.Boolean, default=True)

    total_deliveries = db.Column(db.Integer, default=0)
    rating           = db.Column(db.Numeric(3, 2), default=5.0)

    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user        = db.relationship('User', backref=db.backref('delivery_profile', uselist=False))
    assignments = db.relationship('DeliveryAssignment', backref='partner', lazy='dynamic',
                                  order_by='DeliveryAssignment.assigned_at.desc()')

    @property
    def active_assignments(self):
        return self.assignments.filter(
            DeliveryAssignment.status.in_(['assigned', 'picked_up', 'out_for_delivery'])
        ).all()

    @property
    def completed_today(self):
        today = datetime.utcnow().date()
        return self.assignments.filter(
            DeliveryAssignment.status == 'delivered',
            db.func.date(DeliveryAssignment.updated_at) == today
        ).count()


class DeliveryAssignment(db.Model):
    __tablename__ = 'delivery_assignments'

    STATUS_ASSIGNED         = 'assigned'
    STATUS_PICKED_UP        = 'picked_up'
    STATUS_OUT_FOR_DELIVERY = 'out_for_delivery'
    STATUS_DELIVERED        = 'delivered'
    STATUS_ATTEMPTED        = 'attempted'
    STATUS_FAILED           = 'failed'
    STATUS_RETURNED         = 'returned'

    STATUS_LABELS = {
        'assigned':         'Assigned',
        'picked_up':        'Picked Up from Seller',
        'out_for_delivery': 'Out for Delivery',
        'delivered':        'Delivered',
        'attempted':        'Delivery Attempted',
        'failed':           'Delivery Failed',
        'returned':         'Returned to Seller',
    }

    id          = db.Column(db.Integer, primary_key=True)
    order_id    = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    partner_id  = db.Column(db.Integer, db.ForeignKey('delivery_partners.id'), nullable=False)

    status      = db.Column(db.String(30), default=STATUS_ASSIGNED)
    notes       = db.Column(db.Text)               # delivery notes, special instructions
    otp         = db.Column(db.String(6))          # 6-digit OTP for delivery confirmation
    otp_verified= db.Column(db.Boolean, default=False)

    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order  = db.relationship('Order', backref=db.backref('delivery_assignment', uselist=False))

    @property
    def label(self):
        return self.STATUS_LABELS.get(self.status, self.status.title())

    @staticmethod
    def generate_otp():
        import secrets
        return str(secrets.randbelow(900000) + 100000)
