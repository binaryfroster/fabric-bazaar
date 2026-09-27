# FabricBazaar — How to Run

## Step 1: Open Command Prompt (NOT PowerShell)

Press **Win + R**, type `cmd`, press Enter.
Navigate to the project:
```
cd C:\Users\HP\OneDrive\Desktop\marketplace
```

## Step 2: Create Virtual Environment (First time only)
```
python -m venv venv
```

## Step 3: Activate Virtual Environment

**In CMD (Recommended):**
```
venv\Scripts\activate
```

**If using PowerShell and getting errors, run this once:**
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then:
```
.\venv\Scripts\Activate.ps1
```

## Step 4: Install Dependencies (First time only)
```
pip install -r requirements.txt
```

## Step 5: Seed Database (First time only, or to reset)
```
python seed.py
```

## Step 6: Run the App
```
python app.py
```

Open browser: **http://localhost:5000**

---

## Login Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@fabricbazaar.in | Admin@1234 |
| Seller 1 | rajesh@sharmatextiles.com | Seller@1234 |
| Seller 2 | priya@patelsarees.com | Seller@1234 |
| Customer | amit@example.com | Customer@1 |
| Delivery | rider@fabricbazaar.in | Rider@1234 |

---

## Razorpay (optional — online payments)

Online payments are **optional**. Without keys the store runs on Cash on
Delivery. To enable online payment, copy `.env.example` to `.env` and set your
own `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (use `rzp_test_...` keys in dev).
Never commit real keys — they load from the environment only.

Payments charge the **real order total**. With test keys, use test card
`4111 1111 1111 1111` · CVV: `111` · Expiry: any future date.

---

## Common Issues

**Port 5000 busy:** Edit the last line of `app.py`:
```python
app.run(debug=True, port=5001)
```

**Database errors:** Delete `fabricbazaar_dev.db` and run `python seed.py` again.

**Package not found:** Make sure venv is activated (you see `(venv)` in prompt).
