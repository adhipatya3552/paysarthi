"""One-off: import verified Sandbox invoice 0002 as historical record.
Run once: python backend/import_history.py (idempotent via UNIQUE constraints).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.database import SessionLocal
from backend.app import models, paypal_client

INV = "INV2-TWVF-QYYA-47RL-UVVU"
db = SessionLocal()
live = paypal_client.get_invoice(INV)
ok, info = paypal_client.verify_paid(live)
print("status=", live.get("status"), "verify=", ok, info)
assert ok is True, "historical invoice is not genuinely PAID — aborting import"

det = live.get("detail") or {}
recips = live.get("primary_recipients") or []
buyer = ((recips[0].get("billing_info") if recips else {}) or {}).get("email_address", "")
client = db.query(models.Client).filter_by(email=buyer).first()
if not client:
    client = models.Client(name="US Sandbox Buyer", email=buyer, country="US")
    db.add(client); db.flush()
proj = db.query(models.Project).filter_by(title="Logo design - Day1 test").first()
if not proj:
    proj = models.Project(client_id=client.id, title="Logo design - Day1 test",
                          description="Historical Sandbox validation project")
    db.add(proj); db.flush()
ag = db.query(models.Agreement).filter_by(project_id=proj.id).first()
if not ag:
    ag = models.Agreement(project_id=proj.id, raw_input="(historical Sandbox import)",
                          client_name="US Sandbox Buyer", client_email=buyer,
                          price=float(info["amount"]), currency=info["currency"],
                          deliverables='["Logo design"]', approved=1,
                          quotation_text="Historical import of verified Sandbox invoice 0002.")
    db.add(ag); db.flush()
inv = db.query(models.Invoice).filter_by(paypal_invoice_id=INV).first()
if not inv:
    inv = models.Invoice(project_id=proj.id, agreement_id=ag.id, paypal_invoice_id=INV,
                         invoice_number=det.get("invoice_number", "0002"),
                         amount=float(info["amount"]), currency=info["currency"],
                         status="PAID", hosted_url=paypal_client.hosted_url_of(live))
    db.add(inv); db.flush()
if not db.query(models.Payment).filter_by(paypal_payment_id=info["payment_id"]).first():
    db.add(models.Payment(invoice_id=inv.id, paypal_payment_id=info["payment_id"],
                          amount=float(info["amount"]), currency=info["currency"],
                          verified_via="api"))
    db.add(models.ActivityLog(project_id=proj.id, invoice_id=inv.id,
                              message=f"Historical import: payment {info['payment_id']} "
                                      f"({info['amount']} {info['currency']}) verified via API"))
db.commit()
print(f"IMPORTED: client={client.id} project={proj.id} invoice={inv.id} (idempotent)")
