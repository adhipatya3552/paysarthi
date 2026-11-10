"""Focused tests for _clean_json: think tags, fences, preambles, nesting,
trailing junk, truncation. No network. Run: python backend/test_json_parse.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.ai_client import _clean_json
import json

results = []


def t(name, raw, expect=None, fail=False):
    try:
        got = json.loads(_clean_json(raw))
        ok = (not fail) and (expect is None or got == expect)
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" got={got}"))
        results.append(ok)
    except ValueError as e:
        ok = fail
        print(("PASS " if ok else "FAIL ") + name + (f" (raised as expected)" if ok else f" raised: {e}"))
        results.append(ok)


t("plain", '{"a": 1}', {"a": 1})
t("fence", '```json\n{"a": 1}\n```', {"a": 1})
t("preamble", 'Sure! Here you go:\n{"a": 1}', {"a": 1})
t("think_tags", '<think>reasoning here {not json}</think>\n{"a": 1}', {"a": 1})
t("nested", 'x {"a": {"b": [1, {"c": "}"}]}} y', {"a": {"b": [1, {"c": "}"}]}})
t("brace_in_string", '{"msg": "use } wisely", "a": 1}', {"msg": "use } wisely", "a": 1})
t("trailing_junk", '{"a": 1} hope this helps! } bye', {"a": 1})
t("two_objects_first_wins", '{"a": 1} {"b": 2}', {"a": 1})
t("truncated", '{"a": 1, "b": ', fail=True)
t("no_json", 'hello world', fail=True)

print(f"\n{sum(results)}/{len(results)} json-parse tests passed.")
sys.exit(0 if all(results) else 1)
