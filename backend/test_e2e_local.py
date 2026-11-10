"""E2E steps 1-9 minus HTTP auth (auth gate tested separately over HTTP):
new agreement (live AI) -> edit via PUT -> approve -> invoice prepare.
STOPS before PayPal send. Cleans up its test rows. No invoices created.
Run: python backend/test_e2e_local.py
"""
import os, sys
os.environ["AI_MODEL"] = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.database import SessionLocal
from backend.app import models, schemas
from backend.app.routers import agreements, invoices

results = []


def t(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


db = SessionLocal()
try:
    ag = agreements.create_agreement(
        schemas.AgreementCreate(raw_text=(
            "Bhai ek US client hai, logo chahiye $150 me, 4 din me delivery. "
            "2 revision free, extra $10 each. Email client@example.com")),
        db)
    t("e2e_agreement_created", ag["price"] == 150 and ag["currency"] == "USD",
      f"id={ag['id']} price={ag['price']}")
    t("e2e_email_not_invented", ag["client_email"] == "client@example.com",
      ag["client_email"])
    aid = ag["id"]
    pid = ag["project_id"]

    ag2 = agreements.update_agreement(
        aid, schemas.AgreementUpdate(deadline="4 days", revision_limit=2), db)
    t("e2e_edit_saved", ag2["deadline"] == "4 days", ag2["deadline"])

    ag3 = agreements.approve_agreement(aid, schemas.ApproveIn(approved=True), db)
    t("e2e_approved", ag3["approved"] is True)

    pv = invoices.prepare_invoice(
        schemas.InvoicePrepare(agreement_id=aid), db)
    item = pv["items"][0]
    t("e2e_prepare_preview",
      item["unit_amount"]["value"] == "150.00"
      and item["unit_amount"]["currency_code"] == "USD"
      and pv["recipient"] == "client@example.com", str(item["unit_amount"]))
    t("e2e_no_paypal_invoice_yet", pv["existing"] is None)

    print("STOPPING before POST /api/invoices/send (needs your confirmation).")
finally:
    # cleanup test rows, keep dashboard pristine for the demo
    db.query(models.ActivityLog).filter_by(project_id=pid).delete()
    db.query(models.Agreement).filter_by(id=aid).delete()
    db.query(models.Project).filter_by(id=pid).delete()
    db.query(models.Client).filter(
        models.Client.email == "client@example.com",
        models.Client.id.notin_(db.query(models.Project.client_id).distinct())).delete(
        synchronize_session=False)
    db.commit()
    db.close()

print(f"\n{sum(results)}/{len(results)} e2e checks passed.")
sys.exit(0 if all(results) else 1)
