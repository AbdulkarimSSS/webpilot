#!/usr/bin/env python3
"""Unified benchmark runner: WebPilot (CLI) and Baseline (hand Playwright).

Records the tool's *self-reported* per-field tri-state (confirmed / unconfirmed /
failed) as printed by the 2.0.5+ verification code, plus the checker's ground
truth, so a confusion matrix for the verification feature can be computed.

Usage:
  python3 run_suite.py --tool webpilot --wp /path/to/wp --runs 3 --out-dir results [--scenarios S01,S02,...]
  python3 run_suite.py --tool baseline --runs 3 --out-dir results
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.join(os.path.dirname(HERE), "lab")
sys.path.insert(0, LAB)

from scenarios import SCENARIOS  # noqa: E402
import checker  # noqa: E402

STATE_URL = "http://127.0.0.1:8900/state"
RESET_URL = "http://127.0.0.1:8900/reset"

BUTTON = {"S19": "\u0625\u0631\u0633\u0627\u0644", "S49": "Save", "S50": "Login", "S45": "Submit", "S27": "Submit"}


def token_estimate(text):
    return int(len(text or "") / 4)


def reset_state():
    try:
        req = urllib.request.Request(RESET_URL, data=b"{}", method="POST")
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


def port_in_use(port=9333):
    import socket
    s = socket.socket()
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def reap_supervisors():
    """Harness mitigation for the auto-spawn/token-desync defect: ensure a clean
    daemon per scenario so the benchmark measures fill behaviour, not the
    supervisor's startup race. Documented in REPORT.md (mitigation, not a fix)."""
    subprocess.run(["pkill", "-f", "supervisor/master_daemon.py"], capture_output=True)
    subprocess.run(["pkill", "-f", "supervisor.worker_process"], capture_output=True)
    for _ in range(50):
        if not port_in_use(9333):
            break
        time.sleep(0.2)


def fetch_state():
    try:
        with urllib.request.urlopen(STATE_URL, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {"submissions": [], "events": []}


LINE_RE = {
    "confirmed": re.compile(r"\[.\] Set .*Verified '(.*?)' -> '(.*)'"),
    "unconfirmed": re.compile(r"\[\?\] Set but unconfirmed '(.*?)' -> '(.*)'"),
    "failed": re.compile(r"\[~\] Unmatched/Failed '(.*?)' -> '(.*)'"),
}


def parse_tristate(out):
    conf, unc, fail = {}, {}, {}
    for line in out.splitlines():
        m = LINE_RE["confirmed"].search(line)
        if m:
            conf[m.group(1)] = m.group(2)
            continue
        m = LINE_RE["unconfirmed"].search(line)
        if m:
            unc[m.group(1)] = m.group(2)
            conf.pop(m.group(1), None)
            continue
        m = LINE_RE["failed"].search(line)
        if m:
            fail[m.group(1)] = m.group(2)
            conf.pop(m.group(1), None)
            continue
        if "cleared/reverted field:" in line or "reverted/cleared field:" in line:
            m_rev = re.search(r"field: '(.*?)'", line)
            if m_rev:
                conf.pop(m_rev.group(1), None)
                unc[m_rev.group(1)] = ""
    return conf, unc, fail


def run_webpilot(sid, url, run, out, wp, run_id, env=None):
    sc = SCENARIOS[sid]
    exp = sc.get("request", sc.get("expected", {}))
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    steps = 0
    combined = ""

    def sh(cmd):
        nonlocal combined
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
        except subprocess.TimeoutExpired as e:
            combined += (e.stdout or "") + "\n--- stderr ---\n" + (e.stderr or "") + "\n[TIMEOUT after 180s]\n"
            class _T:
                returncode = 124
                stdout = e.stdout or ""
                stderr = e.stderr or ""
            return _T()
        combined += p.stdout + "\n--- stderr ---\n" + p.stderr + "\n"
        return p

    schema = None
    schema_tokens = 0
    insp = sh([wp, "inspect", "--url", url, "--output", os.path.join(out, "schema.json"), "--timeout-minutes", "0"])
    steps += 1
    sp = os.path.join(out, "schema.json")
    if os.path.exists(sp):
        schema = json.load(open(sp, encoding="utf-8"))
        schema_tokens = token_estimate(json.dumps(schema))

    reported = None
    confirmed, unconfirmed, failed = {}, {}, {}
    rc = 0
    if sc.get("extraction"):
        reported = True
        failure_type = "none"
    else:
        data = dict(exp)
        data_path = os.path.join(out, "data.json")
        json.dump(data, open(data_path, "w"), ensure_ascii=False)
        cmd = [wp, "apply", "--url", url, "--data", data_path, "--timeout-minutes", "0"]
        if sc.get("submit"):
            if sid == "S12":
                cmd += ["--press", "Next", "--press", "Submit"]
            else:
                cmd += ["--press", BUTTON.get(sid, "Submit")]
        p = sh(cmd)
        rc = p.returncode
        steps += 1
        confirmed, unconfirmed, failed = parse_tristate(combined)
        reported = (rc == 0)
        if failed:
            failure_type = "selector_miss"
        elif unconfirmed:
            failure_type = "timing"
        else:
            failure_type = "none"

    wall = round(time.time() - t0, 2)
    open(os.path.join(out, "raw_stdout.txt"), "w").write(combined)
    attempt = {
        "tool": "webpilot", "scenario": sid, "run": run, "run_id": run_id,
        "reported_success": reported, "exit_code": rc, "steps": steps,
        "wall_time_s": wall, "schema": schema, "schema_tokens": schema_tokens,
        "tokens_in": token_estimate(combined), "tokens_out": token_estimate(combined) // 2,
        "confirmed_fields": confirmed, "unconfirmed_fields": unconfirmed, "failed_fields": failed,
        "failure_type": failure_type, "raw_output": combined[-6000:],
    }
    open(os.path.join(out, "attempt.json"), "w").write(json.dumps(attempt, ensure_ascii=False, indent=1))
    return attempt


def run_baseline(sid, url, run, out, run_id):
    import run_baseline as rb
    from playwright.sync_api import sync_playwright
    sc = SCENARIOS[sid]
    exp = sc.get("request", sc.get("expected", {}))
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    steps = 0
    reported = None
    failure_type = "none"
    schema = None
    err = None
    verified = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = b.new_page()
            page.set_default_timeout(6000)
            page.goto(url)
            page.wait_for_timeout(300)
            if sc.get("extraction"):
                schema = page.evaluate("""() => {
                    const out={inputs:[],dropdowns:[],choices:[],file_uploads:[]};
                    document.querySelectorAll('input,select,textarea').forEach(e=>{
                        const id=e.id||e.name||'';
                        const label=(document.querySelector(`label[for="${e.id}"]`)||{}).textContent||'';
                        out.inputs.push({id:id,name:e.name,label:label.trim(),
                          type:e.type||e.tagName.toLowerCase(),required:e.required,options:[]});
                    });
                    return out;}""")
                steps += 1
                reported = True
            else:
                _, verified = rb.do_scenario(page, sid, exp)
                steps += len(exp) + 3
                allok = all(v is True for v in verified.values()) and len(verified) >= 1
                reported = bool(allok)
                if not allok:
                    failure_type = "timing"
                if sc.get("submit"):
                    btn = page.locator("button[type=submit]")
                    if btn.count():
                        try:
                            btn.first.click()
                            steps += 1
                            page.wait_for_timeout(400)
                        except Exception:
                            pass
            b.close()
    except Exception as e:
        err = repr(e)
        reported = False
        failure_type = "env"
    attempt = {
        "tool": "baseline", "scenario": sid, "run": run, "run_id": run_id,
        "reported_success": reported, "exit_code": 0 if reported else 1, "steps": steps,
        "wall_time_s": round(time.time() - t0, 2), "schema": schema, "error": err,
        "failure_type": failure_type, "verified": {k: v for k, v in (verified or {}).items()},
        "raw_output": "",
    }
    open(os.path.join(out, "attempt.json"), "w").write(json.dumps(attempt, ensure_ascii=False, indent=1))
    return attempt


def enrich(result, attempt, state):
    """Add verification confusion-matrix fields from the tool tri-state + checker."""
    conf = set(attempt.get("confirmed_fields", {}) or {})
    unc = set(attempt.get("unconfirmed_fields", {}) or {})
    fail = set(attempt.get("failed_fields", {}) or {})
    detail = result.get("field_detail", {}) or {}
    false_confirm = sum(1 for k in conf if not detail.get(k, {}).get("ok", False))
    false_unconfirm = sum(1 for k in unc if detail.get(k, {}).get("ok", False))
    result["tool_reported"] = {"confirmed": sorted(conf), "unconfirmed": sorted(unc), "failed": sorted(fail)}
    result["false_confirm_count"] = false_confirm
    result["false_unconfirm_count"] = false_unconfirm
    result["tool_claimed_all_confirmed"] = bool(conf) and not unc and not fail
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True, choices=["webpilot", "baseline"])
    ap.add_argument("--wp", default=None)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(HERE), "results"))
    ap.add_argument("--host", default="http://127.0.0.1:8900")
    ap.add_argument("--scenarios", default=None)
    ap.add_argument("--label", default=None)
    ap.add_argument("--fresh-daemon", action="store_true",
                    help="reap supervisors before each webpilot scenario (benchmark mitigation)")
    ap.add_argument("--auto-reap", action="store_true",
                    help="reap supervisors after a failed webpilot attempt so one block cannot poison the pass")
    ap.add_argument("--fixed-token", default=None,
                    help="pin WEBPILOT_SUPERVISOR_TOKEN so failed auto-spawns cannot desync the token file")
    args = ap.parse_args()

    sids = args.scenarios.split(",") if args.scenarios else sorted(SCENARIOS.keys())
    label = args.label or args.tool
    env = dict(os.environ)
    if args.fixed_token:
        env["WEBPILOT_SUPERVISOR_TOKEN"] = args.fixed_token
    all_results = []
    auto_reaps = [0]
    for run in range(1, args.runs + 1):
        for sid in sids:
            url = f"{args.host}/s/{sid}"
            out = os.path.join(args.out_dir, "evidence", label, sid, f"run{run}")
            reset_state()
            if args.tool == "webpilot":
                if args.fresh_daemon:
                    reap_supervisors()
                attempt = run_webpilot(sid, url, run, out, args.wp, label, env=env)
                if args.auto_reap:
                    raw = attempt.get("raw_output", "") or ""
                    if (attempt.get("exit_code") not in (0, None)
                            or "Failed to auto-spawn" in raw
                            or "Network error communicating" in raw):
                        auto_reaps[0] += 1
                        print(f"[{label}] AUTO-REAP after {sid} (instability counter={auto_reaps[0]})", flush=True)
                        reap_supervisors()
            else:
                attempt = run_baseline(sid, url, run, out, label)
            state = fetch_state()
            res = checker.score(sid, attempt, state)
            res = enrich(res, attempt, state)
            res["tool_label"] = label
            all_results.append(res)
            json.dump(res, open(os.path.join(out, "score.json"), "w"), ensure_ascii=False, indent=1)
            print(f"[{label}] run{run} {sid}: acc={res.get('field_accuracy')} pass={res.get('form_pass')} "
                  f"rep={res.get('reported_success')} fs={res.get('false_success')} "
                  f"fc={res.get('false_confirm_count')} fu={res.get('false_unconfirm_count')} "
                  f"crit={len(res.get('critical_incidents', []))}", flush=True)
    # aggregate
    agg = os.path.join(args.out_dir, f"results_{label}.json")
    json.dump(all_results, open(agg, "w"), ensure_ascii=False, indent=1)
    rows = []
    for r in all_results:
        rows.append({
            "tool": r.get("tool_label"), "scenario": r.get("scenario"), "run": r.get("run"),
            "mode": r.get("mode"), "field_accuracy": r.get("field_accuracy"),
            "form_pass": r.get("form_pass"), "reported_success": r.get("reported_success"),
            "false_success": r.get("false_success"), "false_confirm_count": r.get("false_confirm_count"),
            "false_unconfirm_count": r.get("false_unconfirm_count"),
            "critical_incidents": json.dumps(r.get("critical_incidents", [])),
            "steps": r.get("steps"), "wall_time_s": r.get("wall_time_s"),
            "schema_tokens": r.get("schema_tokens"), "precision": r.get("precision"),
            "recall": r.get("recall"), "failure_type": r.get("failure_type"),
        })
    csvp = os.path.join(args.out_dir, f"results_{label}.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"[{label}] wrote {agg} and {csvp} ({len(all_results)} rows); auto_reaps={auto_reaps[0]}")


if __name__ == "__main__":
    main()
