"""
Delivery Partner routes.

/delivery/              → dashboard  (active + today's deliveries)
/delivery/orders        → all assigned orders list
/delivery/order/<id>    → single order detail + update actions
/delivery/scan          → search by order number (quick lookup on phone)
/delivery/history       → completed deliveries
"""
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, abort)
from flask_login import login_required, current_user
from extensions import db
from models.order import Order, OrderTracking
from models.delivery import DeliveryPartner, DeliveryAssignment

delivery_bp = Blueprint('delivery', __name__, url_prefix='/delivery')


# ── Auth decorator ────────────────────────────────────────────────────────────

def delivery_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not (current_user.is_delivery or current_user.is_admin):
            flash('Delivery partner account required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


def _get_partner():
    """Get or lazily create DeliveryPartner profile for current user."""
    p = DeliveryPartner.query.filter_by(user_id=current_user.id).first()
    if not p:
        p = DeliveryPartner(user_id=current_user.id)
        db.session.add(p)
        db.session.commit()
    return p


# ── Dashboard ─────────────────────────────────────────────────────────────────

@delivery_bp.route('/')
@delivery_required
def dashboard():
    partner = _get_partner()

    active = (DeliveryAssignment.query
              .filter_by(partner_id=partner.id)
              .filter(DeliveryAssignment.status.in_([
                  'assigned', 'picked_up', 'out_for_delivery']))
              .order_by(DeliveryAssignment.assigned_at.asc())
              .all())

    today = datetime.utcnow().date()
    delivered_today = (DeliveryAssignment.query
                       .filter_by(partner_id=partner.id, status='delivered')
                       .filter(db.func.date(DeliveryAssignment.updated_at) == today)
                       .count())

    total = partner.total_deliveries
    pending_count = len(active)

    return render_template('delivery/dashboard.html',
                           partner=partner,
                           active=active,
                           delivered_today=delivered_today,
                           total=total,
                           pending_count=pending_count)


# ── All Orders ────────────────────────────────────────────────────────────────

@delivery_bp.route('/orders')
@delivery_required
def orders():
    partner = _get_partner()
    status_filter = request.args.get('status', 'active')

    q = DeliveryAssignment.query.filter_by(partner_id=partner.id)
    if status_filter == 'active':
        q = q.filter(DeliveryAssignment.status.in_(
            ['assigned', 'picked_up', 'out_for_delivery']))
    elif status_filter == 'completed':
        q = q.filter(DeliveryAssignment.status == 'delivered')
    elif status_filter == 'failed':
        q = q.filter(DeliveryAssignment.status.in_(['failed', 'attempted', 'returned']))
    # else: all

    assignments = q.order_by(DeliveryAssignment.assigned_at.desc()).limit(50).all()
    return render_template('delivery/orders.html',
                           partner=partner,
                           assignments=assignments,
                           status_filter=status_filter)


# ── Single Order Detail ───────────────────────────────────────────────────────

@delivery_bp.route('/order/<int:assignment_id>')
@delivery_required
def order_detail(assignment_id):
    partner = _get_partner()
    assignment = DeliveryAssignment.query.get_or_404(assignment_id)
    if assignment.partner_id != partner.id and not current_user.is_admin:
        abort(403)

    order = assignment.order
    events = (OrderTracking.query
              .filter_by(order_id=order.id)
              .order_by(OrderTracking.timestamp.asc()).limit(10).all())

    return render_template('delivery/order_detail.html',
                           partner=partner,
                           assignment=assignment,
                           order=order,
                           events=events)


# ── Update Delivery Status ────────────────────────────────────────────────────

@delivery_bp.route('/order/<int:assignment_id>/update', methods=['POST'])
@delivery_required
def update_status(assignment_id):
    partner  = _get_partner()
    assignment = DeliveryAssignment.query.get_or_404(assignment_id)
    if assignment.partner_id != partner.id and not current_user.is_admin:
        abort(403)

    new_status = request.form.get('status', '').strip()
    location   = request.form.get('location', '').strip()
    notes      = request.form.get('notes', '').strip()

    valid = ['picked_up', 'out_for_delivery', 'delivered', 'attempted', 'failed', 'returned']
    if new_status not in valid:
        flash('Invalid status.', 'danger')
        return redirect(url_for('delivery.order_detail', assignment_id=assignment_id))

    order = assignment.order

    # Map assignment status → order tracking status
    tracking_status_map = {
        'picked_up':        'processing',
        'out_for_delivery': 'out_for_delivery',
        'delivered':        'delivered',
        'attempted':        'delivery_attempted',
        'failed':           'exception',
        'returned':         'returned',
    }
    # Default messages
    default_messages = {
        'picked_up':        'Package picked up from seller warehouse.',
        'out_for_delivery': 'Package is out for delivery. Expected by end of day.',
        'delivered':        '🎉 Package delivered successfully!',
        'attempted':        'Delivery attempted. Customer unavailable. Will retry.',
        'failed':           'Delivery failed. Package returning to origin.',
        'returned':         'Package returned to seller.',
    }

    assignment.status   = new_status
    assignment.notes    = notes or assignment.notes
    assignment.updated_at = datetime.utcnow()

    # Add a tracking event
    track_status = tracking_status_map.get(new_status, new_status)
    msg = notes or default_messages.get(new_status, '')
    OrderTracking.log(
        order_id=order.id,
        status=track_status,
        message=msg,
        location=location or (partner.area or ''),
        created_by=current_user.id,
    )

    # Sync order status
    order_status_sync = {
        'picked_up':        'processing',
        'out_for_delivery': 'shipped',
        'delivered':        'delivered',
        'attempted':        'shipped',
        'failed':           'shipped',
        'returned':         'cancelled',
    }
    order.status = order_status_sync.get(new_status, order.status)

    if new_status == 'delivered':
        partner.total_deliveries += 1
        partner.status = DeliveryPartner.STATUS_AVAILABLE
        if not order.delivered_at:
            order.delivered_at = datetime.utcnow()

    db.session.commit()
    flash(f'Order {order.order_number} → {assignment.label}', 'success')

    if new_status == 'delivered':
        return redirect(url_for('delivery.dashboard'))
    return redirect(url_for('delivery.order_detail', assignment_id=assignment_id))


# ── Quick Scan / Search ───────────────────────────────────────────────────────

@delivery_bp.route('/scan', methods=['GET', 'POST'])
@delivery_required
def scan():
    partner = _get_partner()
    result  = None
    if request.method == 'POST' or request.args.get('q'):
        q = (request.form.get('q') or request.args.get('q', '')).strip().upper()
        if q:
            order = Order.query.filter_by(order_number=q).first()
            if order:
                result = {'order': order,
                          'assignment': order.delivery_assignment}
            else:
                flash(f'No order found for "{q}".', 'warning')

    return render_template('delivery/scan.html', partner=partner, result=result)



# ── Available Orders (rider self-picks) ───────────────────────────────────────

@delivery_bp.route('/available')
@delivery_required
def available_orders():
    """Unassigned orders the rider can claim."""
    partner = _get_partner()
    if not partner.is_active:
        flash('Your account is inactive. Contact admin to activate.', 'danger')
        return redirect(url_for('delivery.dashboard'))

    # Orders that are confirmed/processing but have NO active delivery assignment
    from models.order import OrderItem
    from models.product import Product

    from sqlalchemy import select
    assigned_order_ids = select(DeliveryAssignment.order_id).where(
        DeliveryAssignment.status.notin_(['delivered','failed','returned','cancelled'])
    )

    orders = (Order.query
              .filter(
                  Order.status.in_(['confirmed','processing','handed_to_courier','in_transit']),
                  Order.payment_status.in_(['paid','cod']),
                  ~Order.id.in_(assigned_order_ids),
              )
              .order_by(Order.created_at.asc())
              .limit(30).all())

    # Pre-load items list (dynamic relationship can't use |length in template)
    orders_with_items = [(o, o.items.all()) for o in orders]
    return render_template('delivery/available_orders.html',
                           partner=partner, orders_with_items=orders_with_items)


@delivery_bp.route('/available/<int:order_id>/claim', methods=['POST'])
@delivery_required
def claim_order(order_id):
    """Rider self-assigns an unassigned order."""
    partner = _get_partner()
    if not partner.is_active:
        flash('Account inactive.', 'danger')
        return redirect(url_for('delivery.available_orders'))

    order = Order.query.get_or_404(order_id)

    # Check not already assigned
    existing = DeliveryAssignment.query.filter(
        DeliveryAssignment.order_id == order_id,
        DeliveryAssignment.status.notin_(['delivered','failed','returned','cancelled'])
    ).first()
    if existing:
        flash('This order was already claimed by another rider.', 'warning')
        return redirect(url_for('delivery.available_orders'))

    assignment = DeliveryAssignment(
        order_id=order.id,
        partner_id=partner.id,
        status='assigned',
        assigned_at=datetime.utcnow(),
    )
    db.session.add(assignment)

    order.status = 'handed_to_courier'
    OrderTracking.log(
        order_id=order.id, status='handed_to_courier',
        message=f'Picked up by {partner.user.full_name}.',
        location=partner.area or '',
    )
    partner.status = 'busy'
    db.session.commit()

    flash(f'Order {order.order_number} claimed successfully!', 'success')
    return redirect(url_for('delivery.order_detail', assignment_id=assignment.id))



# ── Profile ───────────────────────────────────────────────────────────────────

@delivery_bp.route('/profile', methods=['GET', 'POST'])
@delivery_required
def profile():
    partner = _get_partner()
    if request.method == 'POST':
        partner.phone        = request.form.get('phone', '').strip()
        partner.vehicle_type = request.form.get('vehicle_type', partner.vehicle_type)
        partner.vehicle_no   = request.form.get('vehicle_no', '').strip().upper()
        partner.area         = request.form.get('area', '').strip()
        status = request.form.get('status', partner.status)
        if status in [DeliveryPartner.STATUS_AVAILABLE,
                      DeliveryPartner.STATUS_BUSY,
                      DeliveryPartner.STATUS_OFFLINE]:
            partner.status = status
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('delivery.profile'))
    return render_template('delivery/profile.html', partner=partner)


# ─── Admin: Assign order to delivery partner ─────────────────────────────────

@delivery_bp.route('/admin/assign', methods=['POST'])
@login_required
def admin_assign():
    if not current_user.is_admin:
        abort(403)

    order_id   = request.form.get('order_id', type=int)
    partner_id = request.form.get('partner_id', type=int)

    if not order_id or not partner_id:
        flash('Order and delivery partner are required.', 'danger')
        return redirect(request.referrer or url_for('admin.orders'))

    order   = Order.query.get_or_404(order_id)
    partner = DeliveryPartner.query.get_or_404(partner_id)

    # Remove any existing active assignment
    existing = DeliveryAssignment.query.filter_by(order_id=order_id).first()
    if existing:
        db.session.delete(existing)

    assignment = DeliveryAssignment(
        order_id   = order_id,
        partner_id = partner_id,
    )
    db.session.add(assignment)

    # Log tracking event
    OrderTracking.log(
        order_id=order_id,
        status='handed_to_courier',
        message=f'Assigned to delivery partner {partner.user.full_name}.',
        created_by=current_user.id,
    )
    order.status = 'shipped'
    db.session.commit()

    flash(f'Order {order.order_number} assigned to {partner.user.full_name}.', 'success')
    return redirect(request.referrer or url_for('admin.orders'))
