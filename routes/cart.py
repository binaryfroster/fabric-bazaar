"""
Cart routes — dual-mode cart:
  • Logged-in users  → CartItem rows in DB (persisted)
  • Guest users      → Flask session dict  (temporary)
"""

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, jsonify)
from flask_login import login_required, current_user
from extensions import db, limiter
from models.product import Product
from models.cart import CartItem

cart_bp = Blueprint('cart', __name__)

# ── View cart ─────────────────────────────────────────────────────────────────

@cart_bp.route('/')
def view_cart():
    cart_items, subtotal = _get_cart()
    shipping = _calc_shipping(subtotal)
    total    = subtotal + shipping
    return render_template('cart.html',
                           cart_items=cart_items,
                           subtotal=subtotal,
                           shipping=shipping,
                           total=total)


# ── Add to cart ───────────────────────────────────────────────────────────────

@cart_bp.route('/add/<int:product_id>', methods=['POST'])
@limiter.limit('30 per minute')
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)

    if not product.in_stock:
        flash(f'Sorry, "{product.name}" is currently out of stock.', 'warning')
        return redirect(request.referrer or url_for('shop.index'))

    moq = product.min_order_qty or 1
    qty = int(request.form.get('quantity', moq))
    qty = max(moq, min(qty, product.stock))        # clamp moq..stock
    if qty < moq:
        flash(f'Minimum order quantity for "{product.name}" is {moq}.', 'warning')
        return redirect(request.referrer or url_for('shop.index'))

    if current_user.is_authenticated:
        _db_add(current_user.id, product_id, qty)
    else:
        _session_add(product_id, qty)

    flash(f'"{product.name}" added to your cart.', 'success')

    # AJAX-friendly: if request wants JSON, return cart count
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        count = _get_cart_count()
        return jsonify({'success': True, 'cart_count': count})

    return redirect(request.referrer or url_for('shop.index'))


# ── Update quantity ───────────────────────────────────────────────────────────

@cart_bp.route('/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    qty = int(request.form.get('quantity', 1))
    product = Product.query.get(product_id)
    moq = (product.min_order_qty or 1) if product else 1

    if qty <= 0:
        return redirect(url_for('cart.remove_from_cart', product_id=product_id))

    if qty < moq:
        qty = moq
        flash(f'Minimum order quantity is {moq} for this product.', 'warning')

    if current_user.is_authenticated:
        item = CartItem.query.filter_by(
            user_id=current_user.id, product_id=product_id).first()
        if item:
            item.quantity = max(moq, min(qty, product.stock if product else qty))
            db.session.commit()
    else:
        cart = session.get('cart', {})
        if str(product_id) in cart:
            cart[str(product_id)] = qty
            session['cart'] = cart

    flash('Cart updated.', 'info')
    return redirect(url_for('cart.view_cart'))


# ── Remove item ───────────────────────────────────────────────────────────────

@cart_bp.route('/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if current_user.is_authenticated:
        CartItem.query.filter_by(
            user_id=current_user.id, product_id=product_id).delete()
        db.session.commit()
    else:
        cart = session.get('cart', {})
        cart.pop(str(product_id), None)
        session['cart'] = cart

    flash('Item removed from cart.', 'info')
    return redirect(url_for('cart.view_cart'))


# ── Clear entire cart ─────────────────────────────────────────────────────────

@cart_bp.route('/clear', methods=['POST'])
def clear_cart():
    if current_user.is_authenticated:
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    else:
        session.pop('cart', None)
    return redirect(url_for('cart.view_cart'))


# ── Cart count (AJAX endpoint) ────────────────────────────────────────────────

@cart_bp.route('/count')
def cart_count():
    return jsonify({'count': _get_cart_count()})


# ── Private helpers ───────────────────────────────────────────────────────────

def _db_add(user_id: int, product_id: int, qty: int):
    """Add/increment item in DB cart."""
    item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if item:
        product = Product.query.get(product_id)
        max_qty = product.stock if product else 99
        item.quantity = min(item.quantity + qty, max_qty)
    else:
        db.session.add(CartItem(user_id=user_id, product_id=product_id, quantity=qty))
    db.session.commit()


def _session_add(product_id: int, qty: int):
    """Add/increment item in session cart."""
    cart = session.get('cart', {})
    key  = str(product_id)
    cart[key] = cart.get(key, 0) + qty
    session['cart'] = cart


def _get_cart():
    """
    Returns (list_of_dicts, subtotal_float) for the current visitor.
    Each dict has: product, quantity, subtotal keys.
    """
    items    = []
    subtotal = 0.0

    if current_user.is_authenticated:
        db_items = (CartItem.query
                    .filter_by(user_id=current_user.id)
                    .join(Product)
                    .all())
        for ci in db_items:
            line = ci.subtotal
            subtotal += line
            items.append({
                'product':  ci.product,
                'quantity': ci.quantity,
                'subtotal': line,
            })
    else:
        cart = session.get('cart', {})
        for pid_str, qty in cart.items():
            product = Product.query.get(int(pid_str))
            if product and product.is_active:
                line     = float(product.display_price) * qty
                subtotal += line
                items.append({
                    'product':  product,
                    'quantity': qty,
                    'subtotal': line,
                })

    return items, subtotal


def _get_cart_count():
    if current_user.is_authenticated:
        return CartItem.query.filter_by(user_id=current_user.id).count()
    cart = session.get('cart', {})
    return sum(cart.values())


def _calc_shipping(subtotal: float) -> float:
    """Free shipping over R800, else flat R99."""
    if subtotal >= 800:
        return 0.0
    return 99.0 if subtotal > 0 else 0.0


@cart_bp.route('/add-multiple', methods=['POST'])
@login_required
def add_multiple():
    """Re-order: add multiple products back to cart at once."""
    from flask import request, redirect, url_for, flash
    product_ids = request.form.getlist('product_ids')
    quantities  = request.form.getlist('quantities')
    added = 0
    for pid_str, qty_str in zip(product_ids, quantities):
        try:
            pid = int(pid_str)
            qty = max(1, int(qty_str))
            product = Product.query.get(pid)
            if not product or not product.is_active:
                continue
            if current_user.is_authenticated:
                ci = CartItem.query.filter_by(
                    user_id=current_user.id, product_id=pid).first()
                if ci:
                    ci.quantity += qty
                else:
                    db.session.add(CartItem(
                        user_id=current_user.id, product_id=pid, quantity=qty))
            added += 1
        except (ValueError, TypeError):
            continue
    db.session.commit()
    if added:
        flash(f'{added} item{"s" if added != 1 else ""} added to cart!', 'success')
    return redirect(url_for('cart.view_cart'))
