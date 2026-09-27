"""Wishlist — customers save products for later."""
from datetime import datetime
from extensions import db


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_items'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user    = db.relationship('User',    backref=db.backref('wishlist', lazy='dynamic'))
    product = db.relationship('Product', backref=db.backref('wishlisted_by', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='uq_wishlist'),
    )
