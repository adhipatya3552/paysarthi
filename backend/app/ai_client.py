"""OpenAI-compatible LLM client (OpenRouter default). Structured JSON output
with validation; raises AINotConfigured when no key is present so endpoints
fail with a helpful message instead of a traceback."""
import json
import re
import requests
from . import config

AGREEMENT_SYSTEM = (
    "You extract freelance project details from informal client conversations "
    "(Hindi, Hinglish or English). Reply with ONLY a JSON object, no markdown, "
    "with keys: client_name, client_email, project_title, project_description, "
    "price (number), currency (3-letter code, default USD), deliverables "
    "(array of strings), deadline (string), revision_limit (integer, default 2), "
    "extra_work_terms (string), payment_terms (string). Use \"\" or defaults "
    "when a field is absent. Never invent an email address."
)


class AINotConfigured(Exception):
    pass


class AIError(Exception):
    pass


def _chat(system, user, max_tokens=1200, temperature=0.2):
    if not config.AI_API_KEY:
        raise AINotConfigured("AI_API_KEY is not set in .env")
    r = requests.post(f"{config.AI_BASE_URL.rstrip('/')}/chat/completions",
                      headers={"Authorization": f"Bearer {config.AI_API_KEY}",
                               "Content-Type": "application/json"},
                      json={"model": config.AI_MODEL,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}]},
                      timeout=60)
    if r.status_code != 200:
        raise AIError(f"AI HTTP {r.status_code}: {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise AIError(f"AI bad response: {e}")


def _balanced_objects(s: str):
    """Yield candidate JSON-object substrings via brace matching that
    respects string literals and escapes (handles nesting; ignores braces
    in trailing prose or inside strings)."""
    i, n = 0, len(s)
    while i < n:
        if s[i] != "{":
            i += 1
            continue
        depth, instr, esc, j = 0, False, False, i
        while j < n:
            ch = s[j]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
            else:
                if ch == '"':
                    instr = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        yield s[i:j + 1]
                        break
            j += 1
        i = j + 1 if (j < n and depth == 0) else i + 1


def _clean_json(raw: str) -> str:
    """Robustly extract a JSON object: strip think tags, prefer fenced code,
    then return the first balanced {...} that parses. Raises ValueError."""
    s = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.DOTALL).strip()
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s)
    candidates = [code_match.group(1).strip()] if code_match else []
    candidates.append(s)
    for cand in candidates:
        for obj in _balanced_objects(cand):
            try:
                json.loads(obj)
                return obj.strip()
            except ValueError:
                continue
    raise ValueError("no parseable JSON object found")


def extract_agreement(raw_text):
    """Returns a validated agreement dict from informal conversation text."""
    out = _chat(AGREEMENT_SYSTEM, raw_text)
    try:
        cleaned = _clean_json(out)
        data = json.loads(cleaned)
    except ValueError as e:
        raise AIError(f"AI did not return valid JSON: {e} (raw: {out[:120]})")
    if not isinstance(data, dict):
        raise AIError("AI JSON is not an object")
    try:
        price = float(data.get("price", 0) or 0)
    except (TypeError, ValueError):
        raise AIError("AI price is not a number")
    if price <= 0:
        raise AIError("AI could not determine a positive price — ask the user")
    data["price"] = round(price, 2)
    data["currency"] = (data.get("currency") or "USD").upper()[:10]
    if not isinstance(data.get("deliverables"), list):
        data["deliverables"] = [str(data.get("deliverables") or "")]
    data.setdefault("revision_limit", 2)
    for k in ("client_name", "client_email", "project_title", "project_description",
              "deadline", "extra_work_terms", "payment_terms"):
        data.setdefault(k, "")
    return data


def draft_reminder(client_name, project_title, amount, currency, days_overdue):
    return _chat(
        "You write short polite freelancer payment reminders. Plain text, no subject line.",
        f"Client {client_name} owes {amount} {currency} for '{project_title}', "
        f"{days_overdue} days overdue. Draft a friendly 4-line reminder with the amount.",
        max_tokens=300).strip()


def analyze_scope_change(agreement_summary, new_request):
    """Compares a new client request against the agreement; JSON verdict."""
    out = _chat(
        "You are a scope-change analyst. Reply with ONLY a JSON object: "
        "{\"in_scope\": true/false, \"reason\": string, "
        "\"suggested_extra_price\": number or 0, \"draft_reply\": string}.",
        f"AGREEMENT:\n{agreement_summary}\n\nNEW CLIENT REQUEST:\n{new_request}",
        max_tokens=800)
    try:
        data = json.loads(_clean_json(out))
    except ValueError as e:
        raise AIError(f"AI scope analysis is not JSON: {e}")
    data.setdefault("in_scope", True)
    data.setdefault("reason", "")
    data.setdefault("suggested_extra_price", 0)
    data.setdefault("draft_reply", "")
    return data


def answer_about_invoices(question, context):
    return _chat(
        "You are PaySarthi, a concise assistant for a freelancer's PayPal invoices. "
        "Answer only from the provided context. Never invent payments.",
        f"CONTEXT:\n{context}\n\nQUESTION:\n{question}",
        max_tokens=600).strip()
