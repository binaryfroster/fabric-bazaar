# Deploying FabricBazaar

FabricBazaar is a Flask app. This guide covers the recommended free stack:

- **Hosting:** Vercel (serverless Python)
- **Database:** Supabase (free, persistent PostgreSQL)
- **Uploads (optional):** Supabase Storage (S3-compatible)
- **Rate limiting (optional):** Upstash Redis

> **Why Supabase over Render's free Postgres?** Render's free PostgreSQL is
> deleted after 90 days. Supabase's free Postgres persists (it only pauses after
> ~1 week of *inactivity* and resumes on the next request), so it gives you the
> "long memory for free" you want. Supabase also bundles S3-compatible storage,
> so one provider covers both the database and image uploads.

The storefront runs fully on **Supabase alone** (Cash on Delivery, catalogue
browsing, orders, tracking, loyalty). Redis, object storage, and Razorpay are
optional upgrades — the app boots and degrades gracefully without them.

---

## 1. Create the Supabase database

1. Create a project at <https://supabase.com> (free tier).
2. Go to **Project Settings → Database → Connection string** and copy the
   **Connection pooler** URI (host contains `pooler.supabase.com`). Use this for
   serverless — it pools connections so many cold starts don't exhaust Postgres.
   It looks like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
3. Keep this string handy — it is your `DATABASE_URL`.

## 2. Seed the database (once)

From your machine, point the seed script at Supabase and run it:

```bash
# Windows (PowerShell)
$env:DATABASE_URL="postgresql://...pooler.supabase.com:6543/postgres"
python seed.py

# macOS / Linux
DATABASE_URL="postgresql://...pooler.supabase.com:6543/postgres" python seed.py
```

This creates all tables and inserts demo data (admin, sellers, products,
delivery partners). Demo credentials are printed at the end.

> Prefer not to run anything locally? Set `AUTO_INIT_DB=1` (and optionally
> `AUTO_SEED=1`) as Vercel env vars for the first deploy — the app then creates
> and seeds the schema on the first cold start. Remove them afterwards for
> faster starts.

## 3. Deploy to Vercel

1. Push this repo to GitHub/GitLab.
2. In Vercel, **New Project → Import** the repo.
3. Set **Root Directory** to `marketplace` (the folder containing `vercel.json`).
4. Add **Environment Variables** (Project → Settings → Environment Variables):

   | Key           | Value                                             | Required |
   |---------------|---------------------------------------------------|----------|
   | `DATABASE_URL`| your Supabase pooler connection string            | **Yes**  |
   | `SECRET_KEY`  | `python -c "import secrets; print(secrets.token_hex(32))"` | **Yes** |
   | `FLASK_ENV`   | `production` (Vercel also sets `VERCEL=1` for you) | Optional |
   | `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay API keys (enables online payment) | Optional |
   | `RAZORPAY_UPI_ID` | your UPI handle (shows the direct-UPI button) | Optional |
   | `REDIS_URL`   | Upstash Redis URL (durable rate limiting)         | Optional |
   | `OBJECT_STORAGE_*` + `MEDIA_PUBLIC_BASE_URL` | see below (image uploads) | Optional |

5. **Deploy.** `vercel.json` routes all traffic to `api/index.py` (the WSGI app)
   and serves `/static/*` directly.

That's it — the storefront is live with Cash on Delivery.

---

## Optional upgrades

### Online payments (Razorpay)
Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`. The "Pay Online" option and the
payment page appear automatically. Set `RAZORPAY_UPI_ID` to also show the direct
UPI button. Without these, the store is Cash-on-Delivery only (orders above
₹5,000 require online payment, so enable Razorpay to accept high-value orders).

### Image uploads (Supabase Storage or any S3 bucket)
Vercel's filesystem is read-only, so admin/seller image uploads need object
storage. The bundled catalogue images display without this. To enable uploads:

1. Supabase → **Storage** → create a public bucket, then **Project Settings →
   Storage → S3 connection** for endpoint + access keys.
2. Set:
   ```
   OBJECT_STORAGE_BUCKET=<bucket>
   OBJECT_STORAGE_REGION=<region>
   OBJECT_STORAGE_ENDPOINT_URL=https://<ref>.storage.supabase.co/storage/v1/s3
   OBJECT_STORAGE_ACCESS_KEY_ID=<key>
   OBJECT_STORAGE_SECRET_ACCESS_KEY=<secret>
   OBJECT_STORAGE_PREFIX=fabricbazaar
   MEDIA_PUBLIC_BASE_URL=https://<ref>.storage.supabase.co/storage/v1/object/public/<bucket>
   ```
Uploaded images are stored as full URLs and served directly; bundled catalogue
images keep working via bare filenames.

### Durable rate limiting (Upstash Redis)
Serverless invocations are isolated, so in-memory rate limiting resets often.
Create a free Redis at <https://upstash.com>, then set `REDIS_URL=rediss://...`.

---

## Deploying to Render / Railway / Fly instead
A `Procfile` and `start.sh` are included. Set `FLASK_ENV=production`, `DATABASE_URL`
(Supabase or the platform's Postgres), and `SECRET_KEY`. `start.sh` creates and
seeds the schema, then launches gunicorn. On these platforms the filesystem is
still ephemeral, so configure object storage for persistent uploads.

## Demo credentials (after seeding)
- **Admin:** `admin@fabricbazaar.in` / `Admin@1234`
- **Seller:** `rajesh@sharmatextiles.com` / `Seller@1234`
- **Customer:** `amit@example.com` / `Customer@1`
- **Delivery:** `rider@fabricbazaar.in` / `Rider@1234`
