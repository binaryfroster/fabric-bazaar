from datetime import datetime
import os
from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from extensions import db, login_manager, bcrypt, migrate, csrf, limiter
from storage import media_url


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Run config-level init if defined (e.g. production warnings)
    cfg = config[config_name]
    if hasattr(cfg, 'init_app'):
        cfg.init_app(app)

    # Vercel terminates TLS at its proxy. Preserve the original HTTPS scheme
    # for secure cookies and generated external URLs.
    if config_name == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'info'

    # ── Security Headers ──────────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # Basic CSP — tighten per-environment as needed
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.razorpay.com; "
            "frame-src https://api.razorpay.com https://checkout.razorpay.com;"
        )
        return response

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.main      import main_bp
    from routes.auth      import auth_bp
    from routes.shop      import shop_bp
    from routes.cart      import cart_bp
    from routes.checkout  import checkout_bp
    from routes.admin     import admin_bp
    from routes.company   import company_bp
    from routes.ratings   import ratings_bp
    from routes.analytics import analytics_bp
    from routes.messaging import msg_bp
    from routes.buyer     import buyer_bp
    from routes.tracking  import tracking_bp
    from routes.delivery  import delivery_bp
    from routes.wishlist  import wishlist_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp,      url_prefix='/auth')
    app.register_blueprint(shop_bp,      url_prefix='/shop')
    app.register_blueprint(cart_bp,      url_prefix='/cart')
    app.register_blueprint(checkout_bp,  url_prefix='/checkout')
    app.register_blueprint(admin_bp,     url_prefix='/admin')
    app.register_blueprint(company_bp,   url_prefix='/company')
    app.register_blueprint(ratings_bp,   url_prefix='/rate')
    app.register_blueprint(analytics_bp)
    app.register_blueprint(msg_bp)
    app.register_blueprint(buyer_bp)
    app.register_blueprint(tracking_bp)
    app.register_blueprint(delivery_bp)
    app.register_blueprint(wishlist_bp)

    # ── Error Handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f'Server Error: {e}')
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    # ── Context Processors ────────────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        from routes.cart import _get_cart_count
        from models.category import get_cached_categories
        from flask_login import current_user

        cart_count = _get_cart_count()
        categories = get_cached_categories()

        pending_companies_count = 0
        if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
            from models.company import Company
            pending_companies_count = Company.query.filter_by(
                is_verified=False, is_active=True).count()

        unread_messages = 0
        try:
            if current_user.is_authenticated:
                from models.messaging import MessageThread
                if current_user.is_customer:
                    unread_messages = db.session.query(
                        db.func.sum(MessageThread.unread_customer)
                    ).filter_by(customer_id=current_user.id).scalar() or 0
                elif current_user.is_company and current_user.company:
                    unread_messages = db.session.query(
                        db.func.sum(MessageThread.unread_seller)
                    ).filter_by(company_id=current_user.company.id).scalar() or 0
        except Exception:
            pass

        return {
            'cart_count':              cart_count,
            'categories':              categories,
            'brand_name':              app.config['BRAND_NAME'],
            'brand_tagline':           app.config['BRAND_TAGLINE'],
            'currency_symbol':         app.config['CURRENCY_SYMBOL'],
            'pending_companies_count': pending_companies_count,
            'now':                     datetime.utcnow(),
            'unread_messages':         int(unread_messages),
            'current_year':            datetime.utcnow().year,
        }

    # ── Template Filters ──────────────────────────────────────────────────────
    @app.template_filter('inr')
    def inr_filter(value):
        try:
            v = float(value)
            if v >= 10000000: return f'₹{v/10000000:.2f}Cr'
            if v >= 100000:   return f'₹{v/100000:.2f}L'
            if v >= 1000:     return f'₹{int(v):,}'
            return f'₹{v:.0f}'
        except (TypeError, ValueError):
            return f'₹{value}'

    @app.template_filter('media_url')
    def media_url_filter(value, folder='products'):
        """Resolve bundled assets locally and persistent object-storage media."""
        return media_url(value, folder)

    # Also expose as a global so templates can call media_url(value, 'folder')
    # directly, not only as a `value | media_url('folder')` filter.
    app.jinja_env.globals['media_url'] = media_url

    return app


# Vercel discovers this module-level WSGI application. Local runs retain the
# development default; deployments receive the production configuration.
app = create_app(
    os.environ.get('FLASK_ENV') or ('production' if os.environ.get('VERCEL') else 'development')
)


def _run_safe_migrations(app):
    """Add any missing columns to an existing DB without dropping data.

    Dialect-aware so it works on both SQLite (dev) and PostgreSQL (prod).
    Only relevant for upgrading an OLD database; fresh databases get every
    column from db.create_all().
    """
    with app.app_context():
        from sqlalchemy import text, inspect
        engine = db.engine
        inspector = inspect(engine)
        is_pg = engine.dialect.name == 'postgresql'

        dt_type = 'TIMESTAMP' if is_pg else 'DATETIME'

        NEEDED = [
            ('orders',     'delivered_at',
             f'ALTER TABLE orders ADD COLUMN delivered_at {dt_type}'),
            ('categories', 'icon',
             "ALTER TABLE categories ADD COLUMN icon VARCHAR(16) DEFAULT '🧵'"),
        ]

        existing_tables = set(inspector.get_table_names())
        with engine.connect() as conn:
            for table, col, ddl in NEEDED:
                if table not in existing_tables:
                    continue
                try:
                    cols = [c['name'] for c in inspector.get_columns(table)]
                    if col not in cols:
                        conn.execute(text(ddl))
                        conn.commit()
                        app.logger.info(f'Added column {table}.{col}')
                except Exception as e:
                    app.logger.warning(f'Migration warning ({table}.{col}): {e}')


def _auto_seed_if_empty(app):
    """Seed the database (non-destructively) when it is empty — first-deploy convenience."""
    with app.app_context():
        try:
            from models.user import User
            if User.query.count() == 0:
                app.logger.info('Empty database — running auto-seed...')
                import seed as seed_module
                seed_module.run(target_app=app, drop=False)
                app.logger.info('Auto-seed complete.')
        except Exception as e:
            app.logger.warning(f'Auto-seed skipped: {e}')


def bootstrap_database(app, seed=False):
    """Idempotently ensure the schema exists (and optionally seed).

    Safe to call on every start: create_all only creates missing tables.
    """
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f'create_all skipped: {e}')
    _run_safe_migrations(app)
    if seed:
        _auto_seed_if_empty(app)


# On serverless (Vercel) there is no start.sh to create the schema. Opt in with
# AUTO_INIT_DB=1 to create tables (and seed an empty DB). On Vercel, schema is already
# created and seeded, so avoid table-inspection delays on every serverless cold start.
if os.environ.get('AUTO_INIT_DB') == '1' and not os.environ.get('VERCEL'):
    bootstrap_database(app, seed=os.environ.get('AUTO_SEED', '1') == '1')
elif os.environ.get('FORCE_INIT_DB') == '1':
    bootstrap_database(app, seed=os.environ.get('AUTO_SEED', '1') == '1')


if __name__ == '__main__':
    bootstrap_database(app, seed=False)
    app.run(debug=True, host='0.0.0.0', port=5000)
