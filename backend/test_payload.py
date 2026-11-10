"""Payload parity tests for detail.payment_terms. Pure unit tests on
_build_payload: no PayPal calls, no DB, no network.
Run: python backend/test_payload.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.routers.invoices import _build_payload


class FakeAg:
    def __init__(self, terms):
        self.id = 99
        self.currency = "USD"
        self.price = 150
        self.deadline = "4 days"
        self.payment_terms = terms
        self.quotation_text = "Q"


results = []


def t(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


# 1) normal terms land in detail.payment_terms; note/memo untouched
d, it = _build_payload(FakeAg("50% advance, balance on delivery"), "Logo")
t("terms_in_payload", d.get("payment_terms") == "50% advance, balance on delivery")
t("note_unchanged", d["note"] == "Logo — 4 days", d["note"])
t("memo_unchanged", d["memo"] == "paysarthi-agreement-99", d["memo"])
t("no_split_payment_invented", len(it) == 1 and it[0]["unit_amount"]["value"] == "150.00")

# 2) Hinglish/Hindi terms preserved byte-identical
hi = "50% advance, delivery par balance. Payment PayPal se."
d2, _ = _build_payload(FakeAg(hi), "Website")
t("hindi_terms_preserved", d2.get("payment_terms") == hi)

# 3) missing/empty terms: key omitted, nothing breaks
d3, _ = _build_payload(FakeAg(""), "Logo")
d4, _ = _build_payload(FakeAg(None), "Logo")
t("empty_terms_omitted", "payment_terms" not in d3 and "payment_terms" not in d4)

# 4) over-limit terms rejected, never truncated
try:
    _build_payload(FakeAg("x" * 2501), "Logo")
    t("overlimit_rejected", False, "no error raised")
except ValueError as e:
    t("overlimit_rejected", "2500" in str(e), str(e)[:80])
d5, _ = _build_payload(FakeAg("y" * 2500), "Logo")
t("limit_boundary_ok", len(d5["payment_terms"]) == 2500)

# 5) preview and send share the builder (single source of truth)
import inspect
import backend.app.routers.invoices as inv
src_prepare = inspect.getsource(inv.prepare_invoice)
src_send = inspect.getsource(inv.send_invoice)
t("shared_builder",
  src_prepare.count("_build_payload") == 1 and src_send.count("_build_payload") == 1)

print(f"\n{sum(results)}/{len(results)} payload tests passed.")
sys.exit(0 if all(results) else 1)
