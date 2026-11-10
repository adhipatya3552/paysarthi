"""Day-1 PayPal Sandbox validation: token -> create -> send -> get.
Real payment (buyer click) + webhooks are manual steps documented in DAY1_RUNBOOK.md.
Never uses Record External Payment endpoint.
Usage: pip install -r requirements.txt; cp .env.example .env (fill); python scripts/day1_validate.py
"""
import os, json, sys
import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://api-m.sandbox.paypal.com"
CID = os.getenv("PAYPAL_CLIENT_ID", "")
CSEC = os.getenv("PAYPAL_CLIENT_SECRET", "")
MERCHANT = os.getenv("PAYPAL_MERCHANT_EMAIL", "")
BUYER = os.getenv("PAYPAL_BUYER_EMAIL", "")

def fail(msg):
    print(f"FAIL: {msg}"); sys.exit(1)

def step1_token():
    print("== Step1: POST /v1/oauth2/token ==")
    r = requests.post(f"{BASE}/v1/oauth2/token",
        auth=(CID, CSEC),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"}, timeout=30)
    print(f"  HTTP {r.status_code}")
    if r.status_code != 200: fail(f"token failed: {r.text[:500]}")
    tok = r.json().get("access_token", "")
    if not tok: fail("no access_token in response")
    print("  PASS: access_token received (not printed)")
    return tok

def step2_create(tok):
    print("== Step2: POST /v2/invoicing/invoices ==")
    body = {
        "detail": {"currency_code": "USD", "note": "PaySarthi Day-1 validation. Thank you.",
                   "memo": "paysarthi-day1"},
        "invoicer": {"email_address": MERCHANT},
        "primary_recipients": [{"billing_info": {"email_address": BUYER}}],
        "items": [{"name": "Logo design - Day1 test", "description": "1 logo, 2 revisions",
                   "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "60.00"}}]
    }
    r = requests.post(f"{BASE}/v2/invoicing/invoices", headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json=body, timeout=30)
    print(f"  HTTP {r.status_code}")
    if r.status_code != 201: fail(f"create failed: {r.text[:800]}")
    data = r.json()
    inv_id = data.get("id", "")
    hrefs = [l.get("href", "") for l in data.get("links", [])]
    print(f"  invoice_id={inv_id} status={data.get('status')} links={hrefs}")
    if not inv_id: fail("no invoice id")
    open("scripts/.last_invoice.json", "w").write(json.dumps({"id": inv_id}))
    print("  PASS: DRAFT created, id saved to scripts/.last_invoice.json")
    return inv_id

def step3_send(tok, inv_id):
    print(f"== Step3: POST /v2/invoicing/invoices/{inv_id}/send ==")
    r = requests.post(f"{BASE}/v2/invoicing/invoices/{inv_id}/send",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"send_to_recipient": True, "send_to_invoicer": True}, timeout=30)
    print(f"  HTTP {r.status_code}")
    if r.status_code not in (200, 202): fail(f"send failed: {r.text[:800]}")
    print("  PASS: sent")
    # E: re-GET to extract recipient_view_url (hosted payment page)
    g = requests.get(f"{BASE}/v2/invoicing/invoices/{inv_id}",
        headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if g.status_code != 200: fail(f"get-after-send failed: {g.text[:500]}")
    gd = g.json()
    print(f"  status after send={gd.get('status')}")
    # Hosted URL lives at top-level recipient_view_url or detail.metadata.recipient_view_url
    rurl = gd.get("recipient_view_url", "") or ((gd.get("detail") or {}).get("metadata") or {}).get("recipient_view_url", "")
    try:
        rec = json.load(open("scripts/.last_invoice.json")); rec["recipient_view_url"] = rurl
        open("scripts/.last_invoice.json", "w").write(json.dumps(rec))
    except Exception: pass
    if rurl:
        print(f"  HOSTED URL (open as sandbox buyer): {rurl}")
    else:
        print("  NOTE: no recipient_view_url yet — open invoice from sandbox merchant dashboard → Invoicing.")

def step4_get(tok, inv_id, expect=None):
    print(f"== Step4: GET /v2/invoicing/invoices/{inv_id} ==")
    r = requests.get(f"{BASE}/v2/invoicing/invoices/{inv_id}",
        headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    print(f"  HTTP {r.status_code}")
    if r.status_code != 200: fail(f"get failed: {r.text[:500]}")
    d = r.json()
    status = d.get("status")
    print(f"  status={status} amount={d.get('amount')} due={d.get('due_amount')}")
    print(f"  payments={json.dumps(d.get('payments', {}))[:400]}")
    if expect and status != expect:
        print(f"  NOTE: expected {expect}, got {status} (continue manual step)")
    else:
        print(f"  PASS: status={status}")
    if status == "MARKED_AS_PAID":
        print("  WARNING: MARKED_AS_PAID = external record, NOT a real PayPal payment. Do not demo as paid.")
    return d

if __name__ == "__main__":
    if not all([CID, CSEC, MERCHANT, BUYER]): fail("fill .env first (see .env.example)")
    tok = step1_token()
    inv = step2_create(tok)
    step3_send(tok, inv)
    d = step4_get(tok, inv, expect=None)
    # After send, PayPal shows SENT/UNPAID. Paid only after real buyer payment.
    print("\nNEXT (manual): log into sandbox buyer, open hosted invoice link, pay. Then re-run:")
    print(f"  python scripts/day1_poll.py   (polls GET until PAID, max ~5 min)")
