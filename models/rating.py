"""
SellerRating  — customers rate a seller company after receiving an order.
ProductReview — customers review individual products.
"""
from datetime import datetime
from extensions import db


class SellerRating(db.Model):
    __tablename__ = 'seller_ratings'

    id          = db.Column(db.Integer, primary_key=True)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'),     nullable=False)
    order_id    = db.Column(db.Integer, db.ForeignKey('orders.id'),    nullable=True)

    rating      = db.Column(db.Integer, nullable=False)   # 1–5
    title       = db.Column(db.String(120))
    review      = db.Column(db.Text)

    # Experience dimensions
    quality_rating       = db.Column(db.Integer)   # 1-5
    communication_rating = db.Column(db.Integer)   # 1-5
    delivery_rating      = db.Column(db.Integer)   # 1-5

    is_verified_purchase = db.Column(db.Boolean, default=False)
    is_approved          = db.Column(db.Boolean, default=True)  # Admin can hide
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    seller_reply         = db.Column(db.Text)
    seller_replied_at    = db.Column(db.DateTime)

    # Relationships
    company = db.relationship('Company', backref=db.backref('ratings', lazy='dynamic'))
    user    = db.relationship('User',    backref=db.backref('seller_ratings', lazy='dynamic'))
    order   = db.relationship('Order',   backref=db.backref('seller_rating', uselist=False))

    __table_args__ = (
        db.UniqueConstraint('company_id', 'user_id', 'order_id', name='uq_seller_rating'),
    )

    @property
    def star_range(self):
        return range(1, 6)


class ProductReview(db.Model):
    __tablename__ = 'product_reviews'

    id          = db.Column(db.Integer, primary_key=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    order_id    = db.Column(db.Integer, db.ForeignKey('orders.id'),   nullable=True)

    rating      = db.Column(db.Integer, nullable=False)   # 1–5
    title       = db.Column(db.String(120))
    review      = db.Column(db.Text)

    is_verified_purchase = db.Column(db.Boolean, default=False)
    is_approved          = db.Column(db.Boolean, default=True)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('reviews', lazy='dynamic'))
    user    = db.relationship('User',    backref=db.backref('product_reviews', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('product_id', 'user_id', 'order_id', name='uq_product_review'),
    )


