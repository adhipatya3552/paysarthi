"""Direct unit tests for the auth helpers (no server, no network).
Empty config must authenticate nobody (fail-closed). Run:
python backend/test_auth_unit.py
"""
import sys, os
from types import SimpleNamespace
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backend.app.auth as auth
from fastapi import HTTPException

results = []


def t(name, cond):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)


real_pw = auth.DEMO_PASSWORD
try:
    # empty configuration: nobody authenticates
    auth.DEMO_PASSWORD = ""
    t("empty_check_password_false", auth.check_password("anything") is False)
    try:
        auth.require_demo(None)
        t("empty_require_demo_503", False)
    except HTTPException as e:
        t("empty_require_demo_503", e.status_code == 503)

    # configured password
    auth.DEMO_PASSWORD = "dummy-test-pw"
    t("wrong_check_password_false", auth.check_password("nope") is False)
    t("correct_check_password_true", auth.check_password("dummy-test-pw") is True)
    try:
        auth.require_demo(None)
        t("anon_require_demo_401", False)
    except HTTPException as e:
        t("anon_require_demo_401", e.status_code == 401)
    tok = auth.mint_token()
    t("token_accepted",
      auth.require_demo(SimpleNamespace(credentials=tok)) is True)
    try:
        auth.require_demo(SimpleNamespace(credentials="forged"))
        t("forged_require_demo_401", False)
    except HTTPException as e:
        t("forged_require_demo_401", e.status_code == 401)
finally:
    auth.DEMO_PASSWORD = real_pw

print(f"\n{sum(results)}/{len(results)} auth-unit tests passed.")
sys.exit(0 if all(results) else 1)
