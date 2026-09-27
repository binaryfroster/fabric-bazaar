"""
FabricBazaar — Database Seed Script

Local (SQLite):           python seed.py
Against Supabase/Postgres: set DATABASE_URL, then  python seed.py

Drops & recreates all tables, then inserts demo data.
Use run(target_app, drop=False) for a non-destructive seed of an empty DB.
"""
import sys

# Windows consoles default to cp1252 and cannot print the emoji/✓ output below.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from app import create_app
from extensions import db, bcrypt

# Honour DATABASE_URL if present (lets `python seed.py` target Supabase directly),
# otherwise falls back to the local SQLite development database.
app = create_app('development')


def run(target_app=None, drop=True):
    target_app = target_app or app
    with target_app.app_context():
        print("\n" + "=" * 52)
        print("  FabricBazaar — Seeding Database")
        print("=" * 52)

        if drop:
            print("  Dropping & recreating all tables…")
            db.drop_all()
        db.create_all()

        _seed_core()
        _seed_ratings()
        _seed_delivery()

        print("\n" + "=" * 52)
        print("  ✅  Done! Credentials:")
        print("=" * 52)
        print("  👤 ADMIN    admin@fabricbazaar.in     / Admin@1234")
        print("  🏭 SELLER   rajesh@sharmatextiles.com / Seller@1234")
        print("  🏭 SELLER   priya@patelsarees.com     / Seller@1234")
        print("  🛍️  CUSTOMER amit@example.com          / Customer@1")
        print("  🏍️  DELIVERY rider@fabricbazaar.in       / Rider@1234  (Maharashtra)")
        print("  🏍️  DELIVERY rider.cg@fabricbazaar.in    / Rider@1234  (Chhattisgarh)")
        print("  🏍️  DELIVERY rider.kar@fabricbazaar.in   / Rider@1234  (Karnataka)")
        print("  🏍️  DELIVERY rider.goa@fabricbazaar.in   / Rider@1234  (Goa)")
        print("  🏍️  DELIVERY rider.rest@fabricbazaar.in  / Rider@1234  (All Other States)")
        print("\n  🌐 http://localhost:5000")
        print("=" * 52 + "\n")


def _seed_core():
    from models.user import User
    from models.company import Company
    from models.category import Category
    from models.product import Product
    from models.order import Order, OrderItem, OrderTracking

    # ── Categories (exactly 6) ──────────────────────────────────────────────
    categories = [
        Category(name='Bed Sheets',      slug='bed-sheets',    sort_order=1, icon='🛏️'),
        Category(name='Sarees',          slug='sarees',        sort_order=2, icon='👘'),
        Category(name='Kurtas & Kurtis', slug='kurtas',        sort_order=3, icon='👗'),
        Category(name='Salwar Suits',    slug='salwar-suits',  sort_order=4, icon='👚'),
        Category(name='Fabrics & Cloth', slug='fabrics',       sort_order=5, icon='🧵'),
        Category(name='Home Textiles',   slug='home',          sort_order=6, icon='🏠'),
    ]
    db.session.add_all(categories)
    db.session.flush()
    cat_map = {c.slug: c.id for c in categories}

    # ── Admin ──────────────────────────────────────────────────────────────
    admin = User(
        first_name='Admin', last_name='FabricBazaar',
        email='admin@fabricbazaar.in',
        password_hash=bcrypt.generate_password_hash('Admin@1234').decode(),
        role='admin', is_active=True,
    )
    db.session.add(admin)

    # ── Sellers ────────────────────────────────────────────────────────────
    seller1_user = User(
        first_name='Rajesh', last_name='Sharma',
        email='rajesh@sharmatextiles.com',
        password_hash=bcrypt.generate_password_hash('Seller@1234').decode(),
        role='company', is_active=True,
    )
    seller2_user = User(
        first_name='Priya', last_name='Patel',
        email='priya@patelsarees.com',
        password_hash=bcrypt.generate_password_hash('Seller@1234').decode(),
        role='company', is_active=True,
    )
    db.session.add_all([seller1_user, seller2_user])
    db.session.flush()

    comp1 = Company(
        user_id=seller1_user.id,
        name='Sharma Textiles',  slug='sharma-textiles',
        logo='sharma-textiles-logo.jpg',
        tagline='Premium Cottons & Home Linen since 1985',
        description='Sharma Textiles is a third-generation family business based in Panipat, specializing in premium cotton bed sheets and home textiles. Our fabrics are sourced from the finest cotton farms in Rajasthan.',
        phone='9876543210', whatsapp='9876543210',
        email='rajesh@sharmatextiles.com',
        city='Panipat', state='Haryana',
        is_verified=True, is_featured=True,
    )
    comp2 = Company(
        user_id=seller2_user.id,
        name='Patel Sarees',  slug='patel-sarees',
        logo='patel-sarees-logo.jpg',
        tagline='Authentic Indian Sarees & Ethnic Wear',
        description='Patel Sarees is your one-stop destination for authentic Indian sarees. We work directly with weavers in Surat, Varanasi, and Kanchipuram to bring you the finest silk and cotton sarees.',
        phone='9123456789', whatsapp='9123456789',
        email='priya@patelsarees.com',
        city='Surat', state='Gujarat',
        is_verified=True, is_featured=True,
    )
    db.session.add_all([comp1, comp2])

    # ── Customers ──────────────────────────────────────────────────────────
    cust1 = User(
        first_name='Amit', last_name='Kumar',
        email='amit@example.com',
        password_hash=bcrypt.generate_password_hash('Customer@1').decode(),
        role='customer', is_active=True,
    )
    cust2 = User(
        first_name='Sunita', last_name='Verma',
        email='sunita@example.com',
        password_hash=bcrypt.generate_password_hash('Customer@1').decode(),
        role='customer', is_active=True,
    )
    db.session.add_all([cust1, cust2])
    db.session.flush()

    # ── Products — exactly 1 per category ──────────────────────────────────
    products = [
        # 1. Bed Sheets — Sharma Textiles
        Product(
            name='Premium Cotton Bed Sheet Set — White King',
            slug='premium-cotton-bed-sheet-white-king',
            image='cotton-bedsheet-white-king.jpg',
            description='400 thread count pure Egyptian cotton. Set includes 1 flat sheet, 1 fitted sheet, and 2 pillowcases. Soft, breathable, and machine washable. Perfect for all seasons.',
            price=1999, sale_price=1499, stock=150, min_order_qty=1,
            fabric_type='Bed Sheets', material='Cotton',
            color='White', size='King', pattern='Solid',
            is_featured=True, is_bestseller=True,
            company_id=comp1.id, category_id=cat_map['bed-sheets'],
        ),
        # 2. Sarees — Patel Sarees
        Product(
            name='Kanjivaram Pure Silk Saree — Deep Crimson',
            slug='kanjivaram-pure-silk-saree-crimson',
            image='kanjivaram-silk-saree-crimson.jpg',
            description='Authentic Kanjivaram pure silk saree handwoven by master weavers in Kanchipuram. Intricate golden zari border and pallu. Comes with a matching blouse piece.',
            price=8999, sale_price=7499, stock=45, min_order_qty=1,
            fabric_type='Sarees', material='Pure Silk',
            color='Red', size='Free Size', pattern='Geometric',
            is_featured=True, is_bestseller=True,
            company_id=comp2.id, category_id=cat_map['sarees'],
        ),
        # 3. Kurtas & Kurtis — Patel Sarees
        Product(
            name='Hand Block Print Cotton Kurta Set — Mint Green',
            slug='cotton-block-print-kurta-set-mint',
            image='blockprint-kurta-set-mint.jpg',
            description='Lightweight hand block printed cotton kurta with matching dupatta and palazzos. Traditional Rajasthani prints, summer-perfect. Available in S, M, L, XL.',
            price=1299, sale_price=999, stock=120, min_order_qty=1,
            fabric_type='Kurtas & Kurtis', material='Cotton',
            color='Green', size='M', pattern='Floral', is_new=True,
            company_id=comp2.id, category_id=cat_map['kurtas'],
        ),
        # 4. Salwar Suits — Sharma Textiles
        Product(
            name='Pure Cotton Salwar Suit — Embroidered Navy',
            slug='pure-cotton-salwar-suit-navy',
            image='navy-stripe-satin.jpg',
            description='Elegant pure cotton salwar suit with delicate white embroidery on the yoke. Comes with matching dupatta. Comfortable daily wear and festive occasions.',
            price=1599, sale_price=1199, stock=90, min_order_qty=1,
            fabric_type='Salwar Suits', material='Cotton',
            color='Blue', size='M', pattern='Embroidered', is_new=True,
            company_id=comp1.id, category_id=cat_map['salwar-suits'],
        ),
        # 5. Fabrics & Cloth — Sharma Textiles
        Product(
            name='Linen Cotton Blend Fabric — Per Metre',
            slug='linen-cotton-blend-fabric-per-metre',
            image='linen-cotton-blend-fabric.jpg',
            description='55% linen, 45% cotton blend fabric sold by the metre. Ideal for summer clothing, shirts, and home décor. 58 inch width. Minimum order 3 metres.',
            price=599, stock=800, min_order_qty=3,
            fabric_type='Fabrics & Cloth', material='Linen',
            color='Ivory', size='1m', pattern='Solid',
            is_new=True,
            company_id=comp1.id, category_id=cat_map['fabrics'],
        ),
        # 6. Home Textiles — Sharma Textiles
        Product(
            name='Cotton Dhurrie Rug — Geometric Pattern — 4×6 ft',
            slug='cotton-dhurrie-geometric-4x6',
            image='cotton-dhurrie-geometric.jpg',
            description='Handwoven flatweave cotton dhurrie with classic geometric pattern. Reversible design, easy to clean, and fade resistant. Perfect for living rooms and bedrooms.',
            price=3499, sale_price=2799, stock=40, min_order_qty=1,
            fabric_type='Home Textiles', material='Cotton',
            color='Multicolor', size='4x6 ft', pattern='Geometric',
            is_featured=True,
            company_id=comp1.id, category_id=cat_map['home'],
        ),
    ]
    db.session.add_all(products)
    db.session.flush()

    # Seed realistic view counts
    view_counts = [183, 241, 97, 134, 312, 76]
    for p, vc in zip(products, view_counts):
        p.view_count = vc

    db.session.commit()

    # ── Sample Order for demo ───────────────────────────────────────────────
    order = Order(
        order_number=Order.generate_order_number(),
        user_id=cust1.id,
        first_name='Amit', last_name='Kumar',
        email='amit@example.com', phone='9876543210',
        address_line1='42 MG Road', city='Mumbai',
        state='Maharashtra', postal_code='400001', country='India',
        subtotal=1499, shipping_cost=0, tax=269.82,
        total=1768.82,
        status='delivered', payment_status='paid',
        tracking_number='FB1234567890IN',
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(OrderItem(
        order_id=order.id, product_id=products[0].id,
        product_name=products[0].name,
        price=1499, quantity=1,
    ))

    # Tracking events for the demo order
    from datetime import datetime, timedelta
    base = datetime.utcnow() - timedelta(days=5)
    tracking_events = [
        ('pending',          'Order placed successfully.',              ''),
        ('confirmed',        'Order confirmed by seller.',              'Mumbai'),
        ('processing',       'Packed and ready for dispatch.',          'Mumbai Warehouse'),
        ('handed_to_courier','Handed to Delhivery courier.',            'Mumbai'),
        ('in_transit',       'Package in transit.',                     'Pune Hub'),
        ('out_for_delivery', 'Out for delivery with Ravi (Bike).',      'Mumbai'),
        ('delivered',        'Delivered. Signed by: Amit Kumar.',       'Mumbai'),
    ]
    for i, (status, msg, loc) in enumerate(tracking_events):
        OrderTracking.log(
            order_id=order.id, status=status,
            message=msg, location=loc, created_by=admin.id,
        )

    db.session.commit()
    print("  ✓ Categories, users, companies, products, sample order seeded")


def _seed_ratings():
    from models.user import User
    from models.company import Company
    from models.product import Product
    from models.rating import SellerRating, ProductReview

    companies = Company.query.all()
    customers = User.query.filter_by(role='customer').all()
    products  = Product.query.all()

    reviews = [
        (5, 'Excellent quality!', 'The fabric quality is outstanding. Will definitely order again.'),
        (5, 'Highly recommended', 'Very smooth transaction. Product exactly as described.'),
        (4, 'Great Seller',       'Fast delivery, good packing. Matched the description.'),
        (4, 'Good purchase',      'Quality is good for the price. Happy with the order.'),
        (3, 'Okay',               'Product is fine but delivery took longer than expected.'),
        (5, 'Beautiful!',         'The saree is stunning. Perfect for my wedding.'),
    ]

    count = 0
    for i, comp in enumerate(companies):
        for j, cust in enumerate(customers):
            if SellerRating.query.filter_by(company_id=comp.id, user_id=cust.id).first():
                continue
            star, title, review = reviews[(i * len(customers) + j) % len(reviews)]
            db.session.add(SellerRating(
                company_id=comp.id, user_id=cust.id,
                rating=star, title=title, review=review,
                quality_rating=min(5, star),
                communication_rating=min(5, max(1, star - 1)),
                delivery_rating=max(1, star - 1),
                is_verified_purchase=True, is_approved=True,
            ))
            count += 1

    for i, prod in enumerate(products):
        for j, cust in enumerate(customers):
            if ProductReview.query.filter_by(product_id=prod.id, user_id=cust.id).first():
                continue
            star, title, review = reviews[(i + j) % len(reviews)]
            db.session.add(ProductReview(
                product_id=prod.id, user_id=cust.id,
                rating=star, title=title, review=review,
                is_verified_purchase=True, is_approved=True,
            ))
            count += 1

    db.session.commit()
    print(f"  ✓ {count} ratings & reviews seeded")


def _seed_delivery():
    from models.user import User
    from models.delivery import DeliveryPartner, DeliveryAssignment
    from models.order import Order

    # ── 5 delivery partners, one per region ──────────────────────────────────
    partners_data = [
        # (first, last, email, password, phone, vehicle, vehicle_no, area, state_tag, deliveries, rating)
        ('Ravi',    'Sharma',   'rider@fabricbazaar.in',      'Rider@1234',    '9876543210', 'Bike',  'MH01AB1234', 'Mumbai – Andheri / Bandra / Dadar',          'Maharashtra',    47, 4.8),
        ('Pradeep', 'Verma',    'rider.cg@fabricbazaar.in',   'Rider@1234',    '9988776655', 'Bike',  'CG04CD5678', 'Raipur – Telibandha / Pandri / Shankar Nagar','Chhattisgarh',   31, 4.6),
        ('Suresh',  'Naik',     'rider.kar@fabricbazaar.in',  'Rider@1234',    '9123456780', 'Bike',  'KA05EF9012', 'Bengaluru – Koramangala / Indiranagar / HSR',  'Karnataka',      58, 4.9),
        ('Arun',    'Dessai',   'rider.goa@fabricbazaar.in',  'Rider@1234',    '9345678901', 'Scooter','GA03GH3456','Panaji – Panjim / Mapusa / Margao',            'Goa',            22, 4.7),
        ('Mohit',   'Tiwari',   'rider.rest@fabricbazaar.in', 'Rider@1234',    '9456789012', 'Bike',  'DL01IJ7890', 'Delhi / UP / Rajasthan / Gujarat / Other States','All Other States',19, 4.5),
    ]

    created = []
    for (first, last, email, pwd, phone, vtype, vno, area, state_tag, deliveries, rating) in partners_data:
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(
                first_name=first, last_name=last, email=email,
                password_hash=bcrypt.generate_password_hash(pwd).decode(),
                role='delivery', is_active=True,
            )
            db.session.add(u)
            db.session.flush()

        dp = DeliveryPartner.query.filter_by(user_id=u.id).first()
        if not dp:
            dp = DeliveryPartner(
                user_id=u.id, phone=phone,
                vehicle_type=vtype, vehicle_no=vno,
                area=area, status='available',
                total_deliveries=deliveries, rating=rating,
            )
            db.session.add(dp)

        created.append((dp, email, pwd, state_tag))

    db.session.commit()

    # Assign a demo delivered order to the first (Maharashtra) rider
    order = Order.query.filter_by(status='delivered').first()
    main_dp = created[0][0]
    if order and main_dp.id and not DeliveryAssignment.query.filter_by(order_id=order.id).first():
        db.session.add(DeliveryAssignment(
            order_id=order.id, partner_id=main_dp.id,
            status='delivered', otp='428751', otp_verified=True,
        ))
        db.session.commit()

    print("  ✓ Delivery partners seeded:")
    for dp, email, pwd, state in created:
        print(f"      🏍️  [{state:20s}]  {email}  /  {pwd}")


if __name__ == '__main__':
    run()
