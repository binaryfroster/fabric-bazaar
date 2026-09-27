"""
Loyalty Points system.
Customers earn points on every delivered order.
Points can be redeemed at checkout for a discount.
"""
from datetime import datetime
from extensions import db


class LoyaltyAccount(db.Model):
    __tablename__ = 'loyalty_accounts'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    points     = db.Column(db.Integer, default=0, nullable=False)   # current balance
    total_earned = db.Column(db.Integer, default=0)                 # lifetime earned
    total_redeemed = db.Column(db.Integer, default=0)               # lifetime redeemed
    tier       = db.Column(db.String(20), default='Bronze')         # Bronze/Silver/Gold/Platinum
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user         = db.relationship('User', backref=db.backref('loyalty', uselist=False))
    transactions = db.relationship('LoyaltyTransaction', backref='account', lazy='dynamic',
                                   order_by='LoyaltyTransaction.created_at.desc()')

    # Tier thresholds (lifetime earned points)
    TIERS = {
        'Bronze':   (0,     199),
        'Silver':   (200,   999),
        'Gold':     (1000,  4999),
        'Platinum': (5000,  999999),
    }
    TIER_COLOURS = {
        'Bronze': '#CD7F32', 'Silver': '#9CA3AF',
        'Gold': '#F59E0B',   'Platinum': '#8B5CF6',
    }

    @property
    def rupee_value(self):
        """100 points = ₹10"""
        return self.points // 10

    @property
    def tier_colour(self):
        return self.TIER_COLOURS.get(self.tier, '#9CA3AF')

    def recalculate_tier(self):
        for tier, (low, high) in self.TIERS.items():
            if low <= self.total_earned <= high:
                self.tier = tier
                break


class LoyaltyTransaction(db.Model):
    __tablename__ = 'loyalty_transactions'

    id         = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('loyalty_accounts.id'), nullable=False)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)

    type        = db.Column(db.String(20), nullable=False)  # 'earn' | 'redeem' | 'bonus' | 'expire'
    points      = db.Column(db.Integer, nullable=False)     # positive=earn, negative=redeem
    description = db.Column(db.String(200))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('loyalty_transactions', lazy='dynamic'))
