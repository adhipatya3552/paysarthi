"""Feature 1: paste conversation -> AI extraction -> editable review -> approve."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, ai_client
from ..auth import require_demo

router = APIRouter(prefix="/api/agreements", tags=["agreements"],
                   dependencies=[Depends(require_demo)])


def _quotation(a: dict) -> str:
    lines = [f"QUOTATION — {a.get('project_title') or 'Project'}", "",
             f"Client: {a.get('client_name') or '-'} ({a.get('client_email') or '-'})",
             f"Price: {a['price']} {a['currency']}",
             f"Deadline: {a.get('deadline') or '-'}",
             f"Revisions included: {a.get('revision_limit', 2)}", "",
             "Deliverables:"]
    for d in a.get("deliverables") or []:
        lines.append(f"  - {d}")
    if a.get("extra_work_terms"):
        lines += ["", f"Additional work: {a['extra_work_terms']}"]
    lines += ["", (a.get("payment_terms")
                   or "50% advance via PayPal invoice, balance on delivery.")]
    return "\n".join(lines)


@router.post("", response_model=schemas.AgreementOut)
def create_agreement(body: schemas.AgreementCreate, db: Session = Depends(get_db)):
    try:
        a = ai_client.extract_agreement(body.raw_text)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIError as e:
        raise HTTPException(422, f"AI extraction failed: {e}")
    client = None
    if a.get("client_email"):
        client = db.query(models.Client).filter_by(email=a["client_email"]).first()
    if client is None:
        # Never invent contact details: missing email stays missing ("").
        client = models.Client(name=a.get("client_name") or "Unknown client",
                               email=a.get("client_email") or "")
        db.add(client)
        db.flush()
    project = models.Project(client_id=client.id,
                             title=a.get("project_title") or "Untitled project",
                             description=a.get("project_description") or "")
    db.add(project)
    db.flush()
    ag = models.Agreement(
        project_id=project.id, raw_input=body.raw_text,
        client_name=a.get("client_name") or "", client_email=a.get("client_email") or "",
        price=a["price"], currency=a["currency"],
        deliverables=json.dumps(a.get("deliverables") or []),
        deadline=a.get("deadline") or "", revision_limit=int(a.get("revision_limit") or 2),
        extra_work_terms=a.get("extra_work_terms") or "",
        payment_terms=a.get("payment_terms") or "",
        quotation_text=_quotation(a))
    db.add(ag)
    db.flush()
    db.add(models.ActivityLog(project_id=project.id,
                              message=f"Agreement #{ag.id} drafted by AI, awaiting review"))
    db.commit()
    return _out(ag, project.title, project.description)


@router.get("/{agreement_id}", response_model=schemas.AgreementOut)
def get_agreement(agreement_id: int, db: Session = Depends(get_db)):
    ag = db.get(models.Agreement, agreement_id)
    if not ag:
        raise HTTPException(404, "agreement not found")
    project = db.get(models.Project, ag.project_id)
    return _out(ag, project.title if project else "",
                project.description if project else "")


def _as_dict(ag, title: str) -> dict:
    try:
        items = json.loads(ag.deliverables or "[]")
    except ValueError:
        items = []
    return {"project_title": title, "client_name": ag.client_name,
            "client_email": ag.client_email, "price": float(ag.price),
            "currency": ag.currency, "deliverables": items, "deadline": ag.deadline,
            "revision_limit": ag.revision_limit, "extra_work_terms": ag.extra_work_terms,
            "payment_terms": ag.payment_terms}


@router.put("/{agreement_id}", response_model=schemas.AgreementOut)
def update_agreement(agreement_id: int, body: schemas.AgreementUpdate,
                     db: Session = Depends(get_db)):
    ag = db.get(models.Agreement, agreement_id)
    if not ag:
        raise HTTPException(404, "agreement not found")
    if ag.approved:
        raise HTTPException(409, "approved agreements are locked — create a new one to change terms")
    data = body.model_dump(exclude_unset=True)
    if "client_email" in data and data["client_email"] not in (None, "") \
            and "@" not in data["client_email"]:
        raise HTTPException(422, "client email is invalid")
    if "price" in data and (data["price"] is None or data["price"] <= 0):
        raise HTTPException(422, "price must be positive")
    if "currency" in data and data["currency"]:
        data["currency"] = data["currency"].upper()[:10]
    if "revision_limit" in data and data["revision_limit"] is not None \
            and data["revision_limit"] < 0:
        raise HTTPException(422, "revision limit cannot be negative")
    if "deliverables" in data and data["deliverables"] is not None:
        ag.deliverables = json.dumps([str(x) for x in data.pop("deliverables")])
    project = db.get(models.Project, ag.project_id)
    for key in ("client_name", "client_email", "price", "currency", "deadline",
                "revision_limit", "extra_work_terms", "payment_terms"):
        if key in data and data[key] is not None:
            setattr(ag, key, data[key])
    if "project_title" in data and data["project_title"] and project:
        project.title = data["project_title"][:300]
    if "project_description" in data and data["project_description"] is not None \
            and project:
        project.description = data["project_description"]
    ag.quotation_text = _quotation(_as_dict(ag, project.title if project else ""))
    db.add(models.ActivityLog(project_id=ag.project_id,
                              message=f"Agreement #{ag.id} edited before approval"))
    db.commit()
    return get_agreement(agreement_id, db)


@router.post("/{agreement_id}/approve", response_model=schemas.AgreementOut)
def approve_agreement(agreement_id: int, body: schemas.ApproveIn,
                      db: Session = Depends(get_db)):
    ag = db.get(models.Agreement, agreement_id)
    if not ag:
        raise HTTPException(404, "agreement not found")
    ag.approved = 1 if body.approved else 0
    db.add(models.ActivityLog(project_id=ag.project_id,
                              message=f"Agreement #{ag.id} "
                                      f"{'approved' if body.approved else 'sent back'} by freelancer"))
    db.commit()
    return get_agreement(agreement_id, db)


def _out(ag: models.Agreement, title: str, description: str = "") -> dict:
    try:
        items = json.loads(ag.deliverables or "[]")
    except ValueError:
        items = []
    return {"id": ag.id, "project_id": ag.project_id, "client_name": ag.client_name,
            "client_email": ag.client_email, "project_title": title,
            "project_description": description,
            "price": float(ag.price), "currency": ag.currency, "deliverables": items,
            "deadline": ag.deadline, "revision_limit": ag.revision_limit,
            "extra_work_terms": ag.extra_work_terms, "payment_terms": ag.payment_terms,
            "quotation_text": ag.quotation_text, "approved": bool(ag.approved)}
