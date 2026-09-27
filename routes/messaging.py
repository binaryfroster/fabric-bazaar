"""Buyer ↔ Seller in-platform messaging."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.messaging import MessageThread, Message
from models.company import Company
from models.product import Product

msg_bp = Blueprint('messages', __name__)


def _get_thread_or_404(thread_id):
    thread = MessageThread.query.get_or_404(thread_id)
    # Access control: only the customer or the company's owner can view
    if not (current_user.id == thread.customer_id or
            (current_user.company and current_user.company.id == thread.company_id) or
            current_user.is_admin):
        from flask import abort
        abort(403)
    return thread


# ── Inbox ─────────────────────────────────────────────────────────────────────

@msg_bp.route('/messages')
@login_required
def inbox():
    if current_user.is_customer:
        threads = (MessageThread.query
                   .filter_by(customer_id=current_user.id)
                   .order_by(MessageThread.updated_at.desc()).all())
        unread_total = sum(t.unread_customer for t in threads)
    elif current_user.is_company:
        comp = current_user.company
        threads = (MessageThread.query
                   .filter_by(company_id=comp.id)
                   .order_by(MessageThread.updated_at.desc()).all()) if comp else []
        unread_total = sum(t.unread_seller for t in threads)
    else:
        threads = (MessageThread.query
                   .order_by(MessageThread.updated_at.desc()).limit(50).all())
        unread_total = 0

    return render_template('messages/inbox.html', threads=threads, unread_total=unread_total)


# ── Start a new thread ────────────────────────────────────────────────────────

@msg_bp.route('/messages/new', methods=['GET', 'POST'])
@login_required
def new_thread():
    if not current_user.is_customer:
        flash('Only customers can start conversations.', 'warning')
        return redirect(url_for('messages.inbox'))

    company_id = request.args.get('company_id', type=int) or request.form.get('company_id', type=int)
    product_id = request.args.get('product_id', type=int) or request.form.get('product_id', type=int)
    comp    = Company.query.get_or_404(company_id) if company_id else None
    product = Product.query.get(product_id) if product_id else None

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body    = request.form.get('body', '').strip()
        if not comp:
            comp = Company.query.get_or_404(request.form.get('company_id', type=int))

        if not subject or not body:
            flash('Please fill in both subject and message.', 'danger')
            return redirect(request.url)

        # Check if a thread already exists for this product
        existing = MessageThread.query.filter_by(
            customer_id=current_user.id,
            company_id=comp.id,
            product_id=product_id,
        ).first()

        if existing:
            # Add to existing thread
            _add_message(existing, current_user, body)
            flash('Message sent!', 'success')
            return redirect(url_for('messages.thread', thread_id=existing.id))

        thread = MessageThread(
            customer_id=current_user.id,
            company_id=comp.id,
            product_id=product_id,
            subject=subject,
            unread_seller=1,
        )
        db.session.add(thread)
        db.session.flush()

        msg = Message(thread_id=thread.id, sender_id=current_user.id, body=body)
        db.session.add(msg)
        db.session.commit()
        flash('Message sent to seller!', 'success')
        return redirect(url_for('messages.thread', thread_id=thread.id))

    companies = Company.query.filter_by(is_active=True, is_verified=True).order_by(Company.name).all()
    return render_template('messages/new.html', comp=comp, product=product, companies=companies)


# ── View / reply in a thread ──────────────────────────────────────────────────

@msg_bp.route('/messages/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def thread(thread_id):
    t = _get_thread_or_404(thread_id)

    # Mark messages as read
    if current_user.id == t.customer_id:
        t.unread_customer = 0
        Message.query.filter_by(thread_id=t.id, is_read=False).filter(
            Message.sender_id != current_user.id).update({'is_read': True})
    elif current_user.company and current_user.company.id == t.company_id:
        t.unread_seller = 0
        Message.query.filter_by(thread_id=t.id, is_read=False).filter(
            Message.sender_id != current_user.id).update({'is_read': True})
    db.session.commit()

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not body:
            flash('Message cannot be empty.', 'danger')
            return redirect(url_for('messages.thread', thread_id=t.id))
        _add_message(t, current_user, body)
        flash('Reply sent!', 'success')
        return redirect(url_for('messages.thread', thread_id=t.id))

    messages = t.messages.order_by(Message.created_at.asc()).all()
    return render_template('messages/thread.html', thread=t, messages=messages)


def _add_message(thread, sender, body):
    msg = Message(thread_id=thread.id, sender_id=sender.id, body=body)
    db.session.add(msg)
    # Increment unread counter for the other party
    if sender.id == thread.customer_id:
        thread.unread_seller += 1
    else:
        thread.unread_customer += 1
    thread.updated_at = __import__('datetime').datetime.utcnow()
    db.session.commit()


# ── AJAX: unread count ────────────────────────────────────────────────────────

@msg_bp.route('/messages/unread-count')
@login_required
def unread_count():
    if current_user.is_customer:
        count = db.session.query(db.func.sum(MessageThread.unread_customer)).filter_by(
            customer_id=current_user.id).scalar() or 0
    elif current_user.is_company and current_user.company:
        count = db.session.query(db.func.sum(MessageThread.unread_seller)).filter_by(
            company_id=current_user.company.id).scalar() or 0
    else:
        count = 0
    return jsonify({'count': int(count)})


# ── AJAX: poll for new messages in a thread ───────────────────────────────────

@msg_bp.route('/messages/<int:thread_id>/poll')
@login_required
def poll_messages(thread_id):
    """Return latest message count for polling."""
    t = _get_thread_or_404(thread_id)
    messages = t.messages.order_by(Message.created_at.asc()).all()
    return jsonify({
        'count': len(messages),
        'messages': [{
            'id': m.id,
            'body': m.body,
            'sender': m.sender.first_name,
            'sender_id': m.sender_id,
            'time': m.created_at.strftime('%I:%M %p'),
            'date': m.created_at.strftime('%d %b %Y'),
            'is_read': m.is_read,
        } for m in messages]
    })
