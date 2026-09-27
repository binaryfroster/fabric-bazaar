from datetime import datetime
"""
Ratings & Reviews routes.
- Customers rate sellers and review products.
- Ratings are visible on seller public pages and product pages.
"""
from flask import Blueprint, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.rating import SellerRating, ProductReview
from models.company import Company
from models.product import Product
from models.order import Order, OrderItem

ratings_bp = Blueprint('ratings', __name__)


# ── Rate a Seller ─────────────────────────────────────────────────────────────

@ratings_bp.route('/seller/<int:company_id>/rate', methods=['POST'])
@login_required
def rate_seller(company_id):
    if not current_user.is_customer:
        return jsonify({'error': 'Only customers can leave ratings'}), 403

    comp = Company.query.get_or_404(company_id)

    rating_val = request.form.get('rating', type=int)
    if not rating_val or not (1 <= rating_val <= 5):
        flash('Please select a valid rating (1–5 stars).', 'danger')
        return redirect(url_for('main.seller_detail', slug=comp.slug))

    order_id = request.form.get('order_id', type=int)

    # Check for existing rating on same order (or any if no order)
    existing = SellerRating.query.filter_by(
        company_id=company_id,
        user_id=current_user.id,
        order_id=order_id,
    ).first()

    if existing:
        # Update existing
        existing.rating               = rating_val
        existing.title                = (request.form.get('title') or '').strip() or None
        existing.review               = (request.form.get('review') or '').strip() or None
        existing.quality_rating       = request.form.get('quality_rating', type=int)
        existing.communication_rating = request.form.get('communication_rating', type=int)
        existing.delivery_rating      = request.form.get('delivery_rating', type=int)
        db.session.commit()
        flash('Your rating has been updated!', 'success')
    else:
        # Verify purchase if order_id provided
        verified = False
        if order_id:
            order = Order.query.filter_by(id=order_id, user_id=current_user.id).first()
            if order:
                verified = OrderItem.query.join(Product).filter(
                    OrderItem.order_id == order_id,
                    Product.company_id == company_id
                ).first() is not None

        r = SellerRating(
            company_id=company_id,
            user_id=current_user.id,
            order_id=order_id,
            rating=rating_val,
            title=(request.form.get('title') or '').strip() or None,
            review=(request.form.get('review') or '').strip() or None,
            quality_rating=request.form.get('quality_rating', type=int),
            communication_rating=request.form.get('communication_rating', type=int),
            delivery_rating=request.form.get('delivery_rating', type=int),
            is_verified_purchase=verified,
        )
        db.session.add(r)
        db.session.commit()
        flash('Thank you for your rating!', 'success')

    return redirect(url_for('main.seller_detail', slug=comp.slug))


# ── Review a Product ──────────────────────────────────────────────────────────

@ratings_bp.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def review_product(product_id):
    if not current_user.is_customer:
        return jsonify({'error': 'Only customers can leave reviews'}), 403

    product    = Product.query.get_or_404(product_id)
    rating_val = request.form.get('rating', type=int)

    if not rating_val or not (1 <= rating_val <= 5):
        flash('Please select a valid rating.', 'danger')
        return redirect(url_for('shop.product_detail', slug=product.slug))

    order_id = request.form.get('order_id', type=int)

    # Verify this user actually bought the product
    verified = False
    if current_user.is_authenticated:
        bought = OrderItem.query.join(Order).filter(
            Order.user_id == current_user.id,
            OrderItem.product_id == product_id,
            Order.status.in_(['delivered', 'shipped']),
        ).first()
        verified = bought is not None

    existing = ProductReview.query.filter_by(
        product_id=product_id, user_id=current_user.id, order_id=order_id
    ).first()

    if existing:
        existing.rating  = rating_val
        existing.title   = (request.form.get('title') or '').strip() or None
        existing.review  = (request.form.get('review') or '').strip() or None
        db.session.commit()
        flash('Your review has been updated!', 'success')
    else:
        r = ProductReview(
            product_id=product_id,
            user_id=current_user.id,
            order_id=order_id,
            rating=rating_val,
            title=(request.form.get('title') or '').strip() or None,
            review=(request.form.get('review') or '').strip() or None,
            is_verified_purchase=verified,
        )
        db.session.add(r)
        db.session.commit()
        flash('Your review has been posted!', 'success')

    return redirect(url_for('shop.product_detail', slug=product.slug))


# ── Admin: Approve / Hide Review ──────────────────────────────────────────────

@ratings_bp.route('/admin/seller-rating/<int:rid>/toggle', methods=['POST'])
@login_required
def toggle_seller_rating(rid):
    if not current_user.is_admin:
        return jsonify({'error': 'Forbidden'}), 403
    r = SellerRating.query.get_or_404(rid)
    r.is_approved = not r.is_approved
    db.session.commit()
    flash(f'Rating {"approved" if r.is_approved else "hidden"}.', 'info')
    return redirect(request.referrer or url_for('admin.companies'))


@ratings_bp.route('/admin/product-review/<int:rid>/toggle', methods=['POST'])
@login_required
def toggle_product_review(rid):
    if not current_user.is_admin:
        return jsonify({'error': 'Forbidden'}), 403
    r = ProductReview.query.get_or_404(rid)
    r.is_approved = not r.is_approved
    db.session.commit()
    flash(f'Review {"approved" if r.is_approved else "hidden"}.', 'info')
    return redirect(request.referrer or url_for('admin.products'))


# ── Seller: Reply to a review ─────────────────────────────────────────────────

@ratings_bp.route('/seller-review/<int:rid>/reply', methods=['POST'])
@login_required
def reply_seller_rating(rid):
    """Company owner replies to a seller rating."""
    if not current_user.is_company:
        return jsonify({'error': 'Seller account required'}), 403
    from models.rating import SellerRating
    r = SellerRating.query.get_or_404(rid)
    if r.company_id != current_user.company.id:
        return jsonify({'error': 'Forbidden'}), 403
    reply = (request.form.get('reply') or '').strip()
    if not reply:
        flash('Reply cannot be empty.', 'danger')
        return redirect(request.referrer or url_for('main.seller_detail', slug=current_user.company.slug))
    r.seller_reply = reply
    r.seller_replied_at = datetime.utcnow()
    db.session.commit()
    flash('Reply posted!', 'success')
    return redirect(request.referrer or url_for('main.seller_detail', slug=current_user.company.slug))


@ratings_bp.route('/product-review/<int:rid>/reply', methods=['POST'])
@login_required
def reply_product_review(rid):
    """Company owner replies to a product review."""
    if not current_user.is_company:
        return jsonify({'error': 'Seller account required'}), 403
    from models.rating import ProductReview
    r = ProductReview.query.get_or_404(rid)
    # Verify this product belongs to this seller
    if r.product.company_id != current_user.company.id:
        return jsonify({'error': 'Forbidden'}), 403
    reply = (request.form.get('reply') or '').strip()
    if not reply:
        flash('Reply cannot be empty.', 'danger')
        return redirect(request.referrer or url_for('shop.product_detail', slug=r.product.slug))
    r.seller_reply = reply
    r.seller_replied_at = datetime.utcnow()
    db.session.commit()
    flash('Reply posted on review!', 'success')
    return redirect(request.referrer or url_for('shop.product_detail', slug=r.product.slug))
