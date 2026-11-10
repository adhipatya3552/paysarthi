"""Parity check: authenticated POST /api/invoices/prepare on the historical
approved agreement. Read-only (prepare never calls PayPal). Prints preview
fields only — never secrets. Run: python backend/check_preview.py
"""
import subprocess, sys, time, json, urllib.request, os
from dotenv import load_dotenv
load_dotenv(".env")

p = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app",
                      "--port", "8001"],
                     cwd=r"D:\Builds\paypal-hackathon",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(12)

    def post(path, body, tok=None):
        h = {"Content-Type": "application/json"}
        if tok:
            h["Authorization"] = "Bearer " + tok
        req = urllib.request.Request("http://127.0.0.1:8001" + path,
                                     data=json.dumps(body).encode(),
                                     headers=h, method="POST")
        return json.load(urllib.request.urlopen(req, timeout=20))

    tok = post("/api/login", {"password": os.environ["DEMO_PASSWORD"]})["token"]
    print("login: ok (token not printed)")
    pv = post("/api/invoices/prepare", {"agreement_id": 2}, tok)
    it = pv["items"][0]
    print("recipient:", pv["recipient"])
    print("item:", it["name"], "|", it["quantity"], "|", it["unit_amount"])
    print("desc_len:", len(it.get("description", "")))
    print("note:", pv["detail"]["note"])
    print("terms_present:", bool(pv.get("payment_terms")))
    print("existing:", pv["existing"] and pv["existing"]["paypal_invoice_id"])
    assert it["unit_amount"] == {"currency_code": "USD", "value": "60.00"}
    assert len(it.get("description", "")) > 0
    print("PARITY_OK")
finally:
    p.terminate()
