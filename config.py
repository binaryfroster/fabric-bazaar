"""
FabricBazaar configuration.

All secrets MUST come from environment variables — never hardcode credentials.
Copy .env.example to .env and fill in real values before running.
"""
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _database_url() -> str:
    """Return a SQLAlchemy-compatible database URL."""
    url = os.environ.get('DATABASE_URL', '')
    # Some managed providers still expose SQLAlchemy's legacy URL scheme.
    if url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url


def _require_env(key: str, fallback: str | None = None) -> str:
    """Return env var or fallback; raise in production if missing."""
    value = os.environ.get(key, fallback)
    if value is None:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def _is_serverless() -> bool:
    """True when running on Vercel (or a similar serverless platform)."""
    return bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))


class Config:
    # ── Core ──────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # ── Security headers ──────────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 300}

    # Redis is required in production; in-memory limiting remains local-only.
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', 'memory://')

    # S3-compatible storage (AWS S3, Cloudflare R2, etc.) for production media.
    OBJECT_STORAGE_BUCKET = os.environ.get('OBJECT_STORAGE_BUCKET', '')
    OBJECT_STORAGE_REGION = os.environ.get('OBJECT_STORAGE_REGION', '')
    OBJECT_STORAGE_ENDPOINT_URL = os.environ.get('OBJECT_STORAGE_ENDPOINT_URL', '')
    OBJECT_STORAGE_ACCESS_KEY_ID = os.environ.get('OBJECT_STORAGE_ACCESS_KEY_ID', '')
    OBJECT_STORAGE_SECRET_ACCESS_KEY = os.environ.get('OBJECT_STORAGE_SECRET_ACCESS_KEY', '')
    OBJECT_STORAGE_PREFIX = os.environ.get('OBJECT_STORAGE_PREFIX', 'fabricbazaar')
    MEDIA_PUBLIC_BASE_URL = os.environ.get('MEDIA_PUBLIC_BASE_URL', '').rstrip('/')

    # ── Uploads ───────────────────────────────────────────────────────────────
    UPLOAD_FOLDER        = os.path.join(BASE_DIR, 'static', 'images')
    ALLOWED_EXTENSIONS   = {'png', 'jpg', 'jpeg', 'webp'}
    MAX_CONTENT_LENGTH   = 5 * 1024 * 1024   # 5 MB

    # ── Pagination ────────────────────────────────────────────────────────────
    PRODUCTS_PER_PAGE = 12

    # ── Branding ──────────────────────────────────────────────────────────────
    BRAND_NAME     = 'FabricBazaar'
    BRAND_TAGLINE  = "India's Fabric Marketplace"
    CURRENCY       = 'INR'
    CURRENCY_SYMBOL = '₹'

    # ── Razorpay ─────────────────────────────────────────────────────────────
    # Keys are loaded from environment — NEVER hardcode here.
    RAZORPAY_KEY_ID     = os.environ.get('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
    RAZORPAY_UPI_ID     = os.environ.get('RAZORPAY_UPI_ID', '')

    # ── COD fraud prevention ──────────────────────────────────────────────────
    COD_MAX_ORDER_VALUE = 5000   # orders above ₹5000 must pay online
    COD_MAX_PENDING     = 2      # max undelivered COD orders per user

    # ── Feature flags (resolved at init_app) ───────────────────────────────────
    # Online card/UPI payments require Razorpay keys; without them the storefront
    # still works with Cash on Delivery. Set in init_app / DevelopmentConfig.
    PAYMENTS_ENABLED = False


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        f'sqlite:///{os.path.join(BASE_DIR, "fabricbazaar_dev.db")}'
    )
    # A stable dev key keeps you logged in across reloads. Overridable via .env.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-insecure-key-change-in-production'
    # Relaxed Razorpay check in dev — allow empty test keys
    RAZORPAY_KEY_ID     = os.environ.get('RAZORPAY_KEY_ID', '')  # Set in .env
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')  # Set in .env

    @classmethod
    def init_app(cls, app):
        app.config['PAYMENTS_ENABLED'] = bool(
            app.config.get('RAZORPAY_KEY_ID') and app.config.get('RAZORPAY_KEY_SECRET')
        )


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True   # HTTPS only
    # SQLite is ephemeral on Vercel and is unsafe with concurrent requests.
    SQLALCHEMY_DATABASE_URI = _database_url()

    @classmethod
    def init_app(cls, app):
        # ── Hard requirements: the app genuinely cannot run without these ───────
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            raise RuntimeError(
                'DATABASE_URL is not set. Point it at your Postgres database '
                '(e.g. your Supabase connection string).'
            )
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            raise RuntimeError('DATABASE_URL must point to PostgreSQL in production.')
        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError(
                'SECRET_KEY is not set. Generate one with '
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )

        # ── Serverless-friendly connection handling ────────────────────────────
        # On Vercel, warm containers reuse connections via QueuePool against the
        # Supabase transaction pooler (port 6543) without per-request TLS overhead.
        if _is_serverless():
            from sqlalchemy.pool import QueuePool
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'poolclass': QueuePool,
                'pool_size': 2,
                'max_overflow': 2,
                'pool_timeout': 10,
                'pool_recycle': 300,
                'pool_pre_ping': True,
                'connect_args': {'sslmode': 'require'},
            }

        # ── Optional integrations: degrade gracefully instead of refusing boot ──
        # Rate limiting: needs Redis to be effective across invocations. Without
        # it we fall back to in-memory limiting (best-effort) and warn.
        redis_url = app.config.get('RATELIMIT_STORAGE_URI', 'memory://')
        if not redis_url.startswith(('redis://', 'rediss://')):
            app.logger.warning(
                'REDIS_URL not configured — rate limiting is in-memory and '
                'best-effort only on serverless. Set REDIS_URL (e.g. Upstash) '
                'for durable rate limiting.'
            )

        # Media uploads: need object storage on a read-only serverless FS.
        storage_ready = all([
            app.config.get('OBJECT_STORAGE_BUCKET'),
            app.config.get('OBJECT_STORAGE_ACCESS_KEY_ID'),
            app.config.get('OBJECT_STORAGE_SECRET_ACCESS_KEY'),
            app.config.get('MEDIA_PUBLIC_BASE_URL'),
        ])
        if not storage_ready:
            app.logger.warning(
                'Object storage not configured — new image uploads will be '
                'rejected on a read-only filesystem. The bundled catalogue still '
                'displays. Set OBJECT_STORAGE_* + MEDIA_PUBLIC_BASE_URL to enable '
                'uploads (Supabase Storage is S3-compatible and free).'
            )

        # Online payments: without Razorpay keys the store runs COD-only.
        app.config['PAYMENTS_ENABLED'] = bool(cls.RAZORPAY_KEY_ID and cls.RAZORPAY_KEY_SECRET)
        if not app.config['PAYMENTS_ENABLED']:
            app.logger.warning(
                'Razorpay keys not set — online payments disabled; '
                'Cash on Delivery remains available.'
            )


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
