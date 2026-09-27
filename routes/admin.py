"""
Admin routes — full control over the entire marketplace.
Admin can: approve/suspend sellers, edit any company, edit any product,
manage categories, view all users & orders.
"""
import os, uuid, re
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import current_user, login_required
from extensions import db, bcrypt
from models.product import Product, FABRIC_CATEGORIES, MATERIALS, SIZES, COLORS
from models.category import Category
from models.order import Order
from models.user import User
from models.company import Company
from forms.product_forms import ProductForm
from forms.company_forms import CompanyProfileForm

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


# ─── Dashboard ───────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    stats = {
        'total_products':    Product.query.count(),
        'active_products':   Product.query.filter_by(is_active=True).count(),
        'total_orders':      Order.query.count(),
        'pending_orders':    Order.query.filter_by(status='pending').count(),
        'total_users':       User.query.filter_by(role='customer').count(),
        'total_companies':   Company.query.count(),
        'pending_companies': Company.query.filter_by(is_verified=False, is_active=True).count(),
        'low_stock':         Product.query.filter(Product.stock <= 5, Product.is_active == True).count(),
    }
    recent_orders     = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    pending_companies = Company.query.filter_by(is_verified=False, is_active=True).all()
    return render_template('admin/dashboard.html', stats=stats,
                           recent_orders=recent_orders,
                           pending_companies=pending_companies)


# ─── Companies ────────────────────────────────────────────────────────────────

@admin_bp.route('/companies')
@admin_required
def companies():
    page   = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    status = request.args.get('status', '')
    q = Company.query
    if search:
        q = q.filter(Company.name.ilike(f'%{search}%'))
    if status == 'pending':
        q = q.filter_by(is_verified=False, is_active=True)
    elif status == 'verified':
        q = q.filter_by(is_verified=True)
    elif status == 'inactive':
        q = q.filter_by(is_active=False)
    companies = q.order_by(Company.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('admin/companies.html', companies=companies,
                           search=search, status=status)


@admin_bp.route('/companies/<int:cid>')
@admin_required
def company_detail(cid):
    comp = Company.query.get_or_404(cid)
    products = comp.products.order_by(Product.created_at.desc()).all()
    return render_template('admin/company_detail.html', comp=comp, products=products)


@admin_bp.route('/companies/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def edit_company(cid):
    comp = Company.query.get_or_404(cid)
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
        flash(f'Company "{comp.name}" updated.', 'success')
        return redirect(url_for('admin.company_detail', cid=comp.id))
    return render_template('admin/edit_company.html', form=form, comp=comp)


@admin_bp.route('/companies/<int:cid>/verify', methods=['POST'])
@admin_required
def verify_company(cid):
    comp = Company.query.get_or_404(cid)
    comp.is_verified = True
    comp.is_active   = True
    db.session.commit()
    flash(f'✅ "{comp.name}" approved — now live on the marketplace.', 'success')
    return redirect(request.referrer or url_for('admin.companies'))


@admin_bp.route('/companies/<int:cid>/reject', methods=['POST'])
@admin_required
def reject_company(cid):
    comp = Company.query.get_or_404(cid)
    comp.is_verified = False
    comp.is_active   = False
    db.session.commit()
    flash(f'❌ "{comp.name}" rejected and suspended.', 'warning')
    return redirect(request.referrer or url_for('admin.companies'))


@admin_bp.route('/companies/<int:cid>/toggle', methods=['POST'])
@admin_required
def toggle_company(cid):
    comp = Company.query.get_or_404(cid)
    comp.is_active = not comp.is_active
    if not comp.is_active:
        comp.is_verified = False   # Suspend also unverifies
    db.session.commit()
    status = 'activated' if comp.is_active else 'suspended'
    flash(f'"{comp.name}" has been {status}.', 'info')
    return redirect(request.referrer or url_for('admin.companies'))


@admin_bp.route('/companies/<int:cid>/feature', methods=['POST'])
@admin_required
def feature_company(cid):
    comp = Company.query.get_or_404(cid)
    comp.is_featured = not comp.is_featured
    db.session.commit()
    flash(f'"{comp.name}" featured status updated.', 'info')
    return redirect(request.referrer or url_for('admin.companies'))


# ─── Products ─────────────────────────────────────────────────────────────────

@admin_bp.route('/products')
@admin_required
def products():
    page   = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    status = request.args.get('status', '')
    company_id = request.args.get('company', '', type=int)

    q = Product.query
    if search:
        q = q.filter(Product.name.ilike(f'%{search}%'))
    if status == 'active':
        q = q.filter_by(is_active=True)
    elif status == 'hidden':
        q = q.filter_by(is_active=False)
    elif status == 'out_of_stock':
        q = q.filter(Product.stock == 0)
    if company_id:
        q = q.filter_by(company_id=company_id)

    products = q.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    all_companies = Company.query.order_by(Company.name).all()
    return render_template('admin/products.html', products=products,
                           search=search, status=status,
                           all_companies=all_companies, company_id=company_id)


@admin_bp.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    """Admin can add a product directly (not linked to any company)."""
    form = ProductForm()
    categories = Category.query.order_by(Category.sort_order).all()
    companies  = Company.query.filter_by(is_active=True).order_by(Company.name).all()

    if form.validate_on_submit():
        slug = _make_product_slug(form.name.data, 'admin')
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
            company_id=request.form.get('company_id', type=int) or None,
            category_id=request.form.get('category_id', type=int) or None,
        )
        product.image   = _save_image(form.image,   'products')
        product.image_2 = _save_image(form.image_2, 'products')
        product.image_3 = _save_image(form.image_3, 'products')
        product.image_4 = _save_image(form.image_4, 'products')
        db.session.add(product)
        db.session.commit()
        flash(f'Product "{product.name}" added!', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', form=form,
                           categories=categories, companies=companies,
                           title='Add Product', action='add')


@admin_bp.route('/products/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(pid):
    """Admin can edit ANY product on the marketplace."""
    product    = Product.query.get_or_404(pid)
    form       = ProductForm(obj=product)
    categories = Category.query.order_by(Category.sort_order).all()
    companies  = Company.query.filter_by(is_active=True).order_by(Company.name).all()

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
        product.is_active   = 'is_active' in request.form
        product.category_id = request.form.get('category_id', type=int) or None
        product.company_id  = request.form.get('company_id', type=int) or None

        for attr, field in [('image', form.image), ('image_2', form.image_2),
                            ('image_3', form.image_3), ('image_4', form.image_4)]:
            new = _save_image(field, 'products')
            if new: setattr(product, attr, new)

        db.session.commit()
        flash(f'Product "{product.name}" updated!', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', form=form, product=product,
                           categories=categories, companies=companies,
                           title='Edit Product', action='edit')


@admin_bp.route('/products/<int:pid>/toggle', methods=['POST'])
@admin_required
def toggle_product(pid):
    product = Product.query.get_or_404(pid)
    product.is_active = not product.is_active
    db.session.commit()
    flash(f'Product {"listed" if product.is_active else "hidden"}.', 'info')
    return redirect(request.referrer or url_for('admin.products'))


@admin_bp.route('/products/<int:pid>/feature', methods=['POST'])
@admin_required
def feature_product(pid):
    product = Product.query.get_or_404(pid)
    product.is_featured = not product.is_featured
    db.session.commit()
    flash('Featured status updated.', 'info')
    return redirect(request.referrer or url_for('admin.products'))


@admin_bp.route('/products/<int:pid>/delete', methods=['POST'])
@admin_required
def delete_product(pid):
    product = Product.query.get_or_404(pid)
    name = product.name
    product.is_active = False
    db.session.commit()
    flash(f'"{name}" removed from marketplace.', 'warning')
    return redirect(request.referrer or url_for('admin.products'))


# ─── Categories ───────────────────────────────────────────────────────────────

@admin_bp.route('/categories')
@admin_required
def categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template('admin/categories.html', categories=cats)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@admin_required
def add_category():
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        desc  = request.form.get('description', '').strip()
        sort  = request.form.get('sort_order', 0, type=int)
        if not name:
            flash('Category name is required.', 'danger')
            return redirect(url_for('admin.add_category'))
        slug = _make_slug_cat(name)
        cat  = Category(name=name, slug=slug, description=desc, sort_order=sort)
        db.session.add(cat)
        db.session.commit()
        flash(f'Category "{name}" created.', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', cat=None, title='Add Category')


@admin_bp.route('/categories/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def edit_category(cid):
    cat = Category.query.get_or_404(cid)
    if request.method == 'POST':
        cat.name        = request.form.get('name', '').strip()
        cat.description = request.form.get('description', '').strip()
        cat.sort_order  = request.form.get('sort_order', 0, type=int)
        cat.is_featured = 'is_featured' in request.form
        db.session.commit()
        flash(f'Category "{cat.name}" updated.', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', cat=cat, title='Edit Category')


@admin_bp.route('/categories/<int:cid>/delete', methods=['POST'])
@admin_required
def delete_category(cid):
    cat = Category.query.get_or_404(cid)
    name = cat.name
    # Unlink products
    Product.query.filter_by(category_id=cid).update({'category_id': None})
    db.session.delete(cat)
    db.session.commit()
    flash(f'Category "{name}" deleted.', 'warning')
    return redirect(url_for('admin.categories'))


# ─── Orders ───────────────────────────────────────────────────────────────────

@admin_bp.route('/orders')
@admin_required
def orders():
    from models.delivery import DeliveryPartner
    page   = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    q = Order.query
    if status:
        q = q.filter_by(status=status)
    orders = q.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    order_statuses = ['pending','confirmed','processing','shipped','delivered','cancelled','refunded']
    delivery_partners = DeliveryPartner.query.filter_by(is_active=True).all()
    return render_template('admin/orders.html', orders=orders,
                           status=status, order_statuses=order_statuses,
                           delivery_partners=delivery_partners)


@admin_bp.route('/orders/<int:oid>/status', methods=['POST'])
@admin_required
def update_order_status(oid):
    order  = Order.query.get_or_404(oid)
    status = request.form.get('status')
    valid  = ['pending','confirmed','processing','shipped','delivered','cancelled','refunded']
    if status in valid:
        old_status = order.status
        order.status = status
        db.session.commit()
        # Award loyalty points when delivered
        if status == 'delivered' and old_status != 'delivered':
            try:
                from routes.buyer import award_loyalty_points
                award_loyalty_points(order)
            except Exception:
                pass
        flash(f'Order #{order.order_number} → {status.title()}.', 'success')
    return redirect(request.referrer or url_for('admin.orders'))


# ─── Users ────────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    role = request.args.get('role', '')
    search = request.args.get('q', '')
    q = User.query
    if role:
        q = q.filter_by(role=role)
    if search:
        q = q.filter(User.email.ilike(f'%{search}%') |
                     User.first_name.ilike(f'%{search}%') |
                     User.last_name.ilike(f'%{search}%'))
    users = q.order_by(User.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False)
    return render_template('admin/users.html', users=users, role=role, search=search)


@admin_bp.route('/users/<int:uid>/toggle', methods=['POST'])
@admin_required
def toggle_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'User {"activated" if user.is_active else "deactivated"}.', 'info')
    return redirect(request.referrer or url_for('admin.users'))


# ─── Site Settings ─────────────────────────────────────────────────────────────

@admin_bp.route('/settings')
@admin_required
def settings():
    stats = {
        'total_products':    Product.query.count(),
        'total_companies':   Company.query.count(),
        'verified_companies': Company.query.filter_by(is_verified=True).count(),
        'total_users':       User.query.count(),
    }
    return render_template('admin/settings.html', stats=stats)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_slug_cat(name):
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    base, counter = slug, 1
    while Category.query.filter_by(slug=slug).first():
        slug = f'{base}-{counter}'; counter += 1
    return slug


def _make_product_slug(name, suffix):
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    slug = f'{slug}-{suffix}'
    base, counter = slug, 1
    while Product.query.filter_by(slug=slug).first():
        slug = f'{base}-{counter}'; counter += 1
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


# ── Delivery Partner Management ───────────────────────────────────────────────

@admin_bp.route('/delivery-partners')
@admin_required
def delivery_partners():
    from models.delivery import DeliveryPartner, DeliveryAssignment
    from models.user import User
    from sqlalchemy import or_

    search     = request.args.get('q', '').strip()
    status_f   = request.args.get('status', '').strip()
    vehicle_f  = request.args.get('vehicle', '').strip()

    q = DeliveryPartner.query.join(DeliveryPartner.user)

    if search:
        like = f'%{search}%'
        q = q.filter(or_(
            User.first_name.ilike(like),
            User.last_name.ilike(like),
            User.email.ilike(like),
            DeliveryPartner.area.ilike(like),
            DeliveryPartner.vehicle_no.ilike(like),
            DeliveryPartner.phone.ilike(like),
        ))
    if status_f:
        if status_f == 'active':
            q = q.filter(DeliveryPartner.is_active == True)
        elif status_f == 'inactive':
            q = q.filter(DeliveryPartner.is_active == False)
        elif status_f in ('available', 'busy', 'offline'):
            q = q.filter(DeliveryPartner.status == status_f)
    if vehicle_f:
        q = q.filter(DeliveryPartner.vehicle_type.ilike(f'%{vehicle_f}%'))

    partners = q.order_by(DeliveryPartner.is_active.desc()).all()

    # Counts for filters
    total      = DeliveryPartner.query.count()
    active_cnt = DeliveryPartner.query.filter_by(is_active=True).count()
    avail_cnt  = DeliveryPartner.query.filter_by(status='available', is_active=True).count()
    busy_cnt   = DeliveryPartner.query.filter_by(status='busy', is_active=True).count()

    return render_template('admin/delivery_partners.html',
                           partners=partners,
                           search=search, status_f=status_f, vehicle_f=vehicle_f,
                           total=total, active_cnt=active_cnt,
                           avail_cnt=avail_cnt, busy_cnt=busy_cnt)


@admin_bp.route('/delivery-partners/toggle/<int:pid>', methods=['POST'])
@admin_required
def toggle_delivery_partner(pid):
    from models.delivery import DeliveryPartner
    p = DeliveryPartner.query.get_or_404(pid)
    p.is_active = not p.is_active
    db.session.commit()
    flash(f'{p.user.full_name} {"activated" if p.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin.delivery_partners'))
