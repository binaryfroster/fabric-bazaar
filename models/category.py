import time
from datetime import datetime
from extensions import db

_CATEGORY_CACHE = {'data': None, 'timestamp': 0}


class Category(db.Model):
    __tablename__ = 'categories'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(80), unique=True, nullable=False)
    slug        = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    image       = db.Column(db.String(256))          # category hero image
    icon        = db.Column(db.String(16), default='🧵')   # emoji icon
    is_featured = db.Column(db.Boolean, default=False)
    sort_order  = db.Column(db.Integer, default=0, index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'

    @property
    def product_count(self):
        return self.products.filter_by(is_active=True).count()


def get_cached_categories(ttl_seconds: int = 300):
    """Return categories from in-memory cache (5-min TTL) to prevent repeated DB round-trips."""
    now = time.time()
    if _CATEGORY_CACHE['data'] is None or (now - _CATEGORY_CACHE['timestamp']) > ttl_seconds:
        _CATEGORY_CACHE['data'] = Category.query.order_by(Category.sort_order).all()
        _CATEGORY_CACHE['timestamp'] = now
    return _CATEGORY_CACHE['data']


def clear_categories_cache():
    """Invalidate in-memory categories cache when modified by admin."""
    _CATEGORY_CACHE['data'] = None
    _CATEGORY_CACHE['timestamp'] = 0
