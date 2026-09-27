"""
Company model — seller/vendor profile on the marketplace.
Each company is linked to a User with role='company'.
"""
from datetime import datetime
from extensions import db


class Company(db.Model):
    __tablename__ = 'companies'

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # Basic Info
    name          = db.Column(db.String(120), nullable=False)
    slug          = db.Column(db.String(120), unique=True, nullable=False, index=True)
    tagline       = db.Column(db.String(200))
    description   = db.Column(db.Text)

    # Contact
    phone         = db.Column(db.String(20))
    whatsapp      = db.Column(db.String(20))
    website       = db.Column(db.String(200))
    email         = db.Column(db.String(120))

    # Address
    address_line1 = db.Column(db.String(256))
    address_line2 = db.Column(db.String(256))
    city          = db.Column(db.String(64))
    state         = db.Column(db.String(64))
    postal_code   = db.Column(db.String(16))
    country       = db.Column(db.String(64), default='India')

    # Business Details
    gst_number    = db.Column(db.String(20))
    pan_number    = db.Column(db.String(20))
    established_year = db.Column(db.Integer)
    business_type = db.Column(db.String(64))   # Manufacturer, Wholesaler, Retailer, Exporter

    # Media
    logo          = db.Column(db.String(256))
    banner        = db.Column(db.String(256))

    # Status
    is_verified   = db.Column(db.Boolean, default=False)   # Admin approved
    is_active     = db.Column(db.Boolean, default=True)
    is_featured   = db.Column(db.Boolean, default=False)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    products      = db.relationship('Product', backref='company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.name}>'

    @property
    def product_count(self):
        return self.products.filter_by(is_active=True).count()

    @property
    def logo_url(self):
        return self.logo or 'company-placeholder.jpg'

    @property
    def full_address(self):
        parts = [self.address_line1, self.address_line2,
                 self.city, self.state, self.postal_code]
        return ', '.join(p for p in parts if p)
