"""
Checkout routes — Razorpay online payment + Cash on Delivery.
"""
import hmac
import hashlib
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, session, request, jsonify, current_app)
from flask_login import current_user
from extensions import db
from models.product import Product
from models.cart import CartItem
from models.order import Order, OrderItem
from forms.checkout_forms import CheckoutForm
from routes.cart import _get_cart, _calc_shipping


# ── All Indian states & UTs — full coverage ───────────────────────────────────
#
# Maps every state/UT to a delivery partner email.
# Add real partner accounts in seed.py / admin panel as you expand.
#
STATE_PARTNER_EMAIL = {
    # States
    'Andhra Pradesh':       'rider.ap@fabricbazaar.in',
    'Arunachal Pradesh':    'rider.northeast@fabricbazaar.in',
    'Assam':                'rider.northeast@fabricbazaar.in',
    'Bihar':                'rider.bihar@fabricbazaar.in',
    'Chhattisgarh':         'rider.cg@fabricbazaar.in',
    'Goa':                  'rider.goa@fabricbazaar.in',
    'Gujarat':              'rider.guj@fabricbazaar.in',
    'Haryana':              'rider.haryana@fabricbazaar.in',
    'Himachal Pradesh':     'rider.hp@fabricbazaar.in',
    'Jharkhand':            'rider.jharkhand@fabricbazaar.in',
    'Karnataka':            'rider.kar@fabricbazaar.in',
    'Kerala':               'rider.kerala@fabricbazaar.in',
    'Madhya Pradesh':       'rider.mp@fabricbazaar.in',
    'Maharashtra':          'rider.mah@fabricbazaar.in',
    'Manipur':              'rider.northeast@fabricbazaar.in',
    'Meghalaya':            'rider.northeast@fabricbazaar.in',
    'Mizoram':              'rider.northeast@fabricbazaar.in',
    'Nagaland':             'rider.northeast@fabricbazaar.in',
    'Odisha':               'rider.odisha@fabricbazaar.in',
    'Punjab':               'rider.punjab@fabricbazaar.in',
    'Rajasthan':            'rider.rajasthan@fabricbazaar.in',
    'Sikkim':               'rider.northeast@fabricbazaar.in',
    'Tamil Nadu':           'rider.tn@fabricbazaar.in',
    'Telangana':            'rider.telangana@fabricbazaar.in',
    'Tripura':              'rider.northeast@fabricbazaar.in',
    'Uttar Pradesh':        'rider.up@fabricbazaar.in',
    'Uttarakhand':          'rider.uk@fabricbazaar.in',
    'West Bengal':          'rider.wb@fabricbazaar.in',
    # Union Territories
    'Andaman and Nicobar Islands': 'rider.island@fabricbazaar.in',
    'Chandigarh':           'rider.punjab@fabricbazaar.in',
    'Dadra and Nagar Haveli and Daman and Diu': 'rider.guj@fabricbazaar.in',
    'Delhi':                'rider.delhi@fabricbazaar.in',
    'Jammu and Kashmir':    'rider.jk@fabricbazaar.in',
    'Ladakh':               'rider.jk@fabricbazaar.in',
    'Lakshadweep':          'rider.island@fabricbazaar.in',
    'Puducherry':           'rider.tn@fabricbazaar.in',
}
_DEFAULT_PARTNER = 'rider.rest@fabricbazaar.in'


def _auto_assign_delivery(order):
    """Automatically assign order to the delivery partner for that state."""
    try:
        from models.delivery import DeliveryPartner, DeliveryAssignment
        from models.order import OrderTracking
        from models.user import User

        order_state = (order.state or '').strip()
        email = STATE_PARTNER_EMAIL.get(order_state, _DEFAULT_PARTNER)

        user = User.query.filter_by(email=email).first()
        if not user:
            # Try the default fallback partner
            user = User.query.filter_by(email=_DEFAULT_PARTNER).first()
        if not user:
            return

        partner = DeliveryPartner.query.filter_by(user_id=user.id).first()
        if not partner:
            return

        # Don't double-assign
        existing = DeliveryAssignment.query.filter(
            DeliveryAssignment.order_id == order.id,
            DeliveryAssignment.status.notin_(['delivered', 'failed', 'returned', 'cancelled'])
        ).first()
        if existing:
            return

        otp = DeliveryAssignment.generate_otp()
        assignment = DeliveryAssignment(
            order_id=order.id,
            partner_id=partner.id,
            status='assigned',
            otp=otp,
        )
        db.session.add(assignment)
        order.status = 'handed_to_courier'
        OrderTracking.log(
            order_id=order.id,
            status='handed_to_courier',
            message=f'Auto-assigned to delivery partner for {order_state or "your region"}. OTP generated for customer.',
        )
        db.session.commit()
    except Exception:
        import traceback
        current_app.logger.exception('Delivery auto-assign failed for order %s', order.id)


def _check_cod_eligibility(user, total):
    """
    Returns (allowed: bool, reason: str).
    Blocks COD if order value exceeds limit or user has too many pending COD orders.
    """
    max_value   = current_app.config.get('COD_MAX_ORDER_VALUE', 5000)
    max_pending = current_app.config.get('COD_MAX_PENDING', 2)

    if float(total) > max_value:
        return False, (
            f'Cash on Delivery is only available for orders up to ₹{max_value:,}. '
            f'Please pay online for this order.'
        )

    if user and user.is_authenticated:
        pending_cod = Order.query.filter_by(
            user_id=user.id,
            payment_status='cod',
            status=Order.STATUS_CONFIRMED,
        ).count()
        # Also count orders that are processing/shipped but not yet delivered
        active_cod = Order.query.filter(
            Order.user_id == user.id,
            Order.payment_status == 'cod',
            Order.status.in_([Order.STATUS_PROCESSING, Order.STATUS_SHIPPED]),
        ).count()
        if (pending_cod + active_cod) >= max_pending:
            return False, (
                f'You have {pending_cod + active_cod} pending Cash on Delivery orders. '
                f'Please pay online or wait for existing orders to be delivered.'
            )

    return True, ''


checkout_bp = Blueprint('checkout', __name__)


def _razorpay_client():
    import razorpay
    return razorpay.Client(auth=(
        current_app.config['RAZORPAY_KEY_ID'],
        current_app.config['RAZORPAY_KEY_SECRET'],
    ))


# ─── Step 1 & 2: Checkout Form ───────────────────────────────────────────────

@checkout_bp.route('/', methods=['GET', 'POST'])
def index():
    cart_items, subtotal = _get_cart()
    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('shop.index'))

    shipping = _calc_shipping(subtotal)
    tax      = round(float(subtotal) * 0.18, 2)
    total    = float(subtotal) + float(shipping) + float(tax)

    cod_max  = current_app.config.get('COD_MAX_ORDER_VALUE', 5000)
    cod_available = float(total) <= cod_max

    form = CheckoutForm()
    if current_user.is_authenticated and not form.is_submitted():
        form.first_name.data = current_user.first_name
        form.last_name.data  = current_user.last_name
        form.email.data      = current_user.email

    if form.validate_on_submit():
        payment_method = request.form.get('payment_method', 'cod')

        # Online payments require Razorpay to be configured.
        if payment_method == 'online' and not current_app.config.get('PAYMENTS_ENABLED'):
            flash('Online payment is currently unavailable. Please choose Cash on Delivery.', 'warning')
            return render_template('checkout.html', form=form,
                                   cart_items=cart_items, subtotal=subtotal,
                                   shipping=shipping, tax=tax, total=total,
                                   cod_available=cod_available, cod_max=cod_max)

        # COD eligibility check
        if payment_method == 'cod':
            allowed, reason = _check_cod_eligibility(current_user, total)
            if not allowed:
                flash(reason, 'warning')
                return render_template('checkout.html', form=form,
                                       cart_items=cart_items, subtotal=subtotal,
                                       shipping=shipping, tax=tax, total=total,
                                       cod_available=cod_available, cod_max=cod_max)

        order = Order(
            order_number   = Order.generate_order_number(),
            user_id        = current_user.id if current_user.is_authenticated else None,
            first_name     = form.first_name.data.strip(),
            last_name      = form.last_name.data.strip(),
            email          = form.email.data.lower().strip(),
            phone          = form.phone.data.strip(),
            address_line1  = form.address_line1.data.strip(),
            address_line2  = (form.address_line2.data or '').strip() or None,
            city           = form.city.data.strip(),
            state          = form.state.data,
            postal_code    = form.postal_code.data.strip(),
            country        = 'India',
            notes          = (form.notes.data or '').strip() or None,
            subtotal       = subtotal,
            shipping_cost  = shipping,
            tax            = tax,
            total          = total,
            status         = Order.STATUS_PENDING,
            payment_status = 'pending',
        )
        db.session.add(order)
        db.session.flush()

        for ci in cart_items:
            product = ci['product']
            db.session.add(OrderItem(
                order_id      = order.id,
                product_id    = product.id,
                product_name  = product.name,
                product_image = product.primary_image,
                price         = product.display_price,
                quantity      = ci['quantity'],
            ))
            p = Product.query.with_for_update().filter_by(id=product.id).first()
            if p and p.stock >= ci['quantity']:
                p.stock = max(0, p.stock - ci['quantity'])
            elif p and p.stock < ci['quantity']:
                p.stock = 0  # floor at zero even if concurrent orders raced

        db.session.commit()
        session['pending_order'] = order.order_number

        # COD → skip payment, go straight to confirmation
        if payment_method == 'cod':
            order.status         = Order.STATUS_CONFIRMED
            order.payment_status = 'cod'
            db.session.commit()
            if current_user.is_authenticated:
                CartItem.query.filter_by(user_id=current_user.id).delete()
            session.pop('cart', None)
            session.pop('pending_order', None)
            db.session.commit()
            _auto_assign_delivery(order)
            flash('Order placed! Pay cash on delivery. A delivery partner has been assigned.', 'success')
            return redirect(url_for('checkout.confirmation',
                                    order_number=order.order_number))

        # Online payment
        return redirect(url_for('checkout.payment',
                                order_number=order.order_number))

    return render_template('checkout.html',
                           form=form,
                           cart_items=cart_items,
                           subtotal=subtotal,
                           shipping=shipping,
                           tax=tax,
                           total=total,
                           cod_available=cod_available,
                           cod_max=cod_max)


# ─── Payment Page ─────────────────────────────────────────────────────────────

@checkout_bp.route('/payment/<order_number>')
def payment(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    if order.payment_status in ('paid', 'cod'):
        return redirect(url_for('checkout.confirmation',
                                order_number=order.order_number))
    if not current_app.config.get('PAYMENTS_ENABLED'):
        flash('Online payment is currently unavailable. Please contact us to complete this order.', 'warning')
        return redirect(url_for('checkout.confirmation', order_number=order.order_number))
    return render_template('payment.html',
                           order=order,
                           razorpay_key=current_app.config['RAZORPAY_KEY_ID'])


# ─── Create Razorpay Order (AJAX) ─────────────────────────────────────────────

@checkout_bp.route('/razorpay/create-order', methods=['POST'])
def create_razorpay_order():
    if not current_app.config.get('PAYMENTS_ENABLED'):
        return jsonify({'success': False, 'error': 'Online payments are not enabled.'}), 503
    data         = request.get_json() or {}
    order_number = data.get('order_number') or session.get('pending_order')
    if not order_number:
        return jsonify({'success': False, 'error': 'Order not found'}), 400
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    if order.razorpay_order_id:
        return jsonify({
            'success': True,
            'rzp_order_id': order.razorpay_order_id,
            'amount': int(float(order.total) * 100),
            'key': current_app.config['RAZORPAY_KEY_ID'],
            'name': order.full_name, 'email': order.email,
            'phone': order.phone or '',
        })
    try:
        client = _razorpay_client()
        amount_paise = int(float(order.total) * 100)
        rzp_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': order.order_number,
            'notes': {'order_number': order.order_number},
            'payment_capture': 1,
        })
        order.razorpay_order_id = rzp_order['id']
        db.session.commit()
        return jsonify({
            'success': True,
            'rzp_order_id': rzp_order['id'],
            'amount': rzp_order['amount'],
            'key': current_app.config['RAZORPAY_KEY_ID'],
            'name': order.full_name, 'email': order.email,
            'phone': order.phone or '',
        })
    except Exception as e:
        current_app.logger.error(f'Razorpay error: {e}')
        return jsonify({'success': False, 'error': 'Payment service error. Please try again.'}), 500


# ─── Verify Razorpay Signature (AJAX) ─────────────────────────────────────────

@checkout_bp.route('/payment/verify', methods=['POST'])
def verify_payment():
    data = request.get_json() or {}
    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_order_id   = data.get('razorpay_order_id', '')
    razorpay_signature  = data.get('razorpay_signature', '')
    order_number        = data.get('order_number') or session.get('pending_order')

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, order_number]):
        return jsonify({'success': False, 'error': 'Missing payment data'}), 400

    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    key_secret   = current_app.config['RAZORPAY_KEY_SECRET'].encode('utf-8')
    message      = f'{razorpay_order_id}|{razorpay_payment_id}'.encode('utf-8')
    expected_sig = hmac.new(key_secret, message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, razorpay_signature):
        current_app.logger.warning(
            f'Payment signature mismatch for order {order_number}. '
            f'Possible fraud attempt from IP {request.remote_addr}.'
        )
        return jsonify({'success': False, 'error': 'Signature verification failed'}), 400

    order.status              = Order.STATUS_CONFIRMED
    order.payment_status      = 'paid'
    order.razorpay_payment_id = razorpay_payment_id
    order.tracking_number     = razorpay_payment_id
    db.session.commit()
    _auto_assign_delivery(order)

    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id).delete()
    session.pop('cart', None)
    session.pop('pending_order', None)
    db.session.commit()

    return jsonify({'success': True,
                    'redirect': url_for('checkout.confirmation',
                                        order_number=order.order_number)})


# ─── Payment Failed ────────────────────────────────────────────────────────────

@checkout_bp.route('/payment/failed', methods=['POST'])
def payment_failed():
    data         = request.get_json() or {}
    order_number = data.get('order_number') or session.get('pending_order')
    reason       = data.get('reason', 'unknown')
    if order_number:
        order = Order.query.filter_by(order_number=order_number).first()
        if order and order.payment_status == 'pending':
            for item in order.items:
                if item.product_id:
                    p = Product.query.get(item.product_id)
                    if p:
                        p.stock += item.quantity
            order.payment_status = 'failed'
            order.notes = (order.notes or '') + f'\nPayment failed: {reason}'
            db.session.commit()
    return jsonify({'success': True})


# ─── Confirmation ─────────────────────────────────────────────────────────────

@checkout_bp.route('/confirmation/<order_number>')
def confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_confirmation.html', order=order)
