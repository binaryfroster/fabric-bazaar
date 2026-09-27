# FabricBazaar 🧵

**India's Fabric Marketplace** — A multi-vendor e-commerce platform for premium Indian fabrics, sarees, bed sheets, kurtas, and home textiles.

---

## What's Fixed in This Version

| # | Issue | Fix Applied |
|---|-------|-------------|
| 1 | Hardcoded Razorpay credentials in source code | All secrets moved to `.env` only — never in code |
| 2 | Hardcoded fallback secret key | Auto-generated secure random key if not set |
| 3 | No rate limiting on login/register | Flask-Limiter: 20 req/hr on login, 10 req/hr on register |
| 4 | No security HTTP headers | X-Frame-Options, CSP, X-XSS-Protection, Referrer-Policy added |
| 5 | Razorpay amount hardcoded to ₹1 (100 paise) | Now correctly uses `order.total × 100` |
| 6 | COD available for any order value | COD blocked above ₹5,000; max 2 pending COD orders per user |
| 7 | Delivery only covered 4 states | All 28 states + 8 UTs mapped to delivery partner emails |
| 8 | No error pages | Custom 404, 500, 429, 403 pages |
| 9 | No SEO meta tags | Open Graph, Twitter Card, JSON-LD structured data added |
| 10 | No production WSGI server | Gunicorn added; `Procfile` for Render/Railway/Fly.io |
| 11 | SQLite in production, no warning | Warning logged; PostgreSQL instructions in .env.example |
| 12 | No `.gitignore` | `.gitignore` added — `.env` and `*.db` excluded from git |
| 13 | Duplicate email registration crash | Graceful check before insert |
| 14 | No production init warnings | `ProductionConfig.init_app()` warns about SQLite & missing keys |

---

## Quick Start (Local Development)

```bash
# 1. Clone / unzip
cd marketplace

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env and fill in your SECRET_KEY and Razorpay test keys

# 5. Run
python app.py
```

Visit: http://localhost:5000

---

## Production Deployment

**👉 See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the full step-by-step guide.**

Recommended free stack: **Vercel** (hosting) + **Supabase** (persistent free
Postgres, S3-compatible storage). The store runs on Supabase alone with Cash on
Delivery; Razorpay, Redis, and object storage are optional and degrade
gracefully when unset.

### Minimum environment variables
```
DATABASE_URL=postgresql://...   # Supabase pooler connection string (REQUIRED)
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">  # REQUIRED
FLASK_ENV=production            # Vercel also sets VERCEL=1 automatically
```
Optional: `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` / `RAZORPAY_UPI_ID`
(online payments), `REDIS_URL` (durable rate limiting), `OBJECT_STORAGE_*` +
`MEDIA_PUBLIC_BASE_URL` (image uploads). See `.env.example`.

### Vercel
`vercel.json` + `api/index.py` are included. Import the repo, set **Root
Directory** to `marketplace`, add the env vars above, and deploy.

### Render / Railway / Fly.io
The included `Procfile` + `start.sh` create/seed the schema and launch gunicorn
(`app:app`). Set `FLASK_ENV=production`, `DATABASE_URL`, and `SECRET_KEY`.

### Database setup
- **Development**: SQLite (auto-created, no setup needed).
- **Production**: seed once with `DATABASE_URL=... python seed.py`, or set
  `AUTO_INIT_DB=1` for first-deploy auto-initialisation (see `DEPLOYMENT.md`).

---

## Architecture

```
marketplace/
├── app.py              # Application factory
├── config.py           # Environment-aware config (dev/prod/test)
├── extensions.py       # Flask extensions (db, login, bcrypt, limiter…)
├── models/             # SQLAlchemy models
│   ├── user.py         # User (customer / company / admin / delivery)
│   ├── product.py      # Product listings
│   ├── order.py        # Orders + tracking events
│   ├── company.py      # Seller profiles
│   └── …
├── routes/             # Flask blueprints
│   ├── auth.py         # Login, register (rate-limited)
│   ├── shop.py         # Product listing + filters
│   ├── checkout.py     # Cart → payment (Razorpay + COD)
│   ├── company.py      # Seller dashboard
│   ├── admin.py        # Admin panel
│   └── …
├── templates/          # Jinja2 HTML templates
│   ├── base.html       # Master layout (SEO, security headers, navbar)
│   ├── errors/         # 404, 500, 429, 403 pages
│   └── …
├── static/             # CSS, JS, images
├── Procfile            # Gunicorn for production deployment
├── requirements.txt    # Python dependencies
└── .env.example        # Template for environment variables
```

---

## User Roles

| Role | Access |
|------|--------|
| **Customer** | Browse, buy, track orders, reviews, messages |
| **Company** | Seller dashboard, product management, analytics |
| **Delivery** | Assigned orders, OTP-based delivery confirmation |
| **Admin** | Full marketplace control — verify sellers, manage all |

---

## Security Notes

- Never commit `.env` to git — it's in `.gitignore`
- Use **live** Razorpay keys only in production
- Razorpay webhook signatures are verified server-side (HMAC-SHA256)
- All forms are CSRF-protected via Flask-WTF
- Passwords hashed with bcrypt (cost factor 12)
- Rate limiting on auth endpoints via Flask-Limiter

---

## Expanding Delivery Coverage

Edit the `STATE_PARTNER_EMAIL` dict in `routes/checkout.py` to map states to real delivery partner email accounts. Create the partner accounts via the Admin panel → Delivery Partners.

