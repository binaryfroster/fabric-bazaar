# Razorpay Payment Setup

## 1. Get Your API Keys

1. Go to [Razorpay Dashboard](https://dashboard.razorpay.com)
2. Sign in → **Settings** → **API Keys**
3. Click **Generate Test Key** (for development)
4. Copy your **Key ID** and **Key Secret**

> Use Test keys (`rzp_test_...`) during development — no real money is charged.  
> Switch to Live keys (`rzp_live_...`) before going live.

---

## 2. Add Keys to .env

Copy `.env.example` → `.env` and fill in your values:

```
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXX
RAZORPAY_UPI_ID=yourname        # from razorpay.me/@yourname
```

---

## 3. How the Payment Flow Works

```
Customer fills checkout form
    ↓
POST /checkout/ → creates pending Order in DB
    ↓
Redirected to /checkout/payment/<order_number>
    ↓
[JS] POST /checkout/razorpay/create-order
    → Server calls Razorpay API → creates Razorpay order
    → Returns { rzp_order_id, amount, key }
    ↓
JS opens Razorpay checkout popup (with rzp_order_id)
    ↓
Customer pays
    ↓
Razorpay returns: { razorpay_payment_id, razorpay_order_id, razorpay_signature }
    ↓
[JS] POST /checkout/payment/verify
    → Server verifies HMAC-SHA256 signature  ← SECURITY CHECK
    → Marks order status = 'confirmed', payment_status = 'paid'
    → Clears cart
    ↓
Redirect to /checkout/confirmation/<order_number>
```

---

## 4. Test Cards (Test Mode)

| Card Number        | Description          |
|--------------------|----------------------|
| 4111 1111 1111 1111 | Visa — success      |
| 5104 0600 0000 0008 | Mastercard — success|
| 4000 0000 0000 0002 | Card declined        |

- CVV: any 3 digits  
- Expiry: any future date  
- OTP: `1234` (in test mode)

**Test UPI:** `success@razorpay`

---

## 5. Images Required

See section below for the images you need to provide.

---

## 6. Production Checklist

- [ ] Switch `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` to Live keys
- [ ] Set `FLASK_ENV=production`
- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set up HTTPS (required by Razorpay for live payments)
- [ ] Enable Razorpay Webhooks for payment confirmation (optional but recommended)
