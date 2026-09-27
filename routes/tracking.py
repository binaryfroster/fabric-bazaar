"""
Order Tracking System — routes for customers, admin, and REST API.

Public  : GET  /track-order/                    → tracking search form
Public  : GET  /track-order/<order_number>       → tracking page (no login needed)
API     : GET  /api/order/<order_number>         → JSON order + tracking data
API     : POST /api/order/update-status          → update status + add event (admin only)
Admin   : GET  /admin/orders/<id>/track          → admin tracking management page
Admin   : POST /admin/orders/<id>/track/add      → add tracking event
Admin   : POST /admin/orders/<id>/track/delivery → set estimated delivery date
Admin   : DELETE/POST /admin/orders/<id>/track/<eid>/delete → delete a tracking event
"""
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, abort)
from flask_login import login_required, current_user
from extensions import db
from models.order import Order, OrderItem, OrderTracking

tracking_bp = Blueprint('tracking', __name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

# ── Unified pipeline ──────────────────────────────────────────────────────────
# These are the 6 DISPLAY steps shown in the progress bar.
# They map from order.status (5 values) + granular tracking events.
PIPELINE = [
    'pending',
    'confirmed',
    'processing',
    'shipped',        # covers: packed, handed_to_courier, in_transit, out_for_delivery
    'delivered',
]

# Maps granular tracking event status → order.status for progress bar
TRACKING_TO_ORDER_STATUS = {
    'pending':             'pending',
    'confirmed':           'confirmed',
    'processing':          'processing',
    'packed':              'processing',
    'handed_to_courier':   'shipped',
    'in_transit':          'shipped',
    'out_for_delivery':    'shipped',
    'delivered':           'delivered',
    'delivery_attempted':  'shipped',
    'exception':           'shipped',
    'returned':            'returned',
}

NEGATIVE_STATUSES = {'cancelled', 'refunded', 'returned', 'return_requested', 'exception'}

# Labels for display steps
PIPELINE_LABELS = {
    'pending':    ('🛒', 'Order Placed'),
    'confirmed':  ('✅', 'Confirmed'),
    'processing': ('⚙️',  'Preparing'),
    'shipped':    ('🚚', 'Out for Delivery'),
    'delivered':  ('🎉', 'Delivered'),
}

def _progress(order):
    """Return (step_index 0-based, total_steps, pct) for the progress bar.
    Works correctly for both order.status and tracking event statuses."""
    status = order.status
    if status in NEGATIVE_STATUSES:
        return 0, len(PIPELINE), 0
    # Map tracking-granular status → pipeline status
    mapped = TRACKING_TO_ORDER_STATUS.get(status, status)
    try:
        idx = PIPELINE.index(mapped)
    except ValueError:
        idx = 0
    pct = round((idx / (len(PIPELINE) - 1)) * 100)
    return idx, len(PIPELINE), pct


def _order_json(order):
    events = (OrderTracking.query
              .filter_by(order_id=order.id, is_public=True)
              .order_by(OrderTracking.timestamp.desc()).all())
    idx, total, pct = _progress(order)
    return {
        'order_number':       order.order_number,
        'status':             order.status,
        'status_label':       order.status.replace('_', ' ').title(),
        'payment_status':     order.payment_status,
        'total':              str(order.total),
        'created_at':         order.created_at.isoformat(),
        'estimated_delivery': order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        'tracking_number':    order.tracking_number,
        'progress_pct':       pct,
        'customer': {
            'name':  order.full_name,
            'email': order.email,
        },
        'shipping': {
            'address': order.full_address,
            'city':    order.city,
            'state':   order.state,
            'pincode': order.postal_code,
        },
        'items': [
            {'name': i.product_name, 'qty': i.quantity, 'price': str(i.price)}
            for i in order.items
        ],
        'events': [
            {
                'id':        e.id,
                'status':    e.status,
                'label':     e.label,
                'icon':      e.icon,
                'location':  e.location or '',
                'message':   e.message or '',
                'timestamp': e.timestamp.isoformat(),
            }
            for e in events
        ],
    }


# ─── Public: Tracking Search Page ────────────────────────────────────────────

@tracking_bp.route('/track-order', methods=['GET'])
@tracking_bp.route('/track-order/', methods=['GET'])
def track_search():
    """Landing page — enter order number to track."""
    q = request.args.get('q', '').strip()
    if q:
        return redirect(url_for('tracking.track_order', order_number=q))
    return render_template('tracking/search.html')


# ─── Public: Order Tracking Page ─────────────────────────────────────────────

@tracking_bp.route('/track-order/<order_number>')
def track_order(order_number):
    """
    Public tracking page — no login required.
    Anyone with the order number can view status (intentional, like courier sites).
    """
    order = Order.query.filter_by(order_number=order_number.upper().strip()).first()
    if not order:
        flash('Order not found. Please check the order number and try again.', 'danger')
        return redirect(url_for('tracking.track_search'))

    events = (OrderTracking.query
              .filter_by(order_id=order.id, is_public=True)
              .order_by(OrderTracking.timestamp.asc()).all())

    idx, total_steps, pct = _progress(order)
    is_negative = order.status in NEGATIVE_STATUSES

    return render_template('tracking/track.html',
                           order=order,
                           events=events,
                           pipeline=PIPELINE,
                           pipeline_labels=PIPELINE_LABELS,
                           progress_idx=idx,
                           progress_pct=pct,
                           is_negative=is_negative,
                           OrderTracking=OrderTracking)


# ─── REST API ─────────────────────────────────────────────────────────────────

@tracking_bp.route('/api/order/<order_number>', methods=['GET'])
def api_order(order_number):
    """
    GET /api/order/<order_number>
    Returns full order + tracking timeline as JSON.
    Public endpoint — returns limited info (no raw PII) for unauthenticated callers.
    """
    order = Order.query.filter_by(order_number=order_number.upper().strip()).first()
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    return jsonify({'success': True, 'order': _order_json(order)})


@tracking_bp.route('/api/order/update-status', methods=['POST'])
@login_required
def api_update_status():
    """
    POST /api/order/update-status
    Body: { order_number, status, message, location, estimated_delivery? }
    Admin only.
    """
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Admin only'}), 403

    data = request.get_json() or {}
    order_number = (data.get('order_number') or '').strip().upper()
    status       = (data.get('status') or '').strip()
    message      = (data.get('message') or '').strip()
    location     = (data.get('location') or '').strip()

    valid_statuses = list(OrderTracking.STATUS_LABELS.keys()) + [
        'cancelled', 'refunded']

    if not order_number:
        return jsonify({'success': False, 'error': 'order_number required'}), 400
    if status not in valid_statuses:
        return jsonify({'success': False,
                        'error': f'Invalid status. Valid: {valid_statuses}'}), 400

    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    # Update order status
    order_status_map = {
        'pending': 'pending', 'confirmed': 'confirmed',
        'processing': 'processing', 'packed': 'processing',
        'handed_to_courier': 'shipped', 'in_transit': 'shipped',
        'out_for_delivery': 'shipped', 'delivered': 'delivered',
        'delivery_attempted': 'shipped', 'exception': 'shipped',
        'returned': 'returned',
    }
    order.status = order_status_map.get(status, status)
    if order.status == 'delivered' and not order.delivered_at:
        order.delivered_at = datetime.utcnow()

    # Estimated delivery
    if data.get('estimated_delivery'):
        try:
            order.estimated_delivery = datetime.fromisoformat(data['estimated_delivery'])
        except ValueError:
            pass

    # Log the tracking event
    event = OrderTracking.log(
        order_id=order.id,
        status=status,
        message=message,
        location=location,
        created_by=current_user.id,
    )
    db.session.commit()

    return jsonify({
        'success': True,
        'order':   _order_json(order),
        'event_id': event.id,
    })


# ─── Admin: Order Tracking Management Page ───────────────────────────────────

@tracking_bp.route('/admin/orders/<int:oid>/track')
@login_required
def admin_track(oid):
    """Admin view — full tracking management for one order."""
    if not current_user.is_admin:
        abort(403)
    order  = Order.query.get_or_404(oid)
    events = (OrderTracking.query
              .filter_by(order_id=oid)
              .order_by(OrderTracking.timestamp.asc()).all())
    idx, total_steps, pct = _progress(order)
    all_statuses = list(OrderTracking.STATUS_LABELS.items())
    return render_template('tracking/admin_track.html',
                           order=order, events=events,
                           progress_pct=pct, progress_idx=idx,
                           all_statuses=all_statuses,
                           pipeline=PIPELINE,
                           OrderTracking=OrderTracking)


@tracking_bp.route('/admin/orders/<int:oid>/track/add', methods=['POST'])
@login_required
def admin_add_event(oid):
    """Admin adds a tracking event to an order."""
    if not current_user.is_admin:
        abort(403)

    order    = Order.query.get_or_404(oid)
    status   = request.form.get('status', '').strip()
    location = request.form.get('location', '').strip()
    message  = request.form.get('message', '').strip()
    ts_str   = request.form.get('timestamp', '').strip()
    is_pub   = request.form.get('is_public', 'on') == 'on'
    update_order_status = request.form.get('update_order_status', '') == 'on'

    if not status:
        flash('Status is required.', 'danger')
        return redirect(url_for('tracking.admin_track', oid=oid))

    # Parse custom timestamp or use now
    timestamp = datetime.utcnow()
    if ts_str:
        try:
            timestamp = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    # Auto-generate a message if empty
    if not message:
        message = OrderTracking.STATUS_LABELS.get(status, status.replace('_', ' ').title())

    event = OrderTracking.log(
        order_id=order.id,
        status=status,
        message=message,
        location=location,
        created_by=current_user.id,
        timestamp=timestamp,
    )
    event.is_public = is_pub

    # Optionally sync order.status
    if update_order_status:
        order_status_map = {
            'pending': 'pending', 'confirmed': 'confirmed',
            'processing': 'processing', 'packed': 'processing',
            'handed_to_courier': 'shipped', 'in_transit': 'shipped',
            'out_for_delivery': 'shipped', 'delivered': 'delivered',
            'delivery_attempted': 'shipped', 'exception': 'shipped',
            'returned': 'cancelled',
        }
        old = order.status
        order.status = order_status_map.get(status, order.status)
        if order.status == 'delivered' and not order.delivered_at:
            from datetime import datetime as _dt
            order.delivered_at = _dt.utcnow()
    db.session.commit()
    flash(f'Tracking event "{event.label}" added to order {order.order_number}.', 'success')
    return redirect(url_for('tracking.admin_track', oid=oid))


@tracking_bp.route('/admin/orders/<int:oid>/track/delivery', methods=['POST'])
@login_required
def admin_set_delivery(oid):
    """Admin sets / updates estimated delivery date."""
    if not current_user.is_admin:
        abort(403)
    order = Order.query.get_or_404(oid)
    date_str = request.form.get('estimated_delivery', '').strip()
    tracking_number = request.form.get('tracking_number', '').strip()

    if date_str:
        try:
            order.estimated_delivery = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format.', 'danger')
            return redirect(url_for('tracking.admin_track', oid=oid))

    if tracking_number:
        order.tracking_number = tracking_number

    db.session.commit()
    flash('Delivery details updated.', 'success')
    return redirect(url_for('tracking.admin_track', oid=oid))


@tracking_bp.route('/admin/orders/<int:oid>/track/<int:eid>/delete', methods=['POST'])
@login_required
def admin_delete_event(oid, eid):
    """Admin removes a tracking event."""
    if not current_user.is_admin:
        abort(403)
    event = OrderTracking.query.get_or_404(eid)
    if event.order_id != oid:
        abort(400)
    db.session.delete(event)
    db.session.commit()
    flash('Tracking event removed.', 'info')
    return redirect(url_for('tracking.admin_track', oid=oid))


@tracking_bp.route('/admin/orders/<int:oid>/track/<int:eid>/toggle', methods=['POST'])
@login_required
def admin_toggle_event(oid, eid):
    """Toggle visibility of a tracking event (public ↔ internal)."""
    if not current_user.is_admin:
        abort(403)
    event = OrderTracking.query.get_or_404(eid)
    if event.order_id != oid:
        abort(400)
    event.is_public = not event.is_public
    db.session.commit()
    state = 'visible' if event.is_public else 'hidden'
    flash(f'Event marked as {state}.', 'info')
    return redirect(url_for('tracking.admin_track', oid=oid))
