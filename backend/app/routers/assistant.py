"""Feature 4b: AI assistant — Q&A over DB context, reminder drafts,
scope-change analysis. Drafts only; sending always needs human approval."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, ai_client
from ..auth import require_demo

router = APIRouter(prefix="/api/assistant", tags=["assistant"],
                   dependencies=[Depends(require_demo)])


def _context(db: Session) -> str:
    lines = []
    for i in db.query(models.Invoice).order_by(models.Invoice.id.desc()).limit(20).all():
        pays = "; ".join(f"{p.paypal_payment_id} {float(p.amount)} {p.currency}"
                         for p in i.payments) or "no payments recorded"
        lines.append(f"Invoice #{i.id} ({i.paypal_invoice_id or 'unsent'}): "
                     f"{float(i.amount)} {i.currency}, status {i.status}. {pays}.")
    return "\n".join(lines) or "No invoices yet."


@router.post("/ask")
def ask(body: schemas.AskIn, db: Session = Depends(get_db)):
    try:
        answer = ai_client.answer_about_invoices(body.question, _context(db))
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIError as e:
        raise HTTPException(502, f"AI failed: {e}")
    return {"answer": answer}


@router.post("/reminder")
def reminder(body: schemas.ReminderIn, db: Session = Depends(get_db)):
    inv = db.get(models.Invoice, body.invoice_id)
    if not inv:
        raise HTTPException(404, "invoice not found")
    project = db.get(models.Project, inv.project_id)
    name = project.client.name if project and project.client else "there"
    try:
        text = ai_client.draft_reminder(name, project.title if project else "project",
                                        float(inv.amount), inv.currency, 0)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIError as e:
        raise HTTPException(502, f"AI failed: {e}")
    return {"draft": text, "note": "DRAFT only — sending needs your approval"}


@router.post("/scope-check")
def scope_check(body: schemas.ScopeCheckIn, db: Session = Depends(get_db)):
    ag = (db.query(models.Agreement).filter_by(project_id=body.project_id)
          .order_by(models.Agreement.id.desc()).first())
    if not ag:
        raise HTTPException(404, "no agreement for this project")
    summary = (f"Title: {db.get(models.Project, body.project_id).title}; "
               f"Price {float(ag.price)} {ag.currency}; "
               f"Deliverables: {ag.deliverables}; Revisions: {ag.revision_limit}; "
               f"Extra terms: {ag.extra_work_terms}")
    try:
        verdict = ai_client.analyze_scope_change(summary, body.new_request)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIError as e:
        raise HTTPException(502, f"AI failed: {e}")
    return verdict
