"""Auth routes — Register (Customer / Company), Login, Logout."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, bcrypt, limiter
from models.user import User
from models.company import Company
from models.cart import CartItem
from forms.auth_forms import RegistrationForm, LoginForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Prevent duplicate emails (race condition guard)
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html', form=form)

        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            email=form.email.data.lower().strip(),
            password_hash=hashed_pw,
            role=form.role.data,
        )
        db.session.add(user)
        db.session.commit()

        _merge_session_cart(user)
        login_user(user)

        if user.is_company:
            flash('Welcome! Please complete your company profile.', 'success')
            return redirect(url_for('company.setup_profile'))
        else:
            flash(f'Welcome to FabricBazaar, {user.first_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per hour")          # brute-force protection
def login():
    if current_user.is_authenticated:
        return redirect(_after_login_url())

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            if not user.is_active:
                flash('This account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember.data)
            _merge_session_cart(user)
            flash(f'Welcome back, {user.first_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or _after_login_url())
        else:
            # Generic message — don't reveal whether email exists
            flash('Incorrect email or password.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out. See you soon!', 'info')
    return redirect(url_for('main.index'))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _after_login_url():
    if current_user.is_admin:
        return url_for('admin.dashboard')
    if current_user.is_company:
        return url_for('company.dashboard')
    if current_user.is_delivery:
        return url_for('delivery.dashboard')
    return url_for('main.index')


def _merge_session_cart(user):
    from flask import session
    guest_cart = session.pop('cart', {})
    if not guest_cart:
        return
    for pid_str, qty in guest_cart.items():
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        existing = CartItem.query.filter_by(user_id=user.id, product_id=pid).first()
        if existing:
            existing.quantity += qty
        else:
            db.session.add(CartItem(user_id=user.id, product_id=pid, quantity=qty))
    db.session.commit()
