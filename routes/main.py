"""Main routes — homepage, sellers directory, search, about, contact."""
from extensions import db
from flask import Blueprint, render_template, flash, redirect, url_for, request
from sqlalchemy import or_, and_
from models.product import Product, FABRIC_CATEGORIES
from models.category import Category
from models.company import Company
from forms.contact_forms import ContactForm

main_bp = Blueprint('main', __name__)


def _public_products():
    """Products visible to the public — from verified sellers or admin-added."""
    return (
        Product.query
        .filter(Product.is_active == True)
        .outerjoin(Company, Product.company_id == Company.id)
        .filter(or_(
            Product.company_id == None,
            and_(Company.is_verified == True, Company.is_active == True)
        ))
    )


@main_bp.route('/')
def index():
    featured_products = (_public_products()
                         .filter(Product.is_featured == True)
                         .limit(8).all())
    new_arrivals      = (_public_products()
                         .filter(Product.is_new == True)
                         .limit(8).all())
    bestsellers       = (_public_products()
                         .filter(Product.is_bestseller == True)
                         .limit(8).all())
    featured_companies = (Company.query
                          .filter_by(is_featured=True, is_active=True, is_verified=True)
                          .limit(6).all())
    categories = Category.query.order_by(Category.sort_order).limit(8).all()

    return render_template('index.html',
                           featured_products=featured_products,
                           new_products=new_arrivals,
                           new_arrivals=new_arrivals,
                           bestsellers=bestsellers,
                           featured_sellers=featured_companies,
                           featured_companies=featured_companies,
                           categories=categories,
                           fabric_categories=FABRIC_CATEGORIES)


@main_bp.route('/sellers')
def sellers():
    page  = request.args.get('page', 1, type=int)
    q     = request.args.get('q', '').strip()
    btype = request.args.get('type', '')

    query = Company.query.filter_by(is_active=True, is_verified=True)
    if q:
        query = query.filter(Company.name.ilike(f'%{q}%'))
    if btype:
        query = query.filter_by(business_type=btype)

    pagination = query.order_by(
        Company.is_featured.desc(), Company.name.asc()
    ).paginate(page=page, per_page=12, error_out=False)

    business_types = ['Manufacturer','Wholesaler','Retailer',
                      'Exporter','Manufacturer & Exporter','Trader']
    return render_template('sellers.html', companies=pagination,
                           q=q, btype=btype, business_types=business_types)


@main_bp.route('/seller/<slug>')
def seller_detail(slug):
    from models.rating import SellerRating
    comp = Company.query.filter_by(slug=slug, is_active=True, is_verified=True).first_or_404()
    page = request.args.get('page', 1, type=int)
    products = (comp.products
                .filter_by(is_active=True)
                .order_by(Product.created_at.desc())
                .paginate(page=page, per_page=12, error_out=False))

    # Compute ratings in Python — NOT in template (SQLAlchemy 2.x safe)
    seller_ratings = SellerRating.query.filter_by(
        company_id=comp.id, is_approved=True).order_by(
        SellerRating.created_at.desc()).limit(20).all()
    seller_total = len(seller_ratings)
    seller_avg   = (sum(r.rating for r in seller_ratings) / seller_total) if seller_total else 0

    return render_template('seller_detail.html',
                           comp=comp, products=products,
                           seller_ratings=seller_ratings,
                           seller_total=seller_total,
                           seller_avg=seller_avg)


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        flash('Thank you for your message! We will reply within 24 hours.', 'success')
        return redirect(url_for('main.contact'))
    return render_template('contact.html', form=form)


@main_bp.route('/search')
def search():
    from models.company import Company
    from models.product import Product

    q    = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')   # 'products' | 'sellers' | ''
    sort = request.args.get('sort', 'relevance')

    products  = []
    companies = []

    if q:
        # ── Products ────────────────────────────────────────────
        pq = _public_products().filter(
            db.or_(
                Product.name.ilike(f'%{q}%'),
                Product.description.ilike(f'%{q}%'),
                Product.fabric_type.ilike(f'%{q}%'),
                Product.material.ilike(f'%{q}%'),
                Product.color.ilike(f'%{q}%'),
                Product.pattern.ilike(f'%{q}%'),
            )
        )
        # Sorting
        if sort == 'price_low':
            pq = pq.order_by(
                db.func.coalesce(Product.sale_price, Product.price).asc())
        elif sort == 'price_high':
            pq = pq.order_by(
                db.func.coalesce(Product.sale_price, Product.price).desc())
        elif sort == 'newest':
            pq = pq.order_by(Product.id.desc())
        else:
            pq = pq.order_by(Product.view_count.desc())

        products = pq.limit(40).all()

        # ── Sellers ──────────────────────────────────────────────
        companies = (Company.query
                     .filter(Company.is_verified == True,
                             Company.is_active == True)
                     .filter(
                         db.or_(
                             Company.name.ilike(f'%{q}%'),
                             Company.description.ilike(f'%{q}%'),
                             Company.city.ilike(f'%{q}%'),
                             Company.state.ilike(f'%{q}%'),
                             Company.business_type.ilike(f'%{q}%'),
                         )
                     ).limit(20).all())

    return render_template('search.html',
                           q=q, products=products, companies=companies,
                           type=type_filter, sort=sort)
