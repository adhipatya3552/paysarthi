"""One-off recovery: verify existing draft INV2-TWVF-QYYA-47RL-UVVU, send only if recipient matches env buyer.
Never creates an invoice. Never uses Record External Payment. Never prints secrets.
Usage: python scripts/recover_invoice.py
"""
import os, sys, json
import requests
from dotenv import load_dotenv
load_dotenv()
BASE = "https://api-m.sandbox.paypal.com"
INV = "INV2-TWVF-QYYA-47RL-UVVU"
CID, CSEC = os.getenv("PAYPAL_CLIENT_ID", ""), os.getenv("PAYPAL_CLIENT_SECRET", "")
BUYER = os.getenv("PAYPAL_BUYER_EMAIL", "")

def fail(msg):
    print(f"FAIL: {msg}"); sys.exit(1)

r = requests.post(f"{BASE}/v1/oauth2/token", auth=(CID, CSEC),
    headers={"Accept": "application/json"}, data={"grant_type": "client_credentials"}, timeout=30)
if r.status_code != 200: fail(f"token HTTP {r.status_code}")
tok = r.json().get("access_token", "")
print("token: HTTP 200 (not printed)")

g = requests.get(f"{BASE}/v2/invoicing/invoices/{INV}",
    headers={"Authorization": f"Bearer {tok}"}, timeout=30)
print(f"GET invoice: HTTP {g.status_code}")
if g.status_code != 200: fail(f"invoice not found or wrong ID: {g.text[:300]}")
d = g.json()
det = d.get("detail") or {}
recips = d.get("primary_recipients") or []
recip = ((recips[0].get("billing_info") if recips else {}) or {}).get("email_address", "")
items = d.get("items") or []
print(f"  id={d.get('id')}")
print(f"  invoice_number={det.get('invoice_number')}")
print(f"  status={d.get('status')}")
print(f"  amount={d.get('amount')}")
print(f"  item0={items[0].get('name') if items else None} | desc={(items[0].get('description') if items else None)}")
print(f"  invoicer={d.get('invoicer', {}).get('email_address')}")
print(f"  recipient={recip}")
print(f"  recipient_matches_env_buyer={recip == BUYER and bool(BUYER)}")
if not BUYER: fail(".env PAYPAL_BUYER_EMAIL is empty")
if recip != BUYER:
    print("STOP: recipient is not your new buyer. Fix: update the draft via "
          f"PUT /v2/invoicing/invoices/{INV} with primary_recipients=[new buyer], "
          "or cancel it and create one fresh. Nothing was sent, nothing saved.")
    sys.exit(1)

def url_of(x):
    return x.get("recipient_view_url", "") or ((x.get("detail") or {}).get("metadata") or {}).get("recipient_view_url", "")

rec = {"id": d.get("id"), "invoice_number": det.get("invoice_number"),
       "recipient": recip, "amount": (d.get("amount") or {}).get("value"),
       "currency": (d.get("amount") or {}).get("currency_code"),
       "recipient_view_url": url_of(d)}
open("scripts/.last_invoice.json", "w").write(json.dumps(rec))
print("saved scripts/.last_invoice.json (pre-send)")

if d.get("status") in ("SENT", "UNPAID"):
    print("already sent; skipping POST send")
else:
    s = requests.post(f"{BASE}/v2/invoicing/invoices/{INV}/send",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"send_to_recipient": True, "send_to_invoicer": True}, timeout=30)
    print(f"POST send: HTTP {s.status_code}")
    if s.status_code not in (200, 202): fail(f"send failed: {s.text[:400]}")

g2 = requests.get(f"{BASE}/v2/invoicing/invoices/{INV}",
    headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
print(f"status after send={g2.get('status')}")
u = url_of(g2)
rec["recipient_view_url"] = u
open("scripts/.last_invoice.json", "w").write(json.dumps(rec))
print(f"HOSTED URL: {u if u else '(none yet — open from merchant dashboard Invoicing)'}")
print("DONE: invoice sent, ID unchanged. Awaiting your manual buyer payment.")
