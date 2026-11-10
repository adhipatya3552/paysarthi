# PaySarthi — From Hindi conversations to verified international payments

PaySarthi is an AI-powered cross-border payment assistant for **Indian freelancers**
receiving international client payments through **PayPal**. It turns informal
Hindi/Hinglish/English chat into a structured agreement, prepares and sends a real
PayPal Sandbox invoice after explicit human approval, verifies the actual payment,
and keeps a tamper-honest ledger. Built for the **PayPal AI Hackathon**.

> **Sandbox honesty:** one genuine $60.00 USD Sandbox payment (invoice `0002`,
> India merchant → US buyer) was API-verified `PAID` with a `PAYPAL` transaction.
> A second $150 agreement was AI-extracted, edited, approved, and invoice-**previewed**
> — but never sent or paid. No simulated payments exist anywhere in the app.

## How it works

1. **Paste chat** (Hindi/Hinglish/English) → AI extracts client, price, deliverables,
   deadline, revisions, terms → editable review → **you approve**.
2. **Stage A — preview** a PayPal invoice from the approved agreement.
3. **Stage B — confirm & send**: a real PayPal Sandbox invoice is created + sent;
   the hosted payment URL is shown. Nothing sends without your click.
4. Buyer pays on PayPal → app re-reads the invoice (`GET`), validates
   `PAID` + `PAYPAL` transaction + payment ID + exact amount/currency
   (`verify_paid()`), optionally via verified `INVOICING.INVOICE.PAID` webhooks.
5. Dashboard shows verified totals per currency, timeline, and history.
6. **AI assistant** answers questions from real invoice data, drafts reminders
   (never sends), and flags out-of-scope client requests.

`MARKED_AS_PAID` (external records) never counts as a PayPal payment.
Webhooks alone are never proof — every payment is re-read from PayPal.

## Architecture

```text
Next.js 16 (frontend/) ──REST──▶ FastAPI (backend/app) ──▶ MySQL/MariaDB (or SQLite)
                                     │                            ▲
                                     ├─ PayPal Invoicing API v2 ───┘ (create/send/get,
                                     │   webhooks + signature verify)  no escrow/payouts
                                     └─ OpenAI-compatible LLM (OpenRouter, free-tier model)
```

## Tech stack

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS v4, Motion, Phosphor icons
- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0, PyMySQL, Requests, Pydantic
- Database: MariaDB 10.4+ (primary; SQLite verified as fallback via `DATABASE_URL`)
- AI: OpenRouter (`AI_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`,
  free tier) — structured-JSON extraction with balanced-brace parsing + validation
- PayPal (Sandbox): OAuth2, `POST/GET /v2/invoicing/invoices`,
  `POST .../send`, `INVOICING.INVOICE.PAID` webhooks,
  `POST /v1/notifications/verify-webhook-signature`

## Prerequisites

- Python 3.13, Node.js 20+, MariaDB 10.4+ running locally
  (or set `DATABASE_URL=sqlite:///./local.db` to skip MariaDB entirely)
- A PayPal Developer account with Sandbox Business (India) + Personal (US) test
  accounts and a REST app with Invoicing enabled
- A free OpenRouter API key (free-tier `:free` models only — no spend)

## Setup

```powershell
cd D:\Builds\paypal-hackathon
Copy-Item .env.example .env   # then fill: PayPal sandbox creds, AI key, DB, DEMO_PASSWORD
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt        # Day-1 validation kit
python -m pip install -r backend/requirements.txt
```

Create the database (MariaDB): `CREATE DATABASE paysarthi CHARACTER SET utf8mb4;`
Tables auto-create on backend start. For SQLite instead, set in `.env`:
`DATABASE_URL=sqlite:///./local.db` (verified: `python backend/check_sqlite.py`).

**Demo password (fail-closed):** the backend refuses login and all app APIs
with HTTP 503 until `DEMO_PASSWORD` is set in `.env` — there is no open mode.
Judges: set any `DEMO_PASSWORD` locally and share that value (never the `.env`
file) with anyone you admit to the demo. The PayPal webhook endpoint is
unaffected: it authenticates via PayPal signatures, not this password.

## Run

```powershell
# Terminal 1 — backend :8000
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --port 8000
# Terminal 2 — frontend :3000
cd frontend; npm install; npm run dev
```

Open http://localhost:3000 → log in with `DEMO_PASSWORD` → dashboard.

## Tests (no PayPal writes, no secrets printed)

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall backend scripts
.\.venv\Scripts\python.exe scripts/test_day1_local.py      # Day-1 kit: 13 checks
.\.venv\Scripts\python.exe backend/test_json_parse.py      # AI JSON hardening: 10
.\.venv\Scripts\python.exe backend/test_payload.py         # payment_terms parity: 9
.\.venv\Scripts\python.exe backend/test_webhooks.py        # webhook edge cases: 5
.\.venv\Scripts\python.exe backend/test_integration.py     # gate + history intact
.\.venv\Scripts\python.exe backend/check_auth_matrix.py   # fail-closed matrix (9) + SQLite app boot
.\.venv\Scripts\python.exe backend/test_auth_unit.py      # auth helpers direct (7)
.\.venv\Scripts\python.exe backend/check_sqlite.py        # SQLite schema/CRUD smoke test
cd frontend; npm run build
```

Live-AI checks (`backend/check_ai.py`: EN/Hinglish extraction, reminders,
scope analysis) and the full agreement→preview flow (`backend/test_e2e_local.py`)
need `AI_API_KEY` in `.env` and stop before any PayPal send.

## Known limitations (honest)

- Sandbox only; Sandbox does not enforce Indian KYC/PAN/bank rules, so this
  proves the API workflow, not live Indian production eligibility (needs a live
  Indian Business account + full KYC at go-live).
- Multi-user SaaS on others' PayPal accounts needs PayPal Partner approval;
  current builds use per-user credentials (BYO-keys model).
- Free-tier AI models can be rate-limited upstream; errors surface verbatim.
- `detail.payment_term` (structured due dates) is not used — free-text
  `detail.payment_terms` only; no split/partial payments.
- FIRA/permit compliance is out of scope (PayPal issues FIRA from its dashboard).

## License

MIT — see [LICENSE](LICENSE).
