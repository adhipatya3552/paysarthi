"""Poll GET invoice until genuine PAID (fallback if webhooks not yet configured).
Usage: python scripts/day1_poll.py
PASS requires ALL (Decimal-exact): status==PAID + payments.paid_amount
matches invoice amount/currency + >=1 type==PAYPAL txn with payment_id +
sum(PAYPAL txn amounts) == invoice total. EXTERNAL never counts.
MARKED_AS_PAID is unconditional FAIL.
"""
import os, sys, time, json
from decimal import Decimal, InvalidOperation
import requests
from dotenv import load_dotenv
load_dotenv()
BASE = "https://api-m.sandbox.paypal.com"

def get_token(cid, csec):
    r = requests.post(f"{BASE}/v1/oauth2/token", auth=(cid, csec),
        headers={"Accept": "application/json"}, data={"grant_type": "client_credentials"}, timeout=30)
    if r.status_code != 200:
        print(f"FAIL: token HTTP {r.status_code}"); sys.exit(1)
    return r.json().get("access_token", "")

def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None

def check(d):
    """Returns (ok, reason). ok=True PASS, False FAIL, None not-yet-paid. Never prints secrets."""
    status = d.get("status")
    if status == "MARKED_AS_PAID":
        return False, "MARKED_AS_PAID is an external record, NOT a hosted PayPal payment."
    if status != "PAID":
        return None, f"status={status} (not yet paid)"
    exp = d.get("amount") or {}
    exp_amt, exp_cur = _dec(exp.get("value")), exp.get("currency_code")
    if exp_amt is None or not exp_cur:
        return False, "invoice amount/currency missing; cannot verify."
    pay = d.get("payments") or {}
    paid = pay.get("paid_amount") or {}
    if _dec(paid.get("value")) != exp_amt or paid.get("currency_code") != exp_cur:
        return False, (f"payments.paid_amount {paid} != invoice total "
                       f"{exp_amt} {exp_cur}.")
    txns = pay.get("transactions") or []
    paypal_txns = [t for t in txns if t.get("type") == "PAYPAL" and t.get("payment_id")]
    if not paypal_txns:
        ext = [t.get("type") for t in txns]
        return False, f"no PAYPAL transaction (types seen: {ext}). EXTERNAL does not count."
    total = Decimal("0")
    for t in paypal_txns:
        a = t.get("amount") or {}
        if a.get("currency_code") != exp_cur:
            return False, "PAYPAL txn currency mismatch vs invoice."
        v = _dec(a.get("value"))
        if v is None:
            return False, "PAYPAL txn amount unparseable."
        total += v
    if total != exp_amt:
        return False, f"sum(PAYPAL txns)={total} != invoice total {exp_amt} {exp_cur}."
    return True, (f"PAYPAL payment_id={paypal_txns[0].get('payment_id')} "
                  f"total={total} {exp_cur}, paid_amount matched.")

def main():
    cid, csec = os.getenv("PAYPAL_CLIENT_ID", ""), os.getenv("PAYPAL_CLIENT_SECRET", "")
    try:
        inv = json.load(open("scripts/.last_invoice.json"))["id"]
    except Exception:
        print("FAIL: no scripts/.last_invoice.json — run day1_validate.py first"); sys.exit(1)
    tok = get_token(cid, csec)
    for i in range(30):
        try:
            r = requests.get(f"{BASE}/v2/invoicing/invoices/{inv}",
                headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        except Exception as e:
            print(f"[{i}] request error: {type(e).__name__}"); time.sleep(10); continue
        if r.status_code == 401:
            tok = get_token(cid, csec); continue
        if r.status_code != 200:
            print(f"[{i}] GET HTTP {r.status_code}"); time.sleep(10); continue
        ok, reason = check(r.json())
        print(f"[{i}] {reason}")
        if ok is True:
            print("PASS: genuine sandbox PayPal payment confirmed.")
            return
        if ok is False:
            print("FAIL: payment integrity check failed."); sys.exit(1)
        time.sleep(10)
    print("NOT TESTED: still not PAID after ~5 min — pay the hosted link as sandbox buyer first.")

if __name__ == "__main__":
    main()
