"""PayPal Invoicing integration. Reuses the verified Day-1 flow:
OAuth client-credentials -> create (201) -> send -> GET verify.
Robust invoice-ID extraction (the Day-1 parsing lesson): prefers the
`id` field, falls back to HATEOAS self-links. `Prefer:
return=representation` requests the full object on create so the ID is
present even when PayPal returns a minimal body. Secrets are never logged.
"""
import re
import requests
from decimal import Decimal
from . import config

INV_ID_RE = re.compile(r"INV2-[A-Z0-9-]+", re.IGNORECASE)

_token_cache = {"token": "", "expiry": 0}


class PayPalError(Exception):
    pass


def access_token():
    import time
    if _token_cache["token"] and _token_cache["expiry"] - time.time() > 60:
        return _token_cache["token"]
    r = requests.post(f"{config.PAYPAL_BASE}/v1/oauth2/token",
                      auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
                      headers={"Accept": "application/json", "Accept-Language": "en_US"},
                      data={"grant_type": "client_credentials"}, timeout=30)
    if r.status_code != 200:
        raise PayPalError(f"oauth HTTP {r.status_code}")
    data = r.json()
    import time as _t
    _token_cache.update(token=data.get("access_token", ""),
                        expiry=_t.time() + int(data.get("expires_in", 300)))
    if not _token_cache["token"]:
        raise PayPalError("oauth: no access_token")
    return _token_cache["token"]


def _extract_invoice_id(data):
    """Robust ID extraction: id field -> self link -> any INV2-... string."""
    if isinstance(data, dict):
        if data.get("id", "").startswith("INV2-"):
            return data["id"]
        for link in data.get("links", []) or []:
            href = link.get("href", "")
            m = INV_ID_RE.search(href)
            if m:
                return m.group(0).upper()
        blob = str(data)
        m = INV_ID_RE.search(blob)
        if m:
            return m.group(0).upper()
    raise PayPalError("create: no invoice ID in response")


def create_draft(detail, invoicer_email, recipient_email, items):
    tok = access_token()
    body = {"detail": detail, "invoicer": {"email_address": invoicer_email},
            "primary_recipients": [{"billing_info": {"email_address": recipient_email}}],
            "items": items}
    r = requests.post(f"{config.PAYPAL_BASE}/v2/invoicing/invoices",
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json",
                               "Prefer": "return=representation"},
                      json=body, timeout=30)
    if r.status_code != 201:
        raise PayPalError(f"create HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    return _extract_invoice_id(data), data


def send_invoice(invoice_id, send_to_recipient=True):
    tok = access_token()
    r = requests.post(f"{config.PAYPAL_BASE}/v2/invoicing/invoices/{invoice_id}/send",
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"},
                      json={"send_to_recipient": send_to_recipient,
                            "send_to_invoicer": True}, timeout=30)
    if r.status_code not in (200, 202):
        raise PayPalError(f"send HTTP {r.status_code}: {r.text[:300]}")
    return True


def get_invoice(invoice_id):
    tok = access_token()
    r = requests.get(f"{config.PAYPAL_BASE}/v2/invoicing/invoices/{invoice_id}",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if r.status_code != 200:
        raise PayPalError(f"get HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def hosted_url_of(inv):
    return (inv.get("recipient_view_url", "")
            or ((inv.get("detail") or {}).get("metadata") or {}).get("recipient_view_url", ""))


def verify_paid(inv):
    """Decimal-exact genuine-payment check. Returns (ok, info|reason)."""
    status = inv.get("status")
    if status == "MARKED_AS_PAID":
        return False, "MARKED_AS_PAID is an external record, not a PayPal payment"
    if status != "PAID":
        return None, f"status={status}"
    exp = inv.get("amount") or {}
    try:
        exp_amt, exp_cur = Decimal(str(exp["value"])), exp["currency_code"]
    except Exception:
        return False, "invoice amount missing"
    pay = inv.get("payments") or {}
    paid = pay.get("paid_amount") or {}
    try:
        if Decimal(str(paid.get("value"))) != exp_amt or paid.get("currency_code") != exp_cur:
            return False, "paid_amount != invoice total"
    except Exception:
        return False, "paid_amount unparseable"
    txns = [tx for tx in (pay.get("transactions") or [])
            if tx.get("type") == "PAYPAL" and tx.get("payment_id")]
    if not txns:
        return False, "no PAYPAL transaction"
    total = sum((Decimal(str((tx.get("amount") or {}).get("value", "0")))
                 for tx in txns
                 if (tx.get("amount") or {}).get("currency_code") == exp_cur),
                Decimal("0"))
    if total != exp_amt:
        return False, f"PAYPAL sum {total} != total {exp_amt}"
    return True, {"payment_id": txns[0]["payment_id"],
                  "amount": str(total), "currency": exp_cur}


def verify_webhook_signature(headers, webhook_id, event):
    tok = access_token()
    r = requests.post(f"{config.PAYPAL_BASE}/v1/notifications/verify-webhook-signature",
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"},
                      json={"transmission_id": headers.get("paypal-transmission-id"),
                            "transmission_time": headers.get("paypal-transmission-time"),
                            "cert_url": headers.get("paypal-cert-url"),
                            "auth_algo": headers.get("paypal-auth-algo"),
                            "transmission_sig": headers.get("paypal-transmission-sig"),
                            "webhook_id": webhook_id,
                            "webhook_event": event}, timeout=30)
    if r.status_code != 200:
        raise PayPalError(f"verify API HTTP {r.status_code}")
    return r.json().get("verification_status") == "SUCCESS"
