# Workspace & Project Notes (FabricBazaar)

## Technology Stack & Environment
- **Framework:** Flask (Python 3.12, SQLAlchemy, Flask-Login, Flask-WTF, Bcrypt)
- **Deployment Platform:** Vercel (WSGI via `api/index.py`, serverless python runtime)
- **Production Database:** Supabase PostgreSQL (AWS ap-southeast-1, Supavisor connection pooler on port 6543 with NullPool + SSL)
- **Version Control:** GitHub (`binaryfroster/fabric-bazaar`)
- **Hosting URL:** `https://fabric-bazaar-eta.vercel.app/`

## Key Roles & Domain Vocabulary
- `admin`: Full marketplace oversight, company verification, user and catalog management.
- `company`: Verified sellers managing inventory, tracking orders, fulfilling shipments.
- `customer`: Buyers browsing, adding to cart, placing orders via Razorpay or COD, tracking parcels.
- `delivery`: Regional delivery partners assigned by state for last-mile handoff with OTP confirmation.

## Security Posture Rules
1. **Multi-Tenant Scoping:** All seller mutations on orders and products MUST filter by `company_id == comp.id`.
2. **PII Masking:** Public order tracking must redact full names, phone numbers, and street addresses unless accessed by the verified order owner or administrator.
3. **Secret Isolation:** Production credentials (`DATABASE_URL`, `SECRET_KEY`, `RAZORPAY_KEY_SECRET`) must be provided via environment variables, never hardcoded.
4. **Self-Registration Boundaries:** Only Customers and Sellers may self-register publicly. Delivery partners must be provisioned or verified by an administrator.
