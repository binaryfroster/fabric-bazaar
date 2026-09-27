"""
CartItem model — persisted cart for logged-in users.
Guest cart is handled in the session (see routes/cart.py).
"""

from datetime import datetime
from extensions import db


class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False, default=1)
    added_at   = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: one row per user+product combination
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='uq_cart_user_product'),
    )

    def __repr__(self):
        return f'<CartItem user={self.user_id} product={self.product_id} qty={self.quantity}>'

    @property
    def subtotal(self):
        """Returns line-item total using current display price."""
        if self.product:
            return float(self.product.display_price) * self.quantity
        return 0.0

    @property
    def unit_price(self):
        if self.product:
            return float(self.product.display_price)
        return 0.0
