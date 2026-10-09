#!/usr/bin/env python3
"""Drive WebPilot (wp CLI) on a lab scenario as the calling agent.

Two tool commands per run:
  1. wp inspect --url <url> --output schema.json   (understand the page)
  2. wp apply --url <url> --data data.json --press <target> [--auto-inspect]

Records stdout/stderr, parses confirmed/failed lines, estimates tokens from
raw output, and writes attempt.json for the checker.

Usage:
  python3 run_webpilot.py --scenario S01 --url http://127.0.0.1:8910/s/S01 \
      --run 1 --out evidence/webpilot/S01/run1 --wp /path/to/wp
"""
import argparse
import json
import os
import subprocess
import sys
import time

from scenarios import SCENARIOS

SUBMIT_BUTTON = {"S01": "Submit", "S45": "Submit", "S49": "Save", "S19": "إرسال"}


def token_estimate(text):
    # rough heuristic: chars/4
    return int(len(text or "") / 4)


def parse_lines(stdout):
    confirmed, failed = {}, {}
    for line in stdout.splitlines():
        ls = line.strip()
        if "✓] Set" in ls or "Set '" in ls and "' ->" in ls and "✓" in ls:
            try:
                body = ls.split("Set '", 1)[1]
                k, v = body.split("' -> '", 1)
                confirmed[k.strip()] = v.rsplit("'", 1)[0]
            except Exception:
                pass
        if "Unmatched/Failed" in ls:
            try:
                body = ls.split("'", 1)[1]
                k, v = body.split("' -> '", 1)
                failed[k.strip()] = v.rsplit("'", 1)[0]
            except Exception:
                pass
    return confirmed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wp", required=True, help="path to the wp binary")
    ap.add_argument("--skip-apply", action="store_true", help="inspect only (S18)")
    args = ap.parse_args()
    sid = args.scenario
    sc = SCENARIOS[sid]
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    steps = 0
    err = None
    failure_type = "none"
    needed_workaround = "no"
    raw = ""
    stdout_combined = ""

    def run(cmd):
        nonlocal stdout_combined
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        stdout_combined += p.stdout + "\n--- stderr ---\n" + p.stderr + "\n"
        return p

    # Close any stale session, then inspect
    run([args.wp, "service", "restart"]) if False else None
    schema = None
    schema_tokens = 0
    p = run([args.wp, "inspect", "--url", args.url, "--output", os.path.join(args.out, "schema.json"),
             "--timeout-minutes", "0"])
    steps += 1
    if os.path.exists(os.path.join(args.out, "schema.json")):
        schema = json.load(open(os.path.join(args.out, "schema.json"), encoding="utf-8"))
        schema_tokens = token_estimate(json.dumps(schema))

    reported = None
    if sc.get("extraction") or args.skip_apply:
        reported = True
        failure_type = "none"
    else:
        data = {}
        exp = sc.get("request", sc.get("expected", {}))
        # field keys are the ids; also include a label alias for the first field
        for k, v in exp.items():
            data[k] = v
        if sid == "S11":
            data = {"category": exp["category"], "company": exp["company"],
                    "vat": exp["vat"], "employees": exp["employees"]}
        data_path = os.path.join(args.out, "data.json")
        json.dump(data, open(data_path, "w"), ensure_ascii=False)

        btn = SUBMIT_BUTTON.get(sid, "Submit") if sc.get("submit") and not sc.get("extraction") else None
        cmd = [args.wp, "apply", "--url", args.url, "--data", data_path,
               "--timeout-minutes", "0"]
        if btn:
            cmd += ["--press", btn]
        p = run(cmd)
        steps += 1
        confirmed, failed = parse_lines(stdout_combined)

        # WebPilot reports success unless the worker raised: exit 0 == "success".
        reported = bool(p.returncode == 0)
        if failed or (exp and len(confirmed) < len(exp)):
            failure_type = "selector_miss"
            if len(confirmed) == 0 and len(exp) > 0:
                failure_type = "selector_miss" if "[✓]" in stdout_combined else "timing"

    wall = round(time.time() - t0, 2)
    raw = stdout_combined
    open(os.path.join(args.out, "raw_stdout.txt"), "w").write(stdout_combined)
    attempt = {
        "tool": "webpilot", "scenario": sid, "run": args.run,
        "reported_success": reported, "steps": steps, "wall_time_s": wall,
        "schema": schema, "schema_tokens": schema_tokens,
        "tokens_in": token_estimate(raw), "tokens_out": token_estimate(raw) // 2,
        "failure_type": failure_type, "needed_workaround": needed_workaround,
        "error": err, "raw_output": raw[:6000],
    }
    open(os.path.join(args.out, "attempt.json"), "w").write(json.dumps(attempt, ensure_ascii=False, indent=1))
    print(json.dumps({"reported": reported, "steps": steps, "wall": wall,
                      "failure_type": failure_type}, ensure_ascii=False))
    # close worker to free resources
    subprocess.run([args.wp, "service", "restart"], capture_output=True)


if __name__ == "__main__":
    main()