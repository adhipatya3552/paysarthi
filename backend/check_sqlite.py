"""SQLite compatibility probe on an ISOLATED temp database.
Never touches MariaDB. Run: python backend/check_sqlite.py
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app import models  # noqa: register tables

tmp = os.path.join(tempfile.mkdtemp(), "probe.db")
eng = create_engine(f"sqlite:///{tmp}")
Base.metadata.create_all(bind=eng)
S = sessionmaker(bind=eng)
db = S()
c = models.Client(name="T", email="t@x.io")
db.add(c)
db.flush()
p = models.Project(client_id=c.id, title="P")
db.add(p)
db.flush()
ag = models.Agreement(project_id=p.id, raw_input="x", price=10, currency="USD")
inv = models.Invoice(project_id=p.id, paypal_invoice_id="INV2-TEST",
                     amount=10, currency="USD", status="DRAFT")
db.add_all([ag, inv])
db.flush()
pay = models.Payment(invoice_id=inv.id, paypal_payment_id="PAY-1",
                     amount=10, currency="USD")
ev = models.WebhookEvent(event_id="WH-1", event_type="X", verified=1)
log = models.ActivityLog(project_id=p.id, message="m")
db.add_all([pay, ev, log])
db.commit()
assert db.query(models.Invoice).count() == 1
assert db.query(models.Payment).count() == 1
# duplicate payment + duplicate webhook must fail (integrity)
from sqlalchemy.exc import IntegrityError
for dup in (models.Payment(invoice_id=inv.id, paypal_payment_id="PAY-1",
                           amount=10, currency="USD"),
            models.WebhookEvent(event_id="WH-1")):
    db.add(dup)
    try:
        db.commit()
        print("FAIL: duplicate accepted")
        sys.exit(1)
    except IntegrityError:
        db.rollback()
print("SQLITE_OK: schema, CRUD, unique constraints all work on SQLite")
