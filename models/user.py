"""
User model — customers, companies (sellers), and admins.
role: 'customer' | 'company' | 'admin'
"""
from datetime import datetime
from flask_login import UserMixin
from extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    ROLE_CUSTOMER  = 'customer'
    ROLE_COMPANY   = 'company'
    ROLE_ADMIN     = 'admin'
    ROLE_DELIVERY  = 'delivery'

    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(64), nullable=False)
    last_name     = db.Column(db.String(64), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default=ROLE_CUSTOMER, nullable=False)
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders     = db.relationship('Order', backref='customer', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic',
                                 cascade='all, delete-orphan')
    company    = db.relationship('Company', backref='user', uselist=False)

    def __repr__(self):
        return f'<User {self.email} [{self.role}]>'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_company(self):
        return self.role == self.ROLE_COMPANY

    @property
    def is_customer(self):
        return self.role == self.ROLE_CUSTOMER

    @property
    def is_delivery(self):
        return self.role == self.ROLE_DELIVERY

    def get_cart_total(self):
        return sum(item.subtotal for item in self.cart_items)

    def get_cart_count(self):
        return self.cart_items.count()


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))
