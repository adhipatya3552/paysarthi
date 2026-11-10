"""Minimal single-user demo gate. Password lives in DEMO_PASSWORD (backend env
only, never sent to the frontend bundle). POST /api/login {password} mints a
random in-memory bearer token; protected routes require it. The PayPal
webhook endpoint is NOT behind this gate (it uses PayPal signatures).
If DEMO_PASSWORD is empty, the gate is open (local dev convenience)."""
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from .config import DEMO_PASSWORD

_tokens: set = set()
_bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    password: str = ""


def mint_token() -> str:
    tok = secrets.token_urlsafe(32)
    _tokens.add(tok)
    return tok


def check_password(pw: str) -> bool:
    if not DEMO_PASSWORD:
        return True  # dev mode: open gate allows any demo password
    return secrets.compare_digest(pw, DEMO_PASSWORD)


def require_demo(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not DEMO_PASSWORD:
        return True  # dev mode: gate open until a password is configured
    if not creds or creds.credentials not in _tokens:
        raise HTTPException(401, "demo login required")
    return True
