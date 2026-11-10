"""PaySarthi MySQL schema. Every invoice keeps its PayPal invoice ID (UNIQUE);
every payment keeps its PayPal payment ID (UNIQUE); webhook events are
deduplicated by PayPal event ID (PRIMARY KEY)."""
from sqlalchemy import (Column, Integer, String, Text, Numeric, DateTime,
                        ForeignKey, Enum, func)
from sqlalchemy.orm import relationship
from .database import Base

InvoiceStatus = ("DRAFT", "SENT", "UNPAID", "VIEWED", "PARTIALLY_PAID",
                 "PAID", "MARKED_AS_PAID", "CANCELLED", "OVERDUE", "REFUNDED")


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=False, index=True)
    country = Column(String(100), default="")
    created_at = Column(DateTime, server_default=func.now())
    projects = relationship("Project", back_populates="client")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, server_default=func.now())
    client = relationship("Client", back_populates="projects")
    agreements = relationship("Agreement", back_populates="project")
    invoices = relationship("Invoice", back_populates="project")


class Agreement(Base):
    __tablename__ = "agreements"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    raw_input = Column(Text, nullable=False)
    client_name = Column(String(200), default="")
    client_email = Column(String(320), default="")
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    deliverables = Column(Text, default="")          # JSON list as text
    deadline = Column(String(100), default="")
    revision_limit = Column(Integer, default=2)
    extra_work_terms = Column(Text, default="")
    payment_terms = Column(Text, default="")
    quotation_text = Column(Text, default="")        # rendered English agreement
    approved = Column(Integer, default=0)            # 0/1 human approval gate
    created_at = Column(DateTime, server_default=func.now())
    project = relationship("Project", back_populates="agreements")


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    agreement_id = Column(Integer, ForeignKey("agreements.id"), nullable=True)
    paypal_invoice_id = Column(String(60), unique=True, index=True)   # INV2-...
    invoice_number = Column(String(60), default="")
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(Enum(*InvoiceStatus, name="invoice_status"), default="DRAFT", index=True)
    hosted_url = Column(Text, default="")
    due_date = Column(String(50), default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project = relationship("Project", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    paypal_payment_id = Column(String(60), unique=True, index=True)   # PAY-... / capture id
    paypal_txn_type = Column(String(20), default="PAYPAL")
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    verified_via = Column(String(20), default="api")  # api | webhook
    received_at = Column(DateTime, server_default=func.now())
    invoice = relationship("Invoice", back_populates="payments")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    event_id = Column(String(100), primary_key=True)  # PayPal event id -> dedupe
    event_type = Column(String(100), default="", index=True)
    paypal_invoice_id = Column(String(60), default="", index=True)
    verified = Column(Integer, default=0)
    processed = Column(Integer, default=0)
    payload = Column(Text, default="")                # raw event JSON
    received_at = Column(DateTime, server_default=func.now())


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)
    kind = Column(String(100), nullable=False, default="note", index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
