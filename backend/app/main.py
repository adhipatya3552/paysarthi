"""PaySarthi FastAPI entrypoint. Run: uvicorn backend.app.main:app --port 8000"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from . import models  # noqa: F401  (register tables)
from . import auth
from .config import FRONTEND_URL
from .routers import agreements, invoices, webhooks, dashboard, assistant

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    import logging
    from sqlalchemy import create_engine as _ce
    from . import database as _db
    logging.warning(f"Database connect failed ({e}). Falling back to local SQLite.")
    _db.engine = _ce("sqlite:///./paysarthi.db", connect_args={"check_same_thread": False})
    _db.SessionLocal.configure(bind=_db.engine)
    Base.metadata.create_all(bind=_db.engine)

app = FastAPI(title="PaySarthi", version="0.1.0")
app.add_middleware(CORSMiddleware,
                   allow_origins=[FRONTEND_URL, "http://localhost:3000",
                                  "http://127.0.0.1:3000"],
                   allow_methods=["GET", "POST", "PUT", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type", "X-Demo-Password"])

app.include_router(agreements.router)
app.include_router(invoices.router)
app.include_router(webhooks.router)
app.include_router(dashboard.router)
app.include_router(assistant.router)


@app.post("/api/login")
def login(body: auth.LoginIn):
    from fastapi import HTTPException
    from .config import DEMO_PASSWORD
    if not DEMO_PASSWORD:
        raise HTTPException(503, "demo password not configured on server")
    if not auth.check_password(body.password):
        raise HTTPException(401, "wrong password")
    return {"token": auth.mint_token()}


@app.get("/api/health")
def health():
    return {"ok": True, "environment": "SANDBOX"}
