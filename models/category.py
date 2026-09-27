"""
Category model — product categories (e.g., Egyptian Cotton, Bamboo, etc.)
"""

from datetime import datetime
from extensions import db


class Category(db.Model):
    __tablename__ = 'categories'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(80), unique=True, nullable=False)
    slug        = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    image       = db.Column(db.String(256))          # category hero image
    icon        = db.Column(db.String(16), default='🧵')   # emoji icon
    is_featured = db.Column(db.Boolean, default=False)
    sort_order  = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'

    @property
    def product_count(self):
        return self.products.filter_by(is_active=True).count()
