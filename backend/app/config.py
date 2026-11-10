"""PaySarthi backend settings. Secrets come from root .env only. Nothing secret is logged."""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

PAYPAL_ENVIRONMENT = os.getenv("PAYPAL_ENVIRONMENT", "SANDBOX")
PAYPAL_BASE = ("https://api-m.sandbox.paypal.com"
               if PAYPAL_ENVIRONMENT.upper() != "LIVE" else "https://api-m.paypal.com")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MERCHANT_EMAIL = os.getenv("PAYPAL_MERCHANT_EMAIL", "")
PAYPAL_BUYER_EMAIL = os.getenv("PAYPAL_BUYER_EMAIL", "")
WEBHOOK_ID = os.getenv("WEBHOOK_ID", "")

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
# Free-tier default, verified working 2026-11-09 (llama-3.3 :free and gemma :free
# were unavailable/rate-limited on a free account). Override in .env.
AI_MODEL = os.getenv("AI_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "paysarthi")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)
# DATABASE_URL override (e.g. sqlite:///./local.db) lets judges run without
# MariaDB. SQLite is verified compatible (backend/check_sqlite.py); MariaDB
# remains the primary documented database.
