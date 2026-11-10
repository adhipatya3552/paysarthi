"""Minimal PayPal webhook receiver (early validation, Day 1-4).
Security order: parse -> validate headers/structure -> verify signature
with PayPal -> THEN dedupe/insert (atomic UNIQUE constraint) -> process.
- Verified new: 2xx after persist.
- Verified duplicate: 2xx, no reprocessing.
- Invalid signature: 400 (never persisted). RETRY POLICY NOTE: PayPal
  retries ANY non-2xx up to ~25 times over 3 days, so a forged/invalid
  event will be redelivered and rejected again — this is intentional and
  harmless (no state change, no processing). Alternative would be 2xx to
  stop retries, but that would acknowledge an unverified event as handled
  and could mask an attack or misconfiguration (wrong WEBHOOK_ID). We
  chose fail-closed (400) over quiet-ack (2xx).
- Verify-API outage/token failure: 502 (retryable, PayPal resends).
Store: SQLite with PRIMARY KEY on event_id (atomic against concurrent
duplicate deliveries) + JSONL audit log of verified events only.
Run: uvicorn scripts.webhook_server:app --port 8000  (needs public HTTPS)
"""
import os, json, sqlite3
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()
BASE = "https://api-m.sandbox.paypal.com"
LOG = "scripts/webhook_log.jsonl"
DB = os.getenv("WEBHOOK_DB", "scripts/webhook_events.db")
app = FastAPI()

def db():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("CREATE TABLE IF NOT EXISTS processed"
                "(event_id TEXT PRIMARY KEY, event_type TEXT, resource_id TEXT)")
    return con

def is_processed(event_id: str) -> bool:
    con = db()
    try:
        return con.execute("SELECT 1 FROM processed WHERE event_id=?",
                           (event_id,)).fetchone() is not None
    finally:
        con.close()

def mark_processed(event_id: str, event_type: str, resource_id: str) -> bool:
    """Atomic insert. Returns True if newly inserted, False if duplicate.
    Retries on SQLite lock contention; a concurrent duplicate loses the
    race via UNIQUE constraint and is reported as duplicate."""
    import time as _time
    for attempt in range(5):
        con = db()
        try:
            con.execute("INSERT INTO processed(event_id,event_type,resource_id) VALUES(?,?,?)",
                        (event_id, event_type, resource_id))
            con.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # duplicate (possibly a concurrent twin)
        except sqlite3.OperationalError:
            _time.sleep(0.05 * (attempt + 1))
            continue
        finally:
            con.close()
    # Lock never cleared: do NOT claim processed and do NOT claim duplicate.
    # Caller treats this as transient failure (502) so PayPal retries.
    raise TimeoutError("sqlite busy: could not record event")

def get_token():
    r = requests.post(f"{BASE}/v1/oauth2/token",
        auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")),
        headers={"Accept": "application/json"}, data={"grant_type": "client_credentials"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def verify_signature(headers, webhook_id: str, event: dict, token: str) -> str:
    """Returns 'SUCCESS' / 'FAILURE' / raises on transport problems."""
    vr = requests.post(f"{BASE}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"transmission_id": headers.get("paypal-transmission-id"),
              "transmission_time": headers.get("paypal-transmission-time"),
              "cert_url": headers.get("paypal-cert-url"),
              "auth_algo": headers.get("paypal-auth-algo"),
              "transmission_sig": headers.get("paypal-transmission-sig"),
              "webhook_id": webhook_id,
              "webhook_event": event}, timeout=30)
    if vr.status_code != 200:
        raise ConnectionError(f"verify API HTTP {vr.status_code}")
    return vr.json().get("verification_status", "")

@app.post("/webhooks/paypal")
async def paypal_webhook(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    evid = body.get("id", "")
    if not evid or not isinstance(evid, str):
        return JSONResponse({"ok": False, "error": "missing_event_id"}, status_code=400)
    h = req.headers
    required = ["paypal-transmission-id", "paypal-transmission-time",
                "paypal-cert-url", "paypal-auth-algo", "paypal-transmission-sig"]
    if any(not h.get(k) for k in required) or not os.getenv("WEBHOOK_ID"):
        return JSONResponse({"ok": False, "error": "missing_verify_headers_or_webhook_id"},
                            status_code=400)
    # 1) VERIFY FIRST (before any dedupe decision)
    try:
        tok = get_token()
    except Exception:
        return JSONResponse({"ok": False, "error": "token_failed_retry_later"}, status_code=502)
    try:
        status = verify_signature(h, os.getenv("WEBHOOK_ID", ""), body, tok)
    except Exception:
        return JSONResponse({"ok": False, "error": "verify_unreachable_retry_later"}, status_code=502)
    if status != "SUCCESS":
        # invalid signature: never stored, never processed; 400 lets PayPal retry harmlessly
        return JSONResponse({"ok": False, "error": "invalid_signature"}, status_code=400)
    # 2) ONLY NOW dedupe + persist atomically
    rid = (body.get("resource") or {}).get("id", "")
    etype = body.get("event_type", "")
    try:
        is_new = mark_processed(evid, etype, rid)
    except TimeoutError:
        return JSONResponse({"ok": False, "error": "store_busy_retry_later"}, status_code=502)
    if not is_new:
        return {"ok": True, "duplicate": True, "event": etype}
    with open(LOG, "a") as f:
        f.write(json.dumps({"id": evid, "type": etype, "verified": True,
                            "resource_id": rid}) + "\n")
    return {"ok": True, "duplicate": False, "event": etype}

@app.get("/webhooks/health")
def health():
    return {"ok": True}
