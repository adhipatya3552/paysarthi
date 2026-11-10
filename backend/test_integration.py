"""Integration checks: auth gate active (DEMO_PASSWORD is set) + DB truth intact.
Anonymous API calls must 401; data-layer checks run via direct DB reads.
No PayPal writes, no secrets printed. Run: python backend/test_integration.py
"""
import subprocess, time, sys, urllib.request, urllib.error
from decimal import Decimal

BASE = "http://127.0.0.1:8001"
ok = []


def check(name, cond, extra=""):
    ok.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


def code(method, url, body=None):
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method=method)
    try:
        return urllib.request.urlopen(req, timeout=15).status
    except urllib.error.HTTPError as e:
        return e.code


p = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app",
                      "--port", "8001"],
                     cwd=r"D:\Builds\paypal-hackathon",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(12)
    check("gate_dashboard_401", code("GET", f"{BASE}/api/dashboard") == 401)
    check("gate_invoice_401", code("GET", f"{BASE}/api/invoices/2") == 401)
    check("gate_login_wrong_401",
          code("POST", f"{BASE}/api/login", b'{"password":"wrong"}') == 401)

    sys.path.insert(0, r"D:\Builds\paypal-hackathon")
    from backend.app.database import SessionLocal
    from backend.app import models
    db = SessionLocal()
    inv = db.query(models.Invoice).filter_by(
        paypal_invoice_id="INV2-TWVF-QYYA-47RL-UVVU").first()
    check("history_invoice_present", inv is not None and inv.status == "PAID"
          and float(inv.amount) == 60.00, getattr(inv, "status", None))
    pay = db.query(models.Payment).filter_by(
        paypal_payment_id="1CA8182964133384M").first()
    check("history_payment_present", pay is not None and float(pay.amount) == 60.00,
          getattr(pay, "paypal_payment_id", None))
    check("no_test_rows_leaked",
          db.query(models.Invoice).count() == 1
          and db.query(models.Payment).count() == 1,
          "invoices/payments unchanged; extra agreements (if any) are your "
          "manual browser-test rows, kept intentionally")
    db.close()
finally:
    p.terminate()

print(f"\n{sum(ok)}/{len(ok)} integration checks passed.")
sys.exit(0 if all(ok) else 1)
