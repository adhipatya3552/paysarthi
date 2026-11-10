"""Webhook edge-case tests: real paypal_webhook() endpoint, stub DB session,
mocked PayPal client. No network, no secrets.
Run: python backend/test_webhooks.py
"""
import os, sys, json, asyncio
os.environ.setdefault("WEBHOOK_ID", "TEST-WH")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest import mock
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
import backend.app.routers.webhooks as wh
from backend.app import models

HDRS = {"paypal-transmission-id": "t", "paypal-transmission-time": "now",
        "paypal-cert-url": "https://c", "paypal-auth-algo": "SHA",
        "paypal-transmission-sig": "SIG"}


def make_req(body):
    raw = json.dumps(body).encode()

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}
    scope = {"type": "http", "method": "POST", "path": "/api/webhooks/paypal",
             "headers": [(k.encode(), v.encode()) for k, v in HDRS.items()]}
    return Request(scope, receive)


class FakeQuery:
    def __init__(self, store, model, kwargs):
        self.s, self.m, self.k = store, model, kwargs

    def filter_by(self, **kw):
        self.k.update(kw)
        return self

    def first(self):
        if self.m is models.WebhookEvent:
            return self.s["events"].get(self.k.get("event_id"))
        if self.m is models.Invoice:
            for inv in self.s["invoices"].values():
                if all(getattr(inv, k, None) == v for k, v in self.k.items()):
                    return inv
            return None
        if self.m is models.Payment:
            for p in self.s["payments"]:
                if all(getattr(p, k, None) == v for k, v in self.k.items()):
                    return p
            return None
        return None


class FakeInvoice:
    def __init__(self, pid="INV2-TEST"):
        self.id = 7
        self.project_id = 3
        self.paypal_invoice_id = pid
        self.status = "SENT"


class FakeDb:
    def __init__(self):
        self.s = {"events": {}, "invoices": {"INV2-TEST": FakeInvoice()},
                  "payments": []}

    def query(self, model):
        return FakeQuery(self.s, model, {})

    def add(self, row):
        if isinstance(row, models.WebhookEvent):
            if row.processed is None:
                row.processed = 0  # mirrors DB column default
            if row.event_id in self.s["events"]:
                self._dup = row
                return
            self._pending = row
        elif isinstance(row, models.Payment):
            self.s["payments"].append(row)

    def commit(self):
        if getattr(self, "_dup", None) is not None:
            self._dup = None
            raise IntegrityError("dup", {}, Exception("dup"))
        p = getattr(self, "_pending", None)
        if p is not None:
            self.s["events"][p.event_id] = p
            self._pending = None

    def rollback(self):
        self._dup = None
        self._pending = None


EV = {"id": "WH-T1", "event_type": "INVOICING.INVOICE.PAID",
      "resource": {"id": "INV2-TEST"}}
PAID = {"status": "PAID", "amount": {"value": "60.00", "currency_code": "USD"},
        "payments": {"paid_amount": {"value": "60.00", "currency_code": "USD"},
                     "transactions": [{"type": "PAYPAL", "payment_id": "PAY-9",
                                       "amount": {"value": "60.00",
                                                  "currency_code": "USD"}}]}}


def call(db, body):
    return asyncio.run(wh.paypal_webhook(make_req(body), db))


def main():
    results = []

    def t(name, cond):
        results.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name)

    # 1) genuine PAID -> recorded, processed=1
    db = FakeDb()
    with mock.patch.object(wh.paypal_client, "verify_webhook_signature", return_value=True), \
         mock.patch.object(wh.paypal_client, "get_invoice", return_value=PAID):
        r = call(db, dict(EV))
        ev = db.s["events"]["WH-T1"]
        t("paid_verified_processed",
          isinstance(r, dict) and r.get("status") == "PAID" and ev.processed == 1
          and len(db.s["payments"]) == 1 and db.s["invoices"]["INV2-TEST"].status == "PAID")

    # 2) event claims PAID but GET reads UNPAID -> synced, stays pending, 502
    db = FakeDb()
    with mock.patch.object(wh.paypal_client, "verify_webhook_signature", return_value=True), \
         mock.patch.object(wh.paypal_client, "get_invoice",
                           return_value={"status": "UNPAID"}):
        r = call(db, dict(EV, id="WH-T2"))
        ev = db.s["events"]["WH-T2"]
        t("unpaid_stays_pending",
          getattr(r, "status_code", 200) == 502 and ev.processed == 0
          and len(db.s["payments"]) == 0
          and db.s["invoices"]["INV2-TEST"].status == "UNPAID")

    # 3) PAID status but unverifiable records -> pending, invoice NOT marked PAID
    db = FakeDb()
    bad = dict(PAID)
    bad["payments"] = {"paid_amount": {"value": "60.00", "currency_code": "USD"},
                       "transactions": [{"type": "EXTERNAL", "payment_id": "X",
                                         "amount": {"value": "60.00", "currency_code": "USD"}}]}
    with mock.patch.object(wh.paypal_client, "verify_webhook_signature", return_value=True), \
         mock.patch.object(wh.paypal_client, "get_invoice", return_value=bad):
        r = call(db, dict(EV, id="WH-T3"))
        ev = db.s["events"]["WH-T3"]
        t("unverifiable_stays_pending_no_paid_mark",
          getattr(r, "status_code", 200) == 502 and ev.processed == 0
          and db.s["invoices"]["INV2-TEST"].status == "SENT"
          and len(db.s["payments"]) == 0)

    # 4) retry of pending event completes it (no duplicate payment)
    db = FakeDb()
    with mock.patch.object(wh.paypal_client, "verify_webhook_signature", return_value=True), \
         mock.patch.object(wh.paypal_client, "get_invoice",
                           side_effect=[{"status": "UNPAID"}, PAID]):
        r1 = call(db, dict(EV, id="WH-T4"))
        r2 = call(db, dict(EV, id="WH-T4"))
        t("retry_resumes_pending_once",
          getattr(r1, "status_code", 200) == 502
          and isinstance(r2, dict) and r2.get("status") == "PAID"
          and len(db.s["payments"]) == 1)

    # 5) invalid signature never stored
    db = FakeDb()
    with mock.patch.object(wh.paypal_client, "verify_webhook_signature", return_value=False):
        r = call(db, dict(EV, id="WH-F1"))
        t("bad_sig_rejected_unstored",
          getattr(r, "status_code", 0) == 400 and "WH-F1" not in db.s["events"])

    print(f"\n{sum(results)}/{len(results)} webhook tests passed.")
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
