"""
Analytics routes.
/company/analytics    — seller's own performance dashboard
/admin/analytics      — marketplace-wide super analytics
/admin/analytics/<id> — per-company deep-dive (admin only)
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, extract, cast, Float
from extensions import db
from models.product import Product
from models.company import Company
from models.order import Order, OrderItem
from models.rating import SellerRating, ProductReview
from models.user import User

analytics_bp = Blueprint('analytics', __name__)


# ─── helpers ────────────────────────────────────────────────────────────────

def _revenue_by_day(company_id=None, days=30):
    """Returns list of (date_str, revenue) for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)
    q = (db.session.query(
            func.date(Order.created_at).label('day'),
            func.sum(OrderItem.price * OrderItem.quantity).label('revenue'),
         )
         .join(OrderItem)
         .filter(Order.created_at >= since,
                 Order.status.notin_(['cancelled', 'refunded']))
    )
    if company_id:
        q = q.join(Product, OrderItem.product_id == Product.id)\
             .filter(Product.company_id == company_id)
    rows = q.group_by(func.date(Order.created_at)).order_by('day').all()
    # Fill in missing days
    result = {}
    for r in rows:
        result[str(r.day)] = float(r.revenue or 0)
    out = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime('%Y-%m-%d')
        out.append({'date': d, 'revenue': result.get(d, 0)})
    return out


def _orders_by_status(company_id=None):
    q = db.session.query(Order.status, func.count(Order.id))
    if company_id:
        q = (q.join(OrderItem)
               .join(Product, OrderItem.product_id == Product.id)
               .filter(Product.company_id == company_id))
    return dict(q.group_by(Order.status).all())


def _top_products(company_id, limit=10):
    rows = (db.session.query(
                Product.name,
                func.sum(OrderItem.quantity).label('units'),
                func.sum(OrderItem.price * OrderItem.quantity).label('revenue'),
                func.count(OrderItem.id).label('orders'),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Product.company_id == company_id,
                    Order.status.notin_(['cancelled', 'refunded']))
            .group_by(Product.id)
            .order_by(func.sum(OrderItem.price * OrderItem.quantity).desc())
            .limit(limit).all())
    return [{'name': r.name, 'units': int(r.units or 0),
             'revenue': float(r.revenue or 0), 'orders': int(r.orders or 0)}
            for r in rows]


def _rating_distribution(company_id):
    rows = (db.session.query(SellerRating.rating, func.count(SellerRating.id))
            .filter_by(company_id=company_id, is_approved=True)
            .group_by(SellerRating.rating).all())
    dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r, c in rows:
        dist[r] = c
    return dist


def _avg_rating(company_id):
    r = (db.session.query(func.avg(SellerRating.rating))
         .filter_by(company_id=company_id, is_approved=True).scalar())
    return round(float(r), 1) if r else None


def _company_summary(company_id):
    """Full KPI dict for one company."""
    comp = Company.query.get(company_id)
    if not comp:
        return {}

    # Revenue & orders (all time)
    rev_row = (db.session.query(func.sum(OrderItem.price * OrderItem.quantity))
               .join(Order, Order.id == OrderItem.order_id)
               .join(Product, Product.id == OrderItem.product_id)
               .filter(Product.company_id == company_id,
                       Order.status.notin_(['cancelled', 'refunded'])).scalar())
    total_revenue = float(rev_row or 0)

    order_count = (Order.query.join(OrderItem)
                   .join(Product, OrderItem.product_id == Product.id)
                   .filter(Product.company_id == company_id)
                   .distinct(Order.id).count())

    units_sold = (db.session.query(func.sum(OrderItem.quantity))
                  .join(Product, OrderItem.product_id == Product.id)
                  .filter(Product.company_id == company_id).scalar() or 0)

    total_views = (db.session.query(func.sum(Product.view_count))
                   .filter_by(company_id=company_id).scalar() or 0)

    avg_order = (total_revenue / order_count) if order_count else 0
    conversion = (order_count / total_views * 100) if total_views else 0

    # Ratings
    avg_rat = _avg_rating(company_id)
    rat_count = SellerRating.query.filter_by(company_id=company_id, is_approved=True).count()

    # This month vs last month
    now   = datetime.utcnow()
    m_start = now.replace(day=1, hour=0, minute=0, second=0)
    lm_start = (m_start - timedelta(days=1)).replace(day=1)

    def _month_rev(start, end):
        r = (db.session.query(func.sum(OrderItem.price * OrderItem.quantity))
             .join(Order).join(Product, OrderItem.product_id == Product.id)
             .filter(Product.company_id == company_id,
                     Order.created_at >= start, Order.created_at < end,
                     Order.status.notin_(['cancelled', 'refunded'])).scalar())
        return float(r or 0)

    this_month_rev = _month_rev(m_start, now)
    last_month_rev = _month_rev(lm_start, m_start)
    rev_change = ((this_month_rev - last_month_rev) / last_month_rev * 100
                  if last_month_rev else None)

    return {
        'comp':            comp,
        'total_revenue':   total_revenue,
        'order_count':     order_count,
        'units_sold':      int(units_sold),
        'total_views':     int(total_views),
        'avg_order':       avg_order,
        'conversion':      round(conversion, 2),
        'avg_rating':      avg_rat,
        'rating_count':    rat_count,
        'this_month_rev':  this_month_rev,
        'last_month_rev':  last_month_rev,
        'rev_change':      round(rev_change, 1) if rev_change is not None else None,
        'active_products': comp.products.filter_by(is_active=True).count(),
        'out_of_stock':    comp.products.filter(Product.stock == 0, Product.is_active == True).count(),
    }


# ─── Seller Analytics ────────────────────────────────────────────────────────

@analytics_bp.route('/company/analytics')
@login_required
def company_analytics():
    if not current_user.is_company:
        from flask import flash, redirect, url_for
        flash('Seller account required.', 'warning')
        return redirect(url_for('main.index'))

    comp = current_user.company
    if not comp:
        from flask import redirect, url_for
        return redirect(url_for('company.setup_profile'))

    period = request.args.get('period', '30', type=str)
    days   = {'7': 7, '30': 30, '90': 90, '365': 365}.get(period, 30)

    summary      = _company_summary(comp.id)
    revenue_data = _revenue_by_day(comp.id, days)
    status_data  = _orders_by_status(comp.id)
    top_products = _top_products(comp.id, 10)
    rat_dist     = _rating_distribution(comp.id)
    recent_ratings = (SellerRating.query
                      .filter_by(company_id=comp.id, is_approved=True)
                      .order_by(SellerRating.created_at.desc())
                      .limit(10).all())

    # Product-level stats
    product_stats = (db.session.query(
                         Product.id, Product.name, Product.image,
                         Product.price, Product.stock, Product.view_count,
                         Product.is_active,
                         func.coalesce(func.sum(OrderItem.quantity), 0).label('units_sold'),
                         func.coalesce(
                             func.sum(OrderItem.price * OrderItem.quantity), 0
                         ).label('revenue'),
                         func.coalesce(func.avg(ProductReview.rating), 0).label('avg_review'),
                         func.count(ProductReview.id).label('review_count'),
                     )
                     .outerjoin(OrderItem, OrderItem.product_id == Product.id)
                     .outerjoin(Order, (Order.id == OrderItem.order_id) &
                                Order.status.notin_(['cancelled', 'refunded']))
                     .outerjoin(ProductReview, (ProductReview.product_id == Product.id) &
                                (ProductReview.is_approved == True))
                     .filter(Product.company_id == comp.id)
                     .group_by(Product.id)
                     .order_by(func.coalesce(
                         func.sum(OrderItem.price * OrderItem.quantity), 0).desc())
                     .all())

    return render_template('company/analytics.html',
                           comp=comp,
                           summary=summary,
                           revenue_data=revenue_data,
                           status_data=status_data,
                           top_products=top_products,
                           rat_dist=rat_dist,
                           recent_ratings=recent_ratings,
                           product_stats=product_stats,
                           period=period,
                           avg_rating=summary.get('avg_rating'))


# ─── Admin Super Analytics ───────────────────────────────────────────────────

@analytics_bp.route('/admin/analytics')
@login_required
def admin_analytics():
    if not current_user.is_admin:
        from flask import flash, redirect, url_for
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))

    period = request.args.get('period', '30', type=str)
    days   = {'7': 7, '30': 30, '90': 90, '365': 365}.get(period, 30)
    since  = datetime.utcnow() - timedelta(days=days)

    # ── Marketplace KPIs ──
    total_rev = (db.session.query(func.sum(OrderItem.price * OrderItem.quantity))
                 .join(Order)
                 .filter(Order.status.notin_(['cancelled', 'refunded'])).scalar() or 0)

    period_rev = (db.session.query(func.sum(OrderItem.price * OrderItem.quantity))
                  .join(Order)
                  .filter(Order.created_at >= since,
                          Order.status.notin_(['cancelled', 'refunded'])).scalar() or 0)

    total_orders  = Order.query.count()
    period_orders = Order.query.filter(Order.created_at >= since).count()
    total_views   = db.session.query(func.sum(Product.view_count)).scalar() or 0

    # ── Revenue by day ──
    revenue_data = _revenue_by_day(None, days)

    # ── Orders by status ──
    status_data  = _orders_by_status(None)

    # ── New registrations per day (companies + customers) ──
    reg_data_rows = (db.session.query(
                    func.date(User.created_at).label('day'),
                    User.role,
                    func.count(User.id).label('cnt'),
                )
                .filter(User.created_at >= since)
                .group_by(func.date(User.created_at), User.role)
                .order_by('day').all())
    reg_data = [{'day': str(r.day), 'role': r.role, 'cnt': int(r.cnt)} for r in reg_data_rows]

    # ── Top companies by revenue ──
    top_companies_rows = (db.session.query(
                         Company.id, Company.name, Company.slug,
                         Company.is_verified,
                         func.coalesce(func.sum(OrderItem.price * OrderItem.quantity), 0).label('revenue'),
                         func.count(func.distinct(Order.id)).label('orders'),
                         func.coalesce(func.avg(SellerRating.rating), 0).label('avg_rating'),
                         func.count(func.distinct(SellerRating.id)).label('rating_count'),
                     )
                     .outerjoin(Product, Product.company_id == Company.id)
                     .outerjoin(OrderItem, OrderItem.product_id == Product.id)
                     .outerjoin(Order, (Order.id == OrderItem.order_id) &
                                Order.status.notin_(['cancelled', 'refunded']))
                     .outerjoin(SellerRating, (SellerRating.company_id == Company.id) &
                                (SellerRating.is_approved == True))
                     .group_by(Company.id)
                     .order_by(func.coalesce(
                         func.sum(OrderItem.price * OrderItem.quantity), 0).desc())
                     .limit(15).all())
    top_companies = [{'id': r.id, 'name': r.name, 'slug': r.slug,
                      'is_verified': r.is_verified,
                      'revenue': float(r.revenue or 0),
                      'orders': int(r.orders or 0),
                      'avg_rating': float(r.avg_rating or 0),
                      'rating_count': int(r.rating_count or 0)}
                     for r in top_companies_rows]

    # ── Top products across marketplace ──
    top_products_global_rows = (db.session.query(
                               Product.id, Product.name, Product.image,
                               Company.name.label('company_name'),
                               func.sum(OrderItem.quantity).label('units'),
                               func.sum(OrderItem.price * OrderItem.quantity).label('revenue'),
                           )
                           .join(OrderItem, OrderItem.product_id == Product.id)
                           .join(Order, Order.id == OrderItem.order_id)
                           .outerjoin(Company, Product.company_id == Company.id)
                           .filter(Order.status.notin_(['cancelled', 'refunded']))
                           .group_by(Product.id, Company.name)
                           .order_by(func.sum(
                               OrderItem.price * OrderItem.quantity).desc())
                           .limit(10).all())
    top_products_global = [{'id': r.id, 'name': r.name, 'image': r.image,
                             'company_name': r.company_name or '',
                             'units': int(r.units or 0),
                             'revenue': float(r.revenue or 0)}
                            for r in top_products_global_rows]

    # ── Category revenue breakdown ──
    from models.category import Category
    cat_revenue_rows = (db.session.query(
                       func.coalesce(Product.fabric_type, 'Uncategorised').label('cat'),
                       func.sum(OrderItem.price * OrderItem.quantity).label('revenue'),
                   )
                   .join(OrderItem, OrderItem.product_id == Product.id)
                   .join(Order, Order.id == OrderItem.order_id)
                   .filter(Order.status.notin_(['cancelled', 'refunded']))
                   .group_by('cat')
                   .order_by(func.sum(
                       OrderItem.price * OrderItem.quantity).desc())
                   .limit(12).all())
    cat_revenue = [[str(r.cat), float(r.revenue or 0)] for r in cat_revenue_rows]

    # ── Platform growth: verified companies over time ──
    company_growth_rows = (db.session.query(
                          func.date(Company.created_at).label('day'),
                          func.count(Company.id).label('cnt'),
                      )
                      .filter(Company.created_at >= since)
                      .group_by(func.date(Company.created_at))
                      .order_by('day').all())
    company_growth = [{'day': str(r.day), 'cnt': int(r.cnt)} for r in company_growth_rows]

    # ── Recent ratings activity ──
    recent_ratings = (SellerRating.query
                      .order_by(SellerRating.created_at.desc())
                      .limit(10).all())

    kpis = {
        'total_revenue':   float(total_rev),
        'period_revenue':  float(period_rev),
        'total_orders':    total_orders,
        'period_orders':   period_orders,
        'total_companies': Company.query.filter_by(is_verified=True).count(),
        'pending_sellers': Company.query.filter_by(is_verified=False, is_active=True).count(),
        'total_products':  Product.query.filter_by(is_active=True).count(),
        'total_customers': User.query.filter_by(role='customer').count(),
        'total_views':     int(total_views),
        'avg_order_value': (float(total_rev) / total_orders) if total_orders else 0,
        'total_ratings':   SellerRating.query.count(),
        'avg_marketplace_rating': (
            db.session.query(func.avg(SellerRating.rating))
            .filter_by(is_approved=True).scalar() or 0
        ),
    }

    return render_template('admin/analytics.html',
                           kpis=kpis,
                           revenue_data=revenue_data,
                           status_data=status_data,
                           reg_data=reg_data,
                           top_companies=top_companies,
                           top_products_global=top_products_global,
                           cat_revenue=cat_revenue,
                           company_growth=company_growth,
                           recent_ratings=recent_ratings,
                           period=period)


# ─── Admin: Per-Company Deep Dive ────────────────────────────────────────────

@analytics_bp.route('/admin/analytics/company/<int:company_id>')
@login_required
def admin_company_analytics(company_id):
    if not current_user.is_admin:
        from flask import flash, redirect, url_for
        flash('Admin access required.', 'danger')
        return redirect(url_for('main.index'))

    period = request.args.get('period', '30', type=str)
    days   = {'7': 7, '30': 30, '90': 90, '365': 365}.get(period, 30)

    summary      = _company_summary(company_id)
    revenue_data = _revenue_by_day(company_id, days)
    status_data  = _orders_by_status(company_id)
    top_products = _top_products(company_id, 15)
    rat_dist     = _rating_distribution(company_id)
    all_ratings  = (SellerRating.query
                    .filter_by(company_id=company_id)
                    .order_by(SellerRating.created_at.desc())
                    .all())

    product_stats = (db.session.query(
                         Product.id, Product.name, Product.image,
                         Product.price, Product.stock, Product.view_count,
                         Product.is_active,
                         func.coalesce(func.sum(OrderItem.quantity), 0).label('units_sold'),
                         func.coalesce(
                             func.sum(OrderItem.price * OrderItem.quantity), 0
                         ).label('revenue'),
                         func.coalesce(func.avg(ProductReview.rating), 0).label('avg_review'),
                         func.count(ProductReview.id).label('review_count'),
                     )
                     .outerjoin(OrderItem, OrderItem.product_id == Product.id)
                     .outerjoin(Order, (Order.id == OrderItem.order_id) &
                                Order.status.notin_(['cancelled', 'refunded']))
                     .outerjoin(ProductReview, (ProductReview.product_id == Product.id) &
                                (ProductReview.is_approved == True))
                     .filter(Product.company_id == company_id)
                     .group_by(Product.id)
                     .order_by(func.coalesce(
                         func.sum(OrderItem.price * OrderItem.quantity), 0).desc())
                     .all())

    # Monthly trend for this company (last 12 months)
    monthly_rows = (db.session.query(
                   extract('year',  Order.created_at).label('yr'),
                   extract('month', Order.created_at).label('mo'),
                   func.sum(OrderItem.price * OrderItem.quantity).label('rev'),
                   func.count(func.distinct(Order.id)).label('cnt'),
               )
               .join(OrderItem)
               .join(Product, OrderItem.product_id == Product.id)
               .filter(Product.company_id == company_id,
                       Order.created_at >= datetime.utcnow() - timedelta(days=365),
                       Order.status.notin_(['cancelled', 'refunded']))
               .group_by('yr', 'mo')
               .order_by('yr', 'mo').all())
    monthly = [[int(r.yr), int(r.mo), float(r.rev or 0), int(r.cnt or 0)]
               for r in monthly_rows]

    return render_template('admin/company_analytics.html',
                           summary=summary,
                           revenue_data=revenue_data,
                           status_data=status_data,
                           top_products=top_products,
                           rat_dist=rat_dist,
                           all_ratings=all_ratings,
                           product_stats=product_stats,
                           monthly=monthly,
                           period=period,
                           company_id=company_id)
