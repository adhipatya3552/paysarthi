"""Feature 4a: dashboard aggregates grouped per currency (no FX invention).
DB truth only — live PayPal state is read per-invoice page."""
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import require_demo
from .. import models

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"],
                   dependencies=[Depends(require_demo)])


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    invoices = db.query(models.Invoice).all()
    payments = db.query(models.Payment).all()
    by_cur: dict = {}

    def bucket(cur):
        return by_cur.setdefault(cur, {"invoiced": Decimal("0"), "paid": Decimal("0")})

    for i in invoices:
        bucket(i.currency)["invoiced"] += i.amount
    inv_by_id = {i.id: i for i in invoices}
    for p in payments:
        bucket(inv_by_id[p.invoice_id].currency
               if p.invoice_id in inv_by_id else p.currency)["paid"] += p.amount
    totals = {}
    for cur, v in by_cur.items():
        totals[cur] = {"invoiced": float(v["invoiced"]), "paid": float(v["paid"]),
                       "pending": float(v["invoiced"] - v["paid"])}
    by_status: dict = {}
    for i in invoices:
        by_status[i.status] = by_status.get(i.status, 0) + 1
    pending = [i for i in invoices if i.status in ("SENT", "UNPAID", "VIEWED", "OVERDUE")]
    recent = (db.query(models.Payment).order_by(models.Payment.id.desc()).limit(10).all())
    log = (db.query(models.ActivityLog).order_by(models.ActivityLog.id.desc()).limit(20).all())
    return {
        "totals_by_currency": totals,
        "invoice_count": len(invoices),
        "by_status": by_status,
        "pending": [{"id": i.id, "paypal_invoice_id": i.paypal_invoice_id,
                     "amount": float(i.amount), "currency": i.currency,
                     "status": i.status} for i in pending],
        "recent_payments": [{"paypal_payment_id": p.paypal_payment_id,
                             "invoice_id": p.invoice_id, "amount": float(p.amount),
                             "currency": p.currency, "via": p.verified_via} for p in recent],
        "timeline": [{"kind": a.kind, "message": a.message,
                      "at": a.created_at.isoformat() if a.created_at else None}
                     for a in log],
        "active_projects": db.query(models.Project).filter_by(status="active").count(),
        "environment": "SANDBOX",
    }
