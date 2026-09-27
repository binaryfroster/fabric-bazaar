"""
Company (Seller) routes — profile setup, dashboard, product management.
All routes require login + is_company role.
"""
import os, uuid
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models.company import Company
from models.product import Product, FABRIC_CATEGORIES, MATERIALS, SIZES, COLORS
from models.order import Order, OrderItem, OrderTracking
from forms.company_forms import CompanyProfileForm
from forms.product_forms import ProductForm

company_bp = Blueprint('company', __name__)


def company_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_company:
            flash('This area is for registered sellers only.', 'warning')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


# ── Profile Setup (first time) ───────────────────────────────────────────────

@company_bp.route('/setup', methods=['GET', 'POST'])
@company_required
def setup_profile():
    # If already set up, go to dashboard
    if current_user.company:
        return redirect(url_for('company.dashboard'))

    form = CompanyProfileForm()
    if form.validate_on_submit():
        slug = _make_slug(form.name.data)
        comp = Company(
            user_id=current_user.id,
            name=form.name.data.strip(),
            slug=slug,
            tagline=(form.tagline.data or '').strip() or None,
            description=form.description.data.strip(),
            business_type=form.business_type.data or None,
            established_year=form.established_year.data,
            phone=(form.phone.data or '').strip() or None,
            whatsapp=(form.whatsapp.data or '').strip() or None,
            email=(form.email.data or '').strip() or None,
            website=(form.website.data or '').strip() or None,
            address_line1=(form.address_line1.data or '').strip() or None,
            address_line2=(form.address_line2.data or '').strip() or None,
            city=(form.city.data or '').strip() or None,
            state=form.state.data or None,
            postal_code=(form.postal_code.data or '').strip() or None,
            gst_number=(form.gst_number.data or '').strip() or None,
            pan_number=(form.pan_number.data or '').strip() or None,
        )
        comp.logo   = _save_image(form.logo,   'companies') or None
        comp.banner = _save_image(form.banner, 'companies') or None

        db.session.add(comp)
        db.session.commit()
        flash('Company profile created! You can now add your products.', 'success')
        return redirect(url_for('company.dashboard'))

    return render_template('company/setup_profile.html', form=form)


# ── Dashboard ────────────────────────────────────────────────────────────────

@company_bp.route('/dashboard')
@company_required
def dashboard():
    comp = current_user.company
    if not comp:
        return redirect(url_for('company.setup_profile'))

    stats = {
        'total_products': comp.products.count(),
        'active_products': comp.products.filter_by(is_active=True).count(),
        'out_of_stock': comp.products.filter(Product.stock == 0, Product.is_active == True).count(),
    }
    recent_products = comp.products.order_by(Product.created_at.desc()).limit(5).all()

    # Orders for this company's products
    recent_orders = (Order.query
                     .join(OrderItem)
                     .join(Product)
                     .filter(Product.company_id == comp.id)
                     .order_by(Order.created_at.desc())
                     .limit(8).all())

    return render_template('company/dashboard.html',
                           comp=comp, stats=stats,
                           recent_products=recent_products,
                           recent_orders=recent_orders)


# ── Edit Profile ─────────────────────────────────────────────────────────────

@company_bp.route('/profile/edit', methods=['GET', 'POST'])
@company_required
def edit_profile():
    comp = current_user.company
    if not comp:
        return redirect(url_for('company.setup_profile'))

    form = CompanyProfileForm(obj=comp)
    if form.validate_on_submit():
        comp.name          = form.name.data.strip()
        comp.tagline       = (form.tagline.data or '').strip() or None
        comp.description   = form.description.data.strip()
        comp.business_type = form.business_type.data or None
        comp.established_year = form.established_year.data
        comp.phone         = (form.phone.data or '').strip() or None
        comp.whatsapp      = (form.whatsapp.data or '').strip() or None
        comp.email         = (form.email.data or '').strip() or None
        comp.website       = (form.website.data or '').strip() or None
        comp.address_line1 = (form.address_line1.data or '').strip() or None
        comp.address_line2 = (form.address_line2.data or '').strip() or None
        comp.city          = (form.city.data or '').strip() or None
        comp.state         = form.state.data or None
        comp.postal_code   = (form.postal_code.data or '').strip() or None
        comp.gst_number    = (form.gst_number.data or '').strip() or None
        comp.pan_number    = (form.pan_number.data or '').strip() or None

        new_logo   = _save_image(form.logo,   'companies')
        new_banner = _save_image(form.banner, 'companies')
        if new_logo:   comp.logo   = new_logo
        if new_banner: comp.banner = new_banner

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('company.view_profile'))

    return render_template('company/edit_profile.html', form=form, comp=comp)


# ── Public Profile ───────────────────────────────────────────────────────────

@company_bp.route('/profile')
@company_required
def view_profile():
    comp = current_user.company
    if not comp:
        return redirect(url_for('company.setup_profile'))
    return render_template('company/view_profile.html', comp=comp)


# ── Products ─────────────────────────────────────────────────────────────────

@company_bp.route('/products')
@company_required
def products():
    comp = current_user.company
    if not comp:
        return redirect(url_for('company.setup_profile'))
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '')
    query = comp.products
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('company/products.html',
                           comp=comp, products=pagination, q=q)


@company_bp.route('/products/add', methods=['GET', 'POST'])
@company_required
def add_product():
    comp = current_user.company
    if not comp:
        return redirect(url_for('company.setup_profile'))

    form = ProductForm()
    if form.validate_on_submit():
        slug = _make_product_slug(form.name.data, comp.id)
        product = Product(
            name=form.name.data.strip(),
            slug=slug,
            description=form.description.data.strip(),
            details=(form.details.data or '').strip() or None,
            price=form.price.data,
            sale_price=form.sale_price.data or None,
            sku=(form.sku.data or '').strip() or None,
            fabric_type=form.fabric_type.data or None,
            material=form.material.data or None,
            color=form.color.data or None,
            size=form.size.data or None,
            pattern=(form.pattern.data or '').strip() or None,
            thread_count=form.thread_count.data,
            care_instructions=(form.care_instructions.data or '').strip() or None,
            stock=form.stock.data,
            min_order_qty=form.min_order_qty.data or 1,
            is_featured=form.is_featured.data,
            is_new=form.is_new.data,
            is_bestseller=form.is_bestseller.data,
            company_id=comp.id,
        )
        product.image   = _save_image(form.image,   'products')
        product.image_2 = _save_image(form.image_2, 'products')
        product.image_3 = _save_image(form.image_3, 'products')
        product.image_4 = _save_image(form.image_4, 'products')

        db.session.add(product)
        db.session.commit()
        flash(f'Product "{product.name}" added successfully!', 'success')
        return redirect(url_for('company.products'))

    from models.category import Category
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template('company/product_form.html', form=form, comp=comp,
                           title='Add Product', action='add', categories=categories)


@company_bp.route('/products/<int:pid>/edit', methods=['GET', 'POST'])
@company_required
def edit_product(pid):
    comp = current_user.company
    product = Product.query.filter_by(id=pid, company_id=comp.id).first_or_404()

    form = ProductForm(obj=product)
    if form.validate_on_submit():
        product.name        = form.name.data.strip()
        product.description = form.description.data.strip()
        product.details     = (form.details.data or '').strip() or None
        product.price       = form.price.data
        product.sale_price  = form.sale_price.data or None
        product.sku         = (form.sku.data or '').strip() or None
        product.fabric_type = form.fabric_type.data or None
        product.material    = form.material.data or None
        product.color       = form.color.data or None
        product.size        = form.size.data or None
        product.pattern     = (form.pattern.data or '').strip() or None
        product.thread_count = form.thread_count.data
        product.care_instructions = (form.care_instructions.data or '').strip() or None
        product.stock       = form.stock.data
        product.min_order_qty = form.min_order_qty.data or 1
        product.is_featured = form.is_featured.data
        product.is_new      = form.is_new.data
        product.is_bestseller = form.is_bestseller.data

        new = _save_image(form.image,   'products')
        if new: product.image = new
        new = _save_image(form.image_2, 'products')
        if new: product.image_2 = new
        new = _save_image(form.image_3, 'products')
        if new: product.image_3 = new
        new = _save_image(form.image_4, 'products')
        if new: product.image_4 = new

        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('company.products'))

    from models.category import Category
    categories = Category.query.order_by(Category.sort_order).all()
    return render_template('company/product_form.html', form=form, comp=comp,
                           product=product, title='Edit Product', action='edit',
                           categories=categories)


@company_bp.route('/products/<int:pid>/toggle', methods=['POST'])
@company_required
def toggle_product(pid):
    comp = current_user.company
    product = Product.query.filter_by(id=pid, company_id=comp.id).first_or_404()
    product.is_active = not product.is_active
    db.session.commit()
    status = 'listed' if product.is_active else 'unlisted'
    flash(f'"{product.name}" is now {status}.', 'info')
    return redirect(url_for('company.products'))


@company_bp.route('/products/<int:pid>/delete', methods=['POST'])
@company_required
def delete_product(pid):
    comp = current_user.company
    product = Product.query.filter_by(id=pid, company_id=comp.id).first_or_404()
    product.is_active = False
    db.session.commit()
    flash(f'"{product.name}" removed from marketplace.', 'info')
    return redirect(url_for('company.products'))


# ── Orders ───────────────────────────────────────────────────────────────────

@company_bp.route('/orders')
@company_required
def orders():
    comp = current_user.company
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    q = (Order.query
         .join(OrderItem)
         .join(Product)
         .filter(Product.company_id == comp.id)
         .distinct())
    if status_filter:
        q = q.filter(Order.status == status_filter)
    orders = q.order_by(Order.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('company/orders.html', comp=comp, orders=orders, status_filter=status_filter)




@company_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@company_required
def cancel_order(order_id):
    """Seller cancels an order for their product."""
    from models.order import Order, OrderItem
    comp = current_user.company
    # Verify this order contains the seller's products
    order = (Order.query.join(OrderItem).join(Product)
             .filter(Product.company_id == comp.id, Order.id == order_id)
             .first_or_404())
    if order.status in ('delivered', 'cancelled', 'refunded'):
        flash(f'Cannot cancel a {order.status} order.', 'warning')
    else:
        # Restore stock
        for item in order.items:
            if item.product_id:
                p = Product.query.get(item.product_id)
                if p and p.company_id == comp.id:
                    p.stock += item.quantity
        order.status = 'cancelled'
        order.notes  = (order.notes or '') + f'\nCancelled by seller {comp.name}.'
        OrderTracking.log(order_id=order.id, status='cancelled',
                          message=f'Order cancelled by seller {comp.name}.',
                          created_by=current_user.id)
        db.session.commit()
        flash(f'Order {order.order_number} has been cancelled.', 'success')
    return redirect(url_for('company.orders'))

# ── Helpers ──────────────────────────────────────────────────────────────────


@company_bp.route('/orders/<int:order_id>/confirm', methods=['POST'])
@company_required
def confirm_order(order_id):
    comp  = current_user.company
    order = Order.query.get_or_404(order_id)
    if order.status != 'pending':
        flash('Order cannot be confirmed.', 'warning')
        return redirect(url_for('company.orders'))
    order.status = 'confirmed'
    OrderTracking.log(order_id=order.id, status='confirmed',
                      message=f'Order confirmed by {comp.name}.')
    db.session.commit()
    flash(f'Order {order.order_number} confirmed.', 'success')
    return redirect(url_for('company.orders'))


@company_bp.route('/orders/<int:order_id>/processing', methods=['POST'])
@company_required
def mark_processing(order_id):
    comp  = current_user.company
    order = Order.query.get_or_404(order_id)
    if order.status not in ('confirmed', 'pending'):
        flash('Order cannot be marked as packed.', 'warning')
        return redirect(url_for('company.orders'))
    order.status = 'processing'
    OrderTracking.log(order_id=order.id, status='processing',
                      message=f'Packed and ready for pickup by {comp.name}.')
    db.session.commit()
    flash(f'Order {order.order_number} marked as packed.', 'success')
    return redirect(url_for('company.orders'))



@company_bp.route('/orders/<int:order_id>/ship', methods=['POST'])
@company_required
def ship_order(order_id):
    comp  = current_user.company
    order = Order.query.get_or_404(order_id)
    if order.status not in ('processing', 'confirmed', 'pending'):
        flash('Order cannot be marked as shipped.', 'warning')
        return redirect(url_for('company.orders'))
    order.status = 'shipped'
    tracking_num = request.form.get('tracking_number', '').strip()
    if tracking_num:
        order.tracking_number = tracking_num
    OrderTracking.log(order_id=order.id, status='out_for_delivery',
                      message=f'Order dispatched by {comp.name}. Out for delivery.')
    db.session.commit()
    flash(f'Order {order.order_number} marked as shipped.', 'success')
    return redirect(url_for('company.orders'))


@company_bp.route('/orders/<int:order_id>/deliver', methods=['POST'])
@company_required
def deliver_order(order_id):
    comp  = current_user.company
    order = Order.query.get_or_404(order_id)
    if order.status in ('delivered', 'cancelled', 'refunded'):
        flash(f'Order is already {order.status}.', 'warning')
        return redirect(url_for('company.orders'))
    from datetime import datetime
    order.status = 'delivered'
    order.payment_status = 'paid'
    if not order.delivered_at:
        order.delivered_at = datetime.utcnow()
    OrderTracking.log(order_id=order.id, status='delivered',
                      message=f'Order delivered successfully.')
    db.session.commit()
    flash(f'Order {order.order_number} marked as delivered.', 'success')
    return redirect(url_for('company.orders'))


def _make_slug(name):
    import re
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    base = slug
    counter = 1
    from models.company import Company
    while Company.query.filter_by(slug=slug).first():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def _make_product_slug(name, company_id):
    import re
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    slug = f'{slug}-{company_id}'
    base = slug
    counter = 1
    while Product.query.filter_by(slug=slug).first():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def _save_image(field, subfolder):
    """Validate and persist an uploaded image via the shared storage layer.

    Returns a public URL (object storage) or bare filename (local static),
    or None when nothing usable was uploaded. Works on read-only serverless
    filesystems when OBJECT_STORAGE_* is configured.
    """
    if not (field and getattr(field, 'data', None)):
        return None
    from storage import save_upload
    return save_upload(field.data, subfolder)
