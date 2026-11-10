"""Lightweight local unit tests (mocked, no PayPal credentials, no real payment).
Run: python scripts/test_day1_local.py
Payment checks use Decimal-exact logic; webhook tests exercise the real
FastAPI endpoint paypal_webhook() with mocked PayPal verify responses.
"""
import os, sys, asyncio, tempfile, threading
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.day1_poll import check
import scripts.webhook_server as ws
from fastapi.responses import JSONResponse

_tmp = tempfile.mkdtemp()
os.environ["WEBHOOK_ID"] = "TEST-WEBHOOK-ID"
os.environ["WEBHOOK_DB"] = os.path.join(_tmp, "t.db")
ws.DB = os.environ["WEBHOOK_DB"]
ws.LOG = os.path.join(_tmp, "t.jsonl")

PASS = []
def t(name, cond):
    PASS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

# ---- payment checks ----
t("paid_paypal_full", check({
    "status": "PAID",
    "amount": {"value": "60.00", "currency_code": "USD"},
    "payments": {"paid_amount": {"value": "60.00", "currency_code": "USD"},
                 "transactions": [{"type": "PAYPAL", "payment_id": "PAY-123",
                                   "amount": {"value": "60.00", "currency_code": "USD"}}]}})[0] is True)
t("marked_as_paid_reject", check({"status": "MARKED_AS_PAID"})[0] is False)
t("external_only_reject", check({
    "status": "PAID", "amount": {"value": "60.00", "currency_code": "USD"},
    "payments": {"paid_amount": {"value": "60.00", "currency_code": "USD"},
                 "transactions": [{"type": "EXTERNAL", "payment_id": "EXT-1",
                                   "amount": {"value": "60.00", "currency_code": "USD"}}]}})[0] is False)
t("amount_mismatch", check({
    "status": "PAID", "amount": {"value": "60.00", "currency_code": "USD"},
    "payments": {"paid_amount": {"value": "59.99", "currency_code": "USD"},
                 "transactions": [{"type": "PAYPAL", "payment_id": "PAY-1",
                                   "amount": {"value": "59.99", "currency_code": "USD"}}]}})[0] is False)
t("partial_sum_reject", check({
    "status": "PAID", "amount": {"value": "60.00", "currency_code": "USD"},
    "payments": {"paid_amount": {"value": "60.00", "currency_code": "USD"},
                 "transactions": [{"type": "PAYPAL", "payment_id": "PAY-1",
                                   "amount": {"value": "30.00", "currency_code": "USD"}}]}})[0] is False)

# ---- webhook endpoint tests (mocked verify, real endpoint + real SQLite) ----
HDRS = {"paypal-transmission-id": "tx-1", "paypal-transmission-time": "2026-01-01T00:00:00Z",
        "paypal-cert-url": "https://api.sandbox.paypal.com/certs", "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "SIG"}

class FakeRequest:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers if headers is not None else dict(HDRS)
    async def json(self):
        return self._body

def call(body, headers=None):
    return asyncio.run(ws.paypal_webhook(FakeRequest(body, headers)))

def is_json_error(resp, code):
    return isinstance(resp, JSONResponse) and resp.status_code == code

EV = {"id": "WH-VALID-1", "event_type": "INVOICING.INVOICE.PAID", "resource": {"id": "INV-1"}}

with mock.patch.object(ws, "get_token", return_value="DUMMY"), \
     mock.patch.object(ws, "verify_signature", return_value="SUCCESS") as mv:
    # 1) new webhook, valid signature -> accepted + stored
    r1 = call(dict(EV))
    t("endpoint_valid_new_accepted",
      isinstance(r1, dict) and r1.get("ok") is True and r1.get("duplicate") is False
      and ws.is_processed("WH-VALID-1") and mv.call_count == 1)
    # 2) duplicate, valid signature -> 2xx without reprocessing (verify still ran first)
    nlog = sum(1 for _ in open(ws.LOG))
    r2 = call(dict(EV))
    t("endpoint_valid_duplicate_acked_once",
      isinstance(r2, dict) and r2.get("ok") is True and r2.get("duplicate") is True
      and mv.call_count == 2 and sum(1 for _ in open(ws.LOG)) == nlog)

with mock.patch.object(ws, "get_token", return_value="DUMMY"), \
     mock.patch.object(ws, "verify_signature", return_value="FAILURE") as mv:
    # 3) invalid signature -> rejected, never stored
    r3 = call({"id": "WH-FORGED-1", "event_type": "INVOICING.INVOICE.PAID", "resource": {"id": "INV-X"}})
    t("endpoint_invalid_sig_rejected_not_stored",
      is_json_error(r3, 400) and not ws.is_processed("WH-FORGED-1"))
    # 4) KNOWN id + invalid signature -> still rejected (verify runs before dedupe)
    r4 = call(dict(EV))
    t("endpoint_known_id_bad_sig_still_rejected",
      is_json_error(r4, 400) and mv.call_count == 2)

with mock.patch.object(ws, "get_token", return_value="DUMMY"), \
     mock.patch.object(ws, "verify_signature", side_effect=ConnectionError("down")):
    # 5) verify API outage -> retryable 502, nothing stored
    r5 = call({"id": "WH-OUTAGE-1", "event_type": "INVOICING.INVOICE.PAID", "resource": {}})
    t("endpoint_verify_outage_502_not_stored",
      is_json_error(r5, 502) and not ws.is_processed("WH-OUTAGE-1"))

# 6) concurrent twin deliveries -> exactly one processed
with mock.patch.object(ws, "get_token", return_value="DUMMY"), \
     mock.patch.object(ws, "verify_signature", return_value="SUCCESS"):
    results = []
    def deliver():
        results.append(asyncio.run(ws.paypal_webhook(
            FakeRequest({"id": "WH-RACE-1", "event_type": "INVOICING.INVOICE.PAID",
                         "resource": {"id": "INV-R"}}))))
    ths = [threading.Thread(target=deliver) for _ in range(2)]
    [x.start() for x in ths]
    [x.join() for x in ths]
    news = sum(1 for r in results if isinstance(r, dict) and r.get("duplicate") is False)
    dups = sum(1 for r in results if isinstance(r, dict) and r.get("duplicate") is True)
    t("endpoint_concurrent_twins_single_process", news == 1 and dups == 1)

# URL extraction supports both locations
def extract(gd):
    return gd.get("recipient_view_url", "") or ((gd.get("detail") or {}).get("metadata") or {}).get("recipient_view_url", "")
t("url_top_level", extract({"recipient_view_url": "https://u1"}) == "https://u1")
t("url_nested", extract({"detail": {"metadata": {"recipient_view_url": "https://u2"}}}) == "https://u2")

bad = [n for n, ok in PASS if not ok]
print(f"\n{len(PASS)-len(bad)}/{len(PASS)} local tests passed.")
sys.exit(1 if bad else 0)
