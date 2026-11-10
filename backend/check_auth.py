"""Auth gate check over HTTP: protected routes reject anonymous, login
rejects wrong password. Never attempts a correct login (password unknown).
Run: python backend/check_auth.py (starts server on :8001 briefly).
"""
import subprocess, sys, time, json, urllib.request, urllib.error

p = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app",
                      "--port", "8001"],
                     cwd=r"D:\Builds\paypal-hackathon",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ok = []


def t(name, cond):
    ok.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)


def code(method, url, body=None):
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method=method)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status
    except urllib.error.HTTPError as e:
        return e.code


try:
    time.sleep(12)
    t("dashboard_anon_401", code("GET", "http://127.0.0.1:8001/api/dashboard") == 401)
    t("agreements_anon_401", code("POST", "http://127.0.0.1:8001/api/agreements",
                                  json.dumps({"raw_text": "x" * 20}).encode()) == 401)
    t("login_wrong_401", code("POST", "http://127.0.0.1:8001/api/login",
                              json.dumps({"password": "definitely-wrong"}).encode()) == 401)
    t("webhook_not_behind_demo_gate",
      code("POST", "http://127.0.0.1:8001/api/webhooks/paypal",
           json.dumps({"id": "x"}).encode()) == 400)  # 400=structure, not 401
    t("health_public", code("GET", "http://127.0.0.1:8001/api/health") == 200)
finally:
    p.terminate()
print(f"\n{sum(ok)}/{len(ok)} auth checks passed.")
sys.exit(0 if all(ok) else 1)
