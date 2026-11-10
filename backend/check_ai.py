"""Live AI check with the free-tier model. Read-only LLM calls only:
no invoices, no emails, no PayPal writes. Prints extracted JSON + verdicts.
Run: python backend/check_ai.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app import ai_client

EN = ("My US client wants a logo for $150. Delivery in 4 days. Two revisions "
      "included. Extra revisions are $10 each. Client email is client@example.com.")
HINGLISH = ("Bhai ek US client hai, usko website chahiye 5 page wali, budget $400 bola hai, "
            "delivery 10 din me chahiye. 3 revision free, uske baad $15 per revision lagega. "
            "Client ka email founder@startup.io hai.")

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(name)


try:
    a = ai_client.extract_agreement(EN)
    print(json.dumps(a, indent=1)[:900])
    check("en_price_150", a["price"] == 150, a["price"])
    check("en_currency_usd", a["currency"] == "USD", a["currency"])
    check("en_email_exact", a["client_email"] == "client@example.com", a["client_email"])
    check("en_revisions_2", a["revision_limit"] == 2, a["revision_limit"])
    check("en_extra_terms", "$10" in (a["extra_work_terms"] or ""), a["extra_work_terms"])
    check("en_deadline", "4" in (a["deadline"] or ""), a["deadline"])
except Exception as e:
    check("en_extraction_runs", False, f"{type(e).__name__}: {str(e)[:200]}")

try:
    h = ai_client.extract_agreement(HINGLISH)
    print(json.dumps(h, indent=1)[:900])
    check("hi_price_400", h["price"] == 400, h["price"])
    check("hi_currency_usd", h["currency"] == "USD", h["currency"])
    check("hi_email_exact", h["client_email"] == "founder@startup.io", h["client_email"])
    check("hi_revisions_3", h["revision_limit"] == 3, h["revision_limit"])
except Exception as e:
    check("hi_extraction_runs", False, f"{type(e).__name__}: {str(e)[:200]}")

try:
    r = ai_client.draft_reminder("Test Client", "Logo", 150, "USD", 5)
    check("reminder_draft", len(r) > 20 and "150" in r, r[:120].replace("\n", " "))
except Exception as e:
    check("reminder_draft", False, f"{type(e).__name__}: {str(e)[:200]}")

try:
    s = ai_client.analyze_scope_change(
        "Logo design, $150, 2 revisions included, extra $10 each",
        "Client now also wants a full website homepage design")
    check("scope_flags_extra", s.get("in_scope") is False and s.get("draft_reply", ""),
          str(s)[:160].replace("\n", " "))
except Exception as e:
    check("scope_flags_extra", False, f"{type(e).__name__}: {str(e)[:200]}")

print(f"\n{4 - len([f for f in fails])} groups checked, failures: {fails or 'none'}")
sys.exit(1 if fails else 0)
