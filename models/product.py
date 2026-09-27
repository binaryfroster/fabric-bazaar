"""
Product model — fabric marketplace products from multiple companies.
"""
from datetime import datetime
from extensions import db

FABRIC_CATEGORIES = [
    'Bed Sheets', 'Pillow Covers', 'Blankets & Quilts',
    'Sarees', 'Salwar Suits', 'Kurtas & Kurtis',
    'Dhooties', 'Lungis', 'Shirts & Tops',
    'Trousers & Pants', 'Fabrics & Cloth',
    'Towels & Bathrobes', 'Curtains',
    'Tablecloths', 'Other',
]

MATERIALS = [
    'Cotton', 'Pure Cotton', 'Egyptian Cotton',
    'Silk', 'Pure Silk', 'Art Silk',
    'Polyester', 'Poly-Cotton Blend',
    'Linen', 'Bamboo',
    'Wool', 'Cashmere',
    'Rayon / Viscose', 'Chiffon', 'Georgette',
    'Denim', 'Khadi', 'Muslin',
    'Microfiber', 'Velvet', 'Satin / Sateen',
]

SIZES = [
    'Free Size', 'XS', 'S', 'M', 'L', 'XL', 'XXL',
    'Single', 'Double', 'Queen', 'King',
    '1m', '2m', '5m', '10m',
]

COLORS = [
    'White', 'Off-White', 'Cream', 'Beige', 'Ivory',
    'Black', 'Grey', 'Charcoal',
    'Red', 'Maroon', 'Crimson',
    'Blue', 'Navy', 'Sky Blue', 'Royal Blue',
    'Green', 'Mehendi', 'Mint',
    'Yellow', 'Golden', 'Mustard',
    'Pink', 'Peach', 'Rose',
    'Purple', 'Violet', 'Lavender',
    'Orange', 'Rust', 'Copper',
    'Brown', 'Tan', 'Camel',
    'Multi-colour', 'Printed',
]


class Product(db.Model):
    __tablename__ = 'products'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    slug        = db.Column(db.String(160), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    details     = db.Column(db.Text)
    price       = db.Column(db.Numeric(10, 2), nullable=False)
    sale_price  = db.Column(db.Numeric(10, 2))
    sku         = db.Column(db.String(64), unique=True)

    # Fabric-specific
    fabric_type = db.Column(db.String(64))   # mapped to FABRIC_CATEGORIES
    color       = db.Column(db.String(64))
    size        = db.Column(db.String(32))
    material    = db.Column(db.String(64))
    thread_count = db.Column(db.Integer)
    pattern     = db.Column(db.String(64))   # Solid, Striped, Floral, Geometric, etc.
    care_instructions = db.Column(db.String(256))

    # Media
    image       = db.Column(db.String(256))
    image_2     = db.Column(db.String(256))
    image_3     = db.Column(db.String(256))
    image_4     = db.Column(db.String(256))

    # Inventory
    stock       = db.Column(db.Integer, default=0, nullable=False)
    min_order_qty = db.Column(db.Integer, default=1)  # Wholesale minimum
    view_count  = db.Column(db.Integer, default=0, nullable=False)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    is_new      = db.Column(db.Boolean, default=False)
    is_bestseller = db.Column(db.Boolean, default=False)

    # Foreign keys
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    company_id  = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    cart_items  = db.relationship('CartItem',  backref='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.name}>'

    @property
    def display_price(self):
        return self.sale_price if self.sale_price else self.price

    @property
    def is_on_sale(self):
        return self.sale_price is not None and self.sale_price < self.price

    @property
    def discount_percent(self):
        if self.is_on_sale:
            return int(((self.price - self.sale_price) / self.price) * 100)
        return 0

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def primary_image(self):
        return self.image or 'placeholder.jpg'

    def get_images(self):
        return [img for img in [self.image, self.image_2, self.image_3, self.image_4] if img]
