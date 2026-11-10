"""Minimal single-user demo gate. Password lives in DEMO_PASSWORD (backend env
only, never sent to the frontend bundle). POST /api/login {password} mints a
random in-memory bearer token; protected routes require it. The PayPal
webhook endpoint is NOT behind this gate (it uses PayPal signatures).
Fail-closed: with DEMO_PASSWORD empty, login and protected routes refuse
(503) instead of opening the app to anyone. Set DEMO_PASSWORD in .env."""
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
        return False  # fail-closed: no password configured, no login
    return secrets.compare_digest(pw, DEMO_PASSWORD)


def require_demo(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not DEMO_PASSWORD:
        raise HTTPException(503, "demo password not configured on server")
    if not creds or creds.credentials not in _tokens:
        raise HTTPException(401, "demo login required")
    return True
