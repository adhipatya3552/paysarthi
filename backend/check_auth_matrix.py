"""Portable auth matrix: isolated subprocess servers, dummy credentials only.
No .env read, no real secrets, no MariaDB writes (temp SQLite), no PayPal calls.
Safe to run after a fresh clone (needs installed deps + backend code only).
Run: python backend/check_auth_matrix.py
"""
import subprocess, sys, time, json, tempfile, os
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
ok = []


def t(name, cond):
    ok.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)


def call(port, method, path, body=None, tok=None):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, ""


def boot(port, extra_env):
    env = dict(os.environ)
    env.update(extra_env)
    tmp = os.path.join(tempfile.mkdtemp(), "matrix.db")
    env["DATABASE_URL"] = f"sqlite:///{tmp}"
    # Always override: the test must never inherit real credentials.
    env["PAYPAL_CLIENT_ID"] = "dummy"
    env["PAYPAL_CLIENT_SECRET"] = "dummy"
    env["PAYPAL_ENVIRONMENT"] = "SANDBOX"
    env["AI_API_KEY"] = ""
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app",
                          "--port", str(port)], cwd=str(ROOT),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    time.sleep(12)
    return p, tmp


DUMMY_PW = "matrix-dummy-password-1"

# --- Case A: empty password (fail-closed) ---
p, tmp = boot(8011, {"DEMO_PASSWORD": ""})
try:
    s, _ = call(8011, "GET", "/api/health")
    t("A_sqlite_boot_health_200", s == 200)
    t("A_sqlite_tables_created", os.path.exists(tmp) and os.path.getsize(tmp) > 0)
    s, _ = call(8011, "POST", "/api/login", {"password": "anything"})
    t("A_empty_pw_login_503", s == 503)
    s, _ = call(8011, "GET", "/api/dashboard")
    t("A_empty_pw_dashboard_503", s == 503)
finally:
    p.terminate()

# --- Cases B-E: dummy password configured ---
p, _ = boot(8012, {"DEMO_PASSWORD": DUMMY_PW})
try:
    s, _ = call(8012, "POST", "/api/login", {"password": "wrong"})
    t("B_wrong_pw_401", s == 401)
    s, body = call(8012, "POST", "/api/login", {"password": DUMMY_PW})
    tok = json.loads(body).get("token", "") if s == 200 else ""
    t("C_correct_pw_200_token", s == 200 and len(tok) > 20)
    s, _ = call(8012, "GET", "/api/dashboard", tok=tok)
    t("C_token_opens_dashboard", s == 200)
    s, _ = call(8012, "GET", "/api/dashboard", tok="forged-token")
    t("D_forged_token_401", s == 401)
    s, _ = call(8012, "GET", "/api/dashboard")
    t("E_anon_protected_401", s == 401)
finally:
    p.terminate()

print(f"\n{sum(ok)}/{len(ok)} auth-matrix checks passed.")
sys.exit(0 if all(ok) else 1)
