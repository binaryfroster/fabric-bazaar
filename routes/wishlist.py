"""Wishlist — save products for later."""
from flask import Blueprint, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.wishlist import WishlistItem
from models.product import Product

wishlist_bp = Blueprint('wishlist', __name__)


@wishlist_bp.route('/wishlist/toggle/<int:product_id>', methods=['POST'])
@login_required
def toggle(product_id):
    if not current_user.is_customer:
        return jsonify({'error': 'Customers only'}), 403

    product = Product.query.get_or_404(product_id)
    existing = WishlistItem.query.filter_by(
        user_id=current_user.id, product_id=product_id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        added = False
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
        db.session.commit()
        added = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        count = WishlistItem.query.filter_by(user_id=current_user.id).count()
        return jsonify({'added': added, 'count': count})

    msg = f'"{product.name}" {"added to" if added else "removed from"} your wishlist.'
    flash(msg, 'success')
    return redirect(request.referrer or url_for('wishlist.view'))


@wishlist_bp.route('/wishlist')
@login_required
def view():
    items = (WishlistItem.query
             .filter_by(user_id=current_user.id)
             .order_by(WishlistItem.created_at.desc()).all())
    return __import__('flask').render_template('wishlist.html', items=items)


@wishlist_bp.route('/wishlist/remove/<int:item_id>', methods=['POST'])
@login_required
def remove(item_id):
    item = WishlistItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash('Not allowed.', 'danger')
        return redirect(url_for('wishlist.view'))
    db.session.delete(item)
    db.session.commit()
    flash('Removed from wishlist.', 'info')
    return redirect(url_for('wishlist.view'))
