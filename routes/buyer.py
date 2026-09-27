"""
Buyer dashboard — order history, order detail with tracking timeline,
and account settings.
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models.order import Order, OrderTracking
from models.messaging import MessageThread

buyer_bp = Blueprint('buyer', __name__)

RETURN_WINDOW_HOURS = 48   # 2-day return window after delivery


def _require_customer():
    if not current_user.is_customer:
        flash('Customer account required.', 'warning')
        return redirect(url_for('main.index'))


# ── Dashboard ──────────────────────────────────────────────────────────────────

@buyer_bp.route('/account')
@login_required
def dashboard():
    r = _require_customer()
    if r: return r
    orders = current_user.orders.order_by(Order.created_at.desc()).limit(5).all()
    unread = db.session.query(db.func.sum(MessageThread.unread_customer)).filter_by(
        customer_id=current_user.id).scalar() or 0
    return render_template('buyer/dashboard.html', orders=orders, unread=int(unread))


# ── Orders ─────────────────────────────────────────────────────────────────────

@buyer_bp.route('/account/orders')
@login_required
def orders():
    r = _require_customer()
    if r: return r
    page = request.args.get('page', 1, type=int)
    all_orders = (current_user.orders
                  .order_by(Order.created_at.desc())
                  .paginate(page=page, per_page=10, error_out=False))
    return render_template('buyer/orders.html', orders=all_orders)


# ── Order Detail + Tracking ────────────────────────────────────────────────────

@buyer_bp.route('/account/orders/<order_number>')
@login_required
def order_detail(order_number):
    r = _require_customer()
    if r: return r
    order = Order.query.filter_by(
        order_number=order_number, user_id=current_user.id).first_or_404()
    timeline = _build_timeline(order)

    # Return window: 48 hrs after delivered_at (or updated_at fallback)
    can_return = False
    return_deadline = None
    if order.status == 'delivered':
        ref_time = order.delivered_at or order.updated_at
        return_deadline = ref_time + timedelta(hours=RETURN_WINDOW_HOURS)
        can_return = datetime.utcnow() < return_deadline

    return render_template('buyer/order_detail.html',
                           order=order, timeline=timeline,
                           can_return=can_return,
                           return_deadline=return_deadline)


# ── Loyalty ──────────────────────────────────────────────────────────────────

@buyer_bp.route('/account/loyalty')
@login_required
def loyalty():
    r = _require_customer()
    if r: return r
    from models.loyalty import LoyaltyAccount
    account = LoyaltyAccount.query.filter_by(user_id=current_user.id).first()
    if not account:
        account = LoyaltyAccount(user_id=current_user.id)
        db.session.add(account)
        db.session.commit()
    transactions = account.transactions.all()
    return render_template('buyer/loyalty.html', account=account, transactions=transactions)


# ── Request Return ─────────────────────────────────────────────────────────────

@buyer_bp.route('/account/orders/<order_number>/return', methods=['POST'])
@login_required
def request_return(order_number):
    r = _require_customer()
    if r: return r

    order = Order.query.filter_by(
        order_number=order_number, user_id=current_user.id).first_or_404()

    # Validate eligibility
    if order.status != 'delivered':
        flash('Only delivered orders can be returned.', 'warning')
        return redirect(url_for('buyer.order_detail', order_number=order_number))

    ref_time = order.delivered_at or order.updated_at
    deadline = ref_time + timedelta(hours=RETURN_WINDOW_HOURS)
    if datetime.utcnow() > deadline:
        flash('The 48-hour return window for this order has expired.', 'danger')
        return redirect(url_for('buyer.order_detail', order_number=order_number))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Please provide a reason for the return.', 'warning')
        return redirect(url_for('buyer.order_detail', order_number=order_number))

    # Update order status
    order.status = Order.STATUS_RETURN_REQUESTED

    # Log tracking event
    OrderTracking.log(
        order_id=order.id,
        status='returned',
        message=f'Return requested by customer. Reason: {reason}',
        created_by=current_user.id,
    )
    db.session.commit()

    flash('Your return request has been submitted. The seller will contact you within 24 hours.', 'success')
    return redirect(url_for('buyer.order_detail', order_number=order_number))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_timeline(order):
    STATUS_STEPS = [
        ('pending',    '🛒', 'Order Placed',      'Your order has been received'),
        ('confirmed',  '✅', 'Payment Confirmed',  'Payment verified successfully'),
        ('processing', '⚙️', 'Being Prepared',     'Seller is preparing your order'),
        ('shipped',    '🚚', 'Out for Delivery',   'Your order is on its way'),
        ('delivered',  '📦', 'Delivered',          'Order successfully delivered'),
    ]
    current_status = order.status
    # Treat return_requested as delivered for timeline display
    display_status = 'delivered' if current_status in ('return_requested', 'returned') else current_status

    status_order = ['pending', 'confirmed', 'processing', 'shipped', 'delivered']
    try:
        current_idx = status_order.index(display_status)
    except ValueError:
        current_idx = -1

    timeline = []
    for i, (status, icon, label, desc) in enumerate(STATUS_STEPS):
        if current_status == 'cancelled':
            state = 'cancelled' if status == 'pending' else 'pending'
        elif current_status == 'refunded':
            state = 'done' if status == 'pending' else ('refunded' if status == 'confirmed' else 'pending')
        else:
            state = 'done' if i < current_idx else ('active' if i == current_idx else 'pending')
        time_val = order.created_at if status == 'pending' else (
            order.delivered_at if status == 'delivered' and order.delivered_at else None)
        timeline.append({'status': status, 'icon': icon, 'label': label,
                         'desc': desc, 'state': state, 'time': time_val})

    if current_status == 'cancelled':
        timeline.append({'status': 'cancelled', 'icon': '❌', 'label': 'Cancelled',
                         'desc': 'This order has been cancelled',
                         'state': 'cancelled', 'time': order.updated_at})
    elif current_status == 'refunded':
        timeline.append({'status': 'refunded', 'icon': '💸', 'label': 'Refunded',
                         'desc': 'Refund has been processed',
                         'state': 'done', 'time': order.updated_at})
    elif current_status == 'return_requested':
        timeline.append({'status': 'return_requested', 'icon': '↩️', 'label': 'Return Requested',
                         'desc': 'Your return request is being reviewed',
                         'state': 'active', 'time': order.updated_at})
    elif current_status == 'returned':
        timeline.append({'status': 'returned', 'icon': '↩️', 'label': 'Returned',
                         'desc': 'Order has been returned to the seller',
                         'state': 'done', 'time': order.updated_at})
    return timeline


def award_loyalty_points(order):
    """Award loyalty points for a delivered order — idempotent (safe to call multiple times)."""
    try:
        from models.loyalty import LoyaltyAccount, LoyaltyTransaction
        if not order.user_id:
            return
        # Guard: don't award twice for the same order
        already = LoyaltyTransaction.query.filter_by(
            order_id=order.id, type='earn').first()
        if already:
            return
        points = max(1, int(float(order.total) // 10))  # 1 point per ₹10
        account = LoyaltyAccount.query.filter_by(user_id=order.user_id).first()
        if not account:
            account = LoyaltyAccount(user_id=order.user_id)
            db.session.add(account)
            db.session.flush()
        account.points       += points
        account.total_earned += points
        account.recalculate_tier()
        txn = LoyaltyTransaction(
            account_id=account.id,
            order_id=order.id,
            type='earn',
            points=points,
            description=f'Earned for order {order.order_number}',
        )
        db.session.add(txn)
        db.session.commit()
    except Exception:
        db.session.rollback()
