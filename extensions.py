"""
Shared Flask extension instances — imported by app.py and models.
Using the application factory pattern to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db            = SQLAlchemy()
login_manager = LoginManager()
bcrypt        = Bcrypt()
migrate       = Migrate()
csrf          = CSRFProtect()
limiter       = Limiter(
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"],
)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please sign in to continue.'
login_manager.login_message_category = 'info'
