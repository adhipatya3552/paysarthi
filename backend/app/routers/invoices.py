"""Feature 2+3: invoice preview (from approved agreement) -> human approval ->
PayPal create+send -> GET verification -> DB + timeline. No auto-send.
Idempotent: one PayPal invoice per agreement; retries resume, never duplicate."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, paypal_client
from ..auth import require_demo
from ..config import PAYPAL_MERCHANT_EMAIL

router = APIRouter(prefix="/api/invoices", tags=["invoices"],
                   dependencies=[Depends(require_demo)])


@router.post("/prepare")
def prepare_invoice(body: schemas.InvoicePrepare, db: Session = Depends(get_db)):
    ag = db.get(models.Agreement, body.agreement_id)
    if not ag:
        raise HTTPException(404, "agreement not found")
    if not ag.approved:
        raise HTTPException(409, "approve the agreement before preparing an invoice")
    email = body.client_email or ag.client_email
    if not email or "@" not in email:
        raise HTTPException(422, "client email is missing — edit it before invoicing")
    project = db.get(models.Project, ag.project_id)
    try:
        detail, items = _build_payload(ag, project.title if project else "Project")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"agreement_id": ag.id, "project_id": ag.project_id,
            "invoicer": PAYPAL_MERCHANT_EMAIL, "recipient": email,
            "detail": detail, "items": items,
            "payment_terms": detail.get("payment_terms", ""),
            "existing": _existing_summary(db, ag.id)}


def _build_payload(ag, project_title):
    """Single source of truth for the PayPal invoice body: preview and send
    use this, so what the freelancer approves is exactly what PayPal gets.
    Free-text terms go in detail.payment_terms (PayPal allows 2500 chars);
    note and memo are left untouched. Over-long terms are rejected, never
    silently truncated. No split-payment or partial-payment logic here."""
    terms = (ag.payment_terms or "").strip()
    if len(terms) > 2500:
        raise ValueError("payment terms exceed PayPal's 2500-character limit — "
                         "please shorten them before invoicing")
    detail = {"currency_code": ag.currency,
              "note": f"{project_title} — {ag.deadline or 'as agreed'}",
              "memo": f"paysarthi-agreement-{ag.id}"}
    if terms:
        detail["payment_terms"] = terms
    items = [{"name": project_title[:120],
              "description": (ag.quotation_text or "")[:500],
              "quantity": "1",
              "unit_amount": {"currency_code": ag.currency,
                              "value": f"{float(ag.price):.2f}"}}]
    return detail, items


def _existing_summary(db, agreement_id):
    inv = (db.query(models.Invoice).filter_by(agreement_id=agreement_id)
           .filter(models.Invoice.paypal_invoice_id.isnot(None))
           .order_by(models.Invoice.id.desc()).first())
    if not inv:
        return None
    return {"id": inv.id, "paypal_invoice_id": inv.paypal_invoice_id,
            "status": inv.status, "hosted_url": inv.hosted_url}


@router.post("/send")
def send_invoice(body: schemas.InvoicePrepare, db: Session = Depends(get_db)):
    """Human-approved send. Idempotent per agreement: an existing PayPal
    invoice is resumed (re-read / re-sent), never recreated."""
    ag = db.get(models.Agreement, body.agreement_id)
    if not ag:
        raise HTTPException(404, "agreement not found")
    if not ag.approved:
        raise HTTPException(409, "approve the agreement before sending an invoice")
    email = body.client_email or ag.client_email
    if not email or "@" not in email:
        raise HTTPException(422, "client email is missing")

    existing = (db.query(models.Invoice).filter_by(agreement_id=ag.id)
                .filter(models.Invoice.paypal_invoice_id.isnot(None))
                .order_by(models.Invoice.id.desc()).first())
    if existing:
        return _resume(db, existing)

    project = db.get(models.Project, ag.project_id)
    try:
        detail, items = _build_payload(ag, project.title if project else "Project")
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        inv_id, _ = paypal_client.create_draft(detail, PAYPAL_MERCHANT_EMAIL, email, items)
    except paypal_client.PayPalError as e:
        raise HTTPException(502, f"PayPal create failed (no invoice created): {e}")
    # Commit the record BEFORE sending: a later failure must never lose the ID.
    inv = models.Invoice(project_id=ag.project_id, agreement_id=ag.id,
                         paypal_invoice_id=inv_id, amount=float(ag.price),
                         currency=ag.currency, status="DRAFT")
    db.add(inv)
    db.commit()
    return _resume(db, inv)


def _resume(db, inv):
    """Bring one local invoice to its true PayPal state: send if DRAFT,
    re-read otherwise. Never creates a second PayPal invoice."""
    try:
        live = paypal_client.get_invoice(inv.paypal_invoice_id)
    except paypal_client.PayPalError as e:
        raise HTTPException(502, f"PayPal read failed, local record kept "
                                 f"({inv.paypal_invoice_id}, {inv.status}): {e}")
    status = live.get("status", inv.status)
    if status == "DRAFT":
        try:
            paypal_client.send_invoice(inv.paypal_invoice_id)
        except paypal_client.PayPalError as e:
            db.add(models.ActivityLog(project_id=inv.project_id, invoice_id=inv.id,
                                      message=f"Send failed for {inv.paypal_invoice_id}, kept DRAFT: {e}"))
            db.commit()
            raise HTTPException(502, f"PayPal send failed (kept {inv.paypal_invoice_id} as DRAFT): {e}")
        try:
            live = paypal_client.get_invoice(inv.paypal_invoice_id)
        except paypal_client.PayPalError as e:
            inv.status = "SENT"  # send succeeded; re-read failed — record survives
            db.commit()
            return _out(inv, note=f"sent, re-read failed (retry refresh): {e}")
        status = live.get("status", "SENT")
    inv.status = status if status in models.InvoiceStatus else inv.status
    if not inv.hosted_url:
        inv.hosted_url = paypal_client.hosted_url_of(live)
    det = live.get("detail") or {}
    if det.get("invoice_number"):
        inv.invoice_number = det["invoice_number"]
    warning = None
    if status == "PAID":
        ok, info = paypal_client.verify_paid(live)
        if ok is True:
            _record_payment(db, inv, info["payment_id"], info["amount"],
                            info["currency"], "api")
        else:
            warning = f"status PAID but verification inconclusive: {info}"
    db.add(models.ActivityLog(project_id=inv.project_id, invoice_id=inv.id,
                              message=f"Invoice {inv.paypal_invoice_id} synced: {inv.status}"))
    db.commit()
    return _out(inv, warning=warning)


def _out(inv, note=None, warning=None):
    d = {"id": inv.id, "paypal_invoice_id": inv.paypal_invoice_id,
         "invoice_number": inv.invoice_number, "status": inv.status,
         "hosted_url": inv.hosted_url, "amount": float(inv.amount),
         "currency": inv.currency}
    if note:
        d["note"] = note
    if warning:
        d["warning"] = warning
    return d


@router.get("/{invoice_id}")
def invoice_detail(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "invoice not found")
    live_status, warning = None, None
    if inv.paypal_invoice_id:
        try:
            body = paypal_client.get_invoice(inv.paypal_invoice_id)
            live_status = body.get("status")
            if live_status == "PAID":
                ok, info = paypal_client.verify_paid(body)
                if ok is True:
                    _record_payment(db, inv, info["payment_id"], info["amount"],
                                    info["currency"], "api")
                    inv.status = "PAID"
                else:
                    warning = f"PayPal says PAID but records unverified: {info}"
            elif live_status in ("SENT", "UNPAID", "VIEWED", "CANCELLED",
                                 "OVERDUE", "REFUNDED", "PARTIALLY_PAID"):
                inv.status = live_status
            if not inv.hosted_url:
                inv.hosted_url = paypal_client.hosted_url_of(body)
            db.commit()
        except paypal_client.PayPalError:
            live_status = None  # sandbox hiccup: serve DB state, don't fail the page
    return {"id": inv.id, "paypal_invoice_id": inv.paypal_invoice_id,
            "invoice_number": inv.invoice_number, "amount": float(inv.amount),
            "currency": inv.currency, "status": inv.status, "hosted_url": inv.hosted_url,
            "live_status": live_status, "warning": warning,
            "payments": [{"paypal_payment_id": p.paypal_payment_id,
                          "amount": float(p.amount), "currency": p.currency,
                          "verified_via": p.verified_via,
                          "received_at": p.received_at.isoformat() if p.received_at else None}
                         for p in inv.payments],
            "timeline": [{"kind": a.kind, "message": a.message,
                          "at": a.created_at.isoformat() if a.created_at else None}
                         for a in db.query(models.ActivityLog)
                         .filter_by(invoice_id=inv.id).order_by(models.ActivityLog.id).all()]}


@router.post("/{invoice_id}/refresh")
def refresh_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Poll-style verification: re-read PayPal, record genuine PAID once."""
    inv = db.get(models.Invoice, invoice_id)
    if not inv or not inv.paypal_invoice_id:
        raise HTTPException(404, "invoice not found or not yet sent to PayPal")
    try:
        live = paypal_client.get_invoice(inv.paypal_invoice_id)
    except paypal_client.PayPalError as e:
        raise HTTPException(502, f"PayPal read failed: {e}")
    ok, info = paypal_client.verify_paid(live)
    if ok is True:
        _record_payment(db, inv, info["payment_id"], info["amount"],
                        info["currency"], "api")
        inv.status = "PAID"
        db.commit()
        return {"status": "PAID", "payment": info}
    if ok is False:
        raise HTTPException(409, f"payment integrity failed: {info}")
    inv.status = live.get("status", inv.status)
    db.commit()
    return {"status": inv.status, "note": info}


def _record_payment(db, inv, payment_id, amount, currency, via):
    if db.query(models.Payment).filter_by(paypal_payment_id=payment_id).first():
        return False
    db.add(models.Payment(invoice_id=inv.id, paypal_payment_id=payment_id,
                          amount=float(amount), currency=currency, verified_via=via))
    db.add(models.ActivityLog(project_id=inv.project_id, invoice_id=inv.id,
                              message=f"Payment {payment_id} ({amount} {currency}) "
                                      f"verified via {via}"))
    return True
