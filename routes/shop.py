"""Shop routes — multi-vendor fabric marketplace product listing with filters."""
from flask import Blueprint, render_template, request, current_app
from sqlalchemy import or_, and_
from extensions import db
from models.product import Product, FABRIC_CATEGORIES, MATERIALS, COLORS, SIZES
from models.category import Category
from models.company import Company

shop_bp = Blueprint('shop', __name__)


def _public_products():
    """Base query: only products from verified+active companies."""
    return (Product.query
            .filter(Product.is_active == True)
            .outerjoin(Company, Product.company_id == Company.id)
            .filter(or_(
                Product.company_id == None,
                and_(Company.is_verified == True, Company.is_active == True)
            )))


@shop_bp.route('/')
def index():
    page              = request.args.get('page', 1, type=int)
    search_query      = request.args.get('q', '').strip()
    selected_fabric   = request.args.get('fabric', '').strip()
    selected_material = request.args.get('material', '').strip()
    selected_color    = request.args.get('color', '').strip()
    selected_size     = request.args.get('size', '').strip()
    selected_company  = request.args.get('company', '').strip()
    selected_category = request.args.get('category', '').strip()
    sort_by           = request.args.get('sort', 'newest').strip()
    min_price         = request.args.get('min_price', '').strip()
    max_price         = request.args.get('max_price', '').strip()

    q = _public_products()

    if search_query:
        like = f'%{search_query}%'
        q = q.filter(or_(
            Product.name.ilike(like),
            Product.description.ilike(like),
            Product.fabric_type.ilike(like),
            Product.material.ilike(like),
            Product.color.ilike(like),
        ))
    if selected_fabric:
        q = q.filter(Product.fabric_type == selected_fabric)
    if selected_material:
        q = q.filter(Product.material == selected_material)
    if selected_color:
        q = q.filter(Product.color == selected_color)
    if selected_size:
        q = q.filter(Product.size == selected_size)
    if selected_company:
        comp = Company.query.filter_by(slug=selected_company).first()
        if comp:
            q = q.filter(Product.company_id == comp.id)
    if selected_category:
        cat = Category.query.filter_by(slug=selected_category).first()
        if cat:
            q = q.filter(Product.category_id == cat.id)
    if min_price:
        try: q = q.filter(Product.price >= float(min_price))
        except ValueError: pass
    if max_price:
        try: q = q.filter(Product.price <= float(max_price))
        except ValueError: pass

    # Sorting
    order_map = {
        'newest':     Product.created_at.desc(),
        'price_asc':  Product.price.asc(),
        'price_desc': Product.price.desc(),
        'featured':   Product.is_featured.desc(),
        'popular':    Product.view_count.desc(),
        'name_asc':   Product.name.asc(),
    }
    q = q.order_by(order_map.get(sort_by, Product.created_at.desc()))

    per_page   = current_app.config.get('PRODUCTS_PER_PAGE', 12)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    products   = pagination.items

    categories = Category.query.order_by(Category.sort_order).all()
    companies  = (Company.query
                  .filter_by(is_active=True, is_verified=True)
                  .order_by(Company.name).all())

    return render_template('shop.html',
                           products=products,
                           pagination=pagination,
                           categories=categories,
                           companies=companies,
                           fabric_categories=FABRIC_CATEGORIES,
                           materials=MATERIALS,
                           colors=COLORS,
                           sizes=SIZES,
                           selected_fabric=selected_fabric,
                           selected_material=selected_material,
                           selected_color=selected_color,
                           selected_size=selected_size,
                           selected_company=selected_company,
                           selected_category=selected_category,
                           sort_by=sort_by,
                           search_query=search_query,
                           min_price=min_price,
                           max_price=max_price)


@shop_bp.route('/product/<slug>')
def product_detail(slug):
    product = (Product.query
               .filter(Product.slug == slug, Product.is_active == True)
               .outerjoin(Company, Product.company_id == Company.id)
               .filter(or_(
                   Product.company_id == None,
                   and_(Company.is_verified == True, Company.is_active == True)
               ))
               .first_or_404())

    related = (_public_products()
               .filter(Product.fabric_type == product.fabric_type,
                       Product.id != product.id)
               .limit(4).all())

    # Pre-fetch reviews in Python — no SQLAlchemy in template (2.x safe)
    from models.rating import ProductReview
    approved_reviews = (ProductReview.query
                        .filter_by(product_id=product.id, is_approved=True)
                        .order_by(ProductReview.created_at.desc())
                        .limit(30).all())
    review_total = len(approved_reviews)
    review_avg   = (sum(r.rating for r in approved_reviews) / review_total) if review_total else 0

    # Increment view counter
    try:
        product.view_count = (product.view_count or 0) + 1
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except: pass

    return render_template('product_detail.html',
                           product=product,
                           related=related,
                           approved_reviews=approved_reviews,
                           review_total=review_total,
                           review_avg=review_avg)
