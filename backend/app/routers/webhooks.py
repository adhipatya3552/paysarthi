"""POST /api/webhooks/paypal — verify-first, idempotent PayPal receiver.
Same security order as the validated Day-1 script: headers -> verify
signature -> atomic dedupe (PRIMARY KEY). Events stuck at processed=0
(GET failed mid-handling) are RESUMED on PayPal retry instead of being
acked as done. A webhook alone is never proof: every PAID is re-read from
PayPal and Decimal-verified before a payment is recorded."""
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..database import get_db
from .. import models, paypal_client
from ..config import WEBHOOK_ID
from .invoices import _record_payment

router = APIRouter(tags=["webhooks"])


@router.post("/api/webhooks/paypal")
async def paypal_webhook(req: Request, db: Session = Depends(get_db)):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    evid = body.get("id", "")
    if not evid or not isinstance(evid, str):
        return JSONResponse({"ok": False, "error": "missing_event_id"}, status_code=400)
    h = req.headers
    required = ("paypal-transmission-id", "paypal-transmission-time", "paypal-cert-url",
                "paypal-auth-algo", "paypal-transmission-sig")
    if any(not h.get(k) for k in required) or not WEBHOOK_ID:
        return JSONResponse({"ok": False, "error": "missing_verify_headers"}, status_code=400)
    try:
        verified = paypal_client.verify_webhook_signature(h, WEBHOOK_ID, body)
    except paypal_client.PayPalError:
        return JSONResponse({"ok": False, "error": "verify_unreachable_retry_later"},
                            status_code=502)
    if not verified:
        return JSONResponse({"ok": False, "error": "invalid_signature"}, status_code=400)
    etype = body.get("event_type", "")
    resource = body.get("resource") or {}
    paypal_inv = resource.get("id", "") if isinstance(resource, dict) else ""
    if not str(paypal_inv).startswith("INV2-"):
        paypal_inv = (resource.get("invoice_id", "") or "").upper()
    row = models.WebhookEvent(event_id=evid, event_type=etype,
                              paypal_invoice_id=paypal_inv, verified=1,
                              payload=json.dumps(body)[:8000])
    db.add(row)
    try:
        db.commit()
        fresh = True
    except IntegrityError:
        db.rollback()
        row = db.query(models.WebhookEvent).filter_by(event_id=evid).first()
        if row is None or row.processed:
            return {"ok": True, "duplicate": True, "event": etype}
        fresh = False  # processed=0: resume unfinished work below
    return _handle(db, row, fresh)


def _handle(db, row, fresh):
    """Settle one verified event. processed=1 ONLY after the invoice was
    re-read AND a final state was reached:
    - genuine PAID (verify_paid True) -> record, mark processed
    - any other readable status (SENT/UNPAID/...) -> sync status, mark processed
      (event delivered its news; a later PAID arrives as a new event)
    - unreadable invoice or PAID-with-unverifiable records -> processed stays 0,
      return 502 so PayPal retries and the next delivery resumes.
    verify_paid False is never recorded as a payment."""
    if row.event_type == "INVOICING.INVOICE.PAID" and row.paypal_invoice_id:
        inv = db.query(models.Invoice).filter_by(
            paypal_invoice_id=row.paypal_invoice_id).first()
        if inv is None:
            row.processed = 1  # not ours; nothing to settle
            db.commit()
            return {"ok": True, "duplicate": not fresh, "event": row.event_type,
                    "note": "invoice unknown to PaySarthi"}
        try:
            live = paypal_client.get_invoice(row.paypal_invoice_id)
        except paypal_client.PayPalError as e:
            db.commit()  # persist processed=0; retry will resume
            return JSONResponse({"ok": False,
                                 "error": f"paypal_read_failed_retry_later: {e}"},
                                status_code=502)
        status = live.get("status")
        if status == "PAID":
            ok, info = paypal_client.verify_paid(live)
            if ok is True:
                _record_payment(db, inv, info["payment_id"], info["amount"],
                                info["currency"], "webhook")
                inv.status = "PAID"
                row.processed = 1
                db.commit()
                return {"ok": True, "duplicate": not fresh, "event": row.event_type,
                        "status": "PAID"}
            # PAID claimed but records incomplete/unverifiable: stay pending.
            db.commit()
            return JSONResponse({"ok": False,
                                 "error": f"paid_unverifiable_retry_later: {info}"},
                                status_code=502)
        if status in ("SENT", "UNPAID", "VIEWED", "CANCELLED", "OVERDUE",
                      "REFUNDED", "PARTIALLY_PAID", "DRAFT", "MARKED_AS_PAID"):
            # Event claims PAID but PayPal doesn't (yet): sync the visible
            # status, but keep processed=0 so the next retry re-checks.
            if status != inv.status:
                inv.status = status
            db.commit()
            return JSONResponse({"ok": False,
                                 "error": f"not_paid_yet_retry_later: {status}"},
                                status_code=502)
        db.commit()  # unknown status shape: stay pending, retry resumes
        return JSONResponse({"ok": False,
                             "error": f"unknown_status_retry_later: {status}"},
                            status_code=502)
    row.processed = 1
    db.commit()
    return {"ok": True, "duplicate": not fresh, "event": row.event_type}
