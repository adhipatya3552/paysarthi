"""Pydantic request/response schemas."""
from typing import List, Optional
from pydantic import BaseModel, Field


class AgreementCreate(BaseModel):
    raw_text: str = Field(min_length=10, max_length=20000)


class AgreementOut(BaseModel):
    id: int
    project_id: int
    client_name: str
    client_email: str
    project_title: str = ""
    project_description: str = ""
    price: float
    currency: str
    deliverables: List[str] = []
    deadline: str = ""
    revision_limit: int = 2
    extra_work_terms: str = ""
    payment_terms: str = ""
    quotation_text: str = ""
    approved: bool = False


class ApproveIn(BaseModel):
    approved: bool = True


class AgreementUpdate(BaseModel):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    project_title: Optional[str] = None
    project_description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    deliverables: Optional[List[str]] = None
    deadline: Optional[str] = None
    revision_limit: Optional[int] = None
    extra_work_terms: Optional[str] = None
    payment_terms: Optional[str] = None


class InvoicePrepare(BaseModel):
    agreement_id: int
    client_email: Optional[str] = None
    due_days: int = 7


class ReminderIn(BaseModel):
    invoice_id: int


class ScopeCheckIn(BaseModel):
    project_id: int
    new_request: str = Field(min_length=3, max_length=5000)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
