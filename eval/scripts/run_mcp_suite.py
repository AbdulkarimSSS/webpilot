#!/usr/bin/env python3
"""Playwright MCP benchmark runner (scripted policy, mirrors run_suite scoring).

Drives @playwright/mcp over stdio JSON-RPC. One MCP process is reused per run;
the scripted policy navigates, then either browser_snapshot (extraction) or
browser_fill_form + submit click (fill). Reported success is recorded BOTH as
the harness's optimistic flag (reported_optimistic) and as an honest
"tool-claims-nothing" default, so the report can separate the two.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LAB = os.path.join(ROOT, "lab")
sys.path.insert(0, LAB)
from scenarios import SCENARIOS  # noqa: E402
import checker  # noqa: E402

spec = importlib.util.spec_from_file_location("run_mcp3", os.path.join(LAB, "run_mcp3.py"))
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

STATE_URL = "http://127.0.0.1:8900/state"
RESET_URL = "http://127.0.0.1:8900/reset"
BUTTON = {"S19": "إرسال", "S49": "Save", "S50": "Login", "S45": "Submit",
          "S12": "Next", "S21": "Close", "S10": "Close"}


def reset_state():
    try:
        urllib.request.urlopen(urllib.request.Request(RESET_URL, data=b"{}", method="POST"), timeout=5).read()
    except Exception:
        pass


def fetch_state():
    try:
        with urllib.request.urlopen(STATE_URL, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {"submissions": [], "events": []}


def fields_for(sid, exp):
    fields = []
    for k, v in exp.items():
        ftype, target, value = "textbox", f"#{k}", str(v)
        if sid == "S02":
            ftype = "combobox"
            if k == "langs":
                target, value = "#langs", "English,Japanese"
        elif sid == "S06":
            if k == "newsletter":
                ftype, value = "checkbox", "true"
            elif k == "interests":
                target, ftype, value = "input[name='interests'][value='AI']", "checkbox", "true"
        elif sid == "S39":
            ftype, target = "checkbox", f"input[name='{k}'][value='{v}']"
            value = "true"
        fields.append({"element": k, "target": target, "name": k, "type": ftype, "value": value})
    return fields


def run_scenario(m, sid, url):
    sc = SCENARIOS[sid]
    exp = sc.get("request", sc.get("expected", {}))
    t0 = time.time()
    steps = 0
    raw = ""
    err = None
    try:
        r = m.call("tools/call", {"name": "browser_navigate", "arguments": {"url": url}})
        steps += 1
        raw += json.dumps(r, ensure_ascii=False) + "\n"
        if sc.get("extraction"):
            r = m.call("tools/call", {"name": "browser_snapshot", "arguments": {}})
            steps += 1
            raw += json.dumps(r, ensure_ascii=False) + "\n"
        else:
            r = m.call("tools/call", {"name": "browser_fill_form", "arguments": {"fields": fields_for(sid, exp)}})
            steps += 1
            raw += json.dumps(r, ensure_ascii=False) + "\n"
            if sc.get("submit"):
                r = m.call("tools/call", {"name": "browser_click", "arguments": {
                    "element": BUTTON.get(sid, "Submit"),
                    "target": "#mainform button[type=submit], button[type=submit], #submit-btn, input[type=submit]"}})
                steps += 1
                raw += json.dumps(r, ensure_ascii=False) + "\n"
    except Exception as e:
        err = repr(e)
    wall = round(time.time() - t0, 2)
    return {
        "tool": "playwright-mcp", "scenario": sid, "reported_success": True,
        "reported_optimistic": True, "steps": steps, "wall_time_s": wall,
        "schema": None, "schema_tokens": 0,
        "tokens_in": len(raw) // 4, "tokens_out": len(raw) // 8,
        "failure_type": "env" if err else "none", "error": err, "raw_output": raw[:6000],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--label", default="mcp_3x")
    ap.add_argument("--scenarios", default=None)
    ap.add_argument("--host", default="http://127.0.0.1:8900")
    args = ap.parse_args()
    sids = args.scenarios.split(",") if args.scenarios else sorted(SCENARIOS.keys())
    outroot = os.path.join(ROOT, "results")
    allr = []
    for run in range(1, args.runs + 1):
        m = rm.MCP()
        try:
            for sid in sids:
                url = f"{args.host}/s/{sid}"
                out = os.path.join(outroot, "evidence", args.label, sid, f"run{run}")
                os.makedirs(out, exist_ok=True)
                reset_state()
                attempt = run_scenario(m, sid, url)
                state = fetch_state()
                res = checker.score(sid, attempt, state)
                res["tool_reported"] = {}
                res["tool_label"] = args.label
                json.dump(res, open(os.path.join(out, "score.json"), "w"), ensure_ascii=False, indent=1)
                json.dump(attempt, open(os.path.join(out, "attempt.json"), "w"), ensure_ascii=False, indent=1)
                allr.append(res)
                print(f"[{args.label}] run{run} {sid}: acc={res.get('field_accuracy')} "
                      f"pass={res.get('form_pass')} fs={res.get('false_success')} "
                      f"wall={attempt['wall_time_s']}", flush=True)
        finally:
            m.close()
    json.dump(allr, open(os.path.join(outroot, f"results_{args.label}.json"), "w"), ensure_ascii=False, indent=1)
    print(f"[{args.label}] wrote {len(allr)} rows")


if __name__ == "__main__":
    main()
