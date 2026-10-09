#!/usr/bin/env python3
"""Persistent Playwright MCP driver."""
import argparse, json, os, subprocess, time

from scenarios import SCENARIOS

BIN = "/home/abdulkarim/webpilot_eval/mcp/node_modules/@playwright/mcp/cli.js"

class MCP:
    def __init__(self):
        self.p = subprocess.Popen(
            ["node", BIN, "--browser", "chromium", "--headless", "--no-sandbox"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd="/home/abdulkarim/webpilot_eval/mcp",
        )
        self._id = 0

    def call(self, method, params):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        try:
            self.p.stdin.write(json.dumps(payload) + "\n")
            self.p.stdin.flush()
        except Exception as e:
            return {"error": {"message": str(e)}}
        while True:
            try:
                line = self.p.stdout.readline()
            except Exception:
                break
            if not line:
                break
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("id") == self._id:
                return obj
        return {"error": {"message": "no response"}}

    def close(self):
        try:
            self.call("tools/call", {"name": "browser_close", "arguments": {}})
        except Exception:
            pass
        try:
            self.p.kill()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sid, sc = args.scenario, SCENARIOS[args.scenario]
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    m = MCP()
    steps, reported, failure_type, err, raw = 0, False, "none", None, ""
    try:
        r = m.call("tools/call", {"name": "browser_navigate", "arguments": {"url": args.url}})
        steps += 1; raw += json.dumps(r, ensure_ascii=False) + "\n"
        if sc.get("extraction"):
            r = m.call("tools/call", {"name": "browser_snapshot", "arguments": {}})
            steps += 1; raw += json.dumps(r, ensure_ascii=False) + "\n"
            reported = True
        else:
            exp = sc.get("request", sc.get("expected", {}))
            fields = []
            for k, v in exp.items():
                ftype = "textbox"; target = f"#{k}"; value = str(v)
                if sid == "S02":
                    ftype = "combobox"
                    if k == "langs": target = "#langs"; value = "English,Japanese"
                elif sid == "S06":
                    if k == "newsletter": ftype = "checkbox"; value = "true"
                    elif k == "interests": target = "input[name='interests'][value='AI']"; ftype = "checkbox"; value = "true"
                fields.append({"element": k, "target": target, "name": k, "type": ftype, "value": value})
            r = m.call("tools/call", {"name": "browser_fill_form", "arguments": {"fields": fields}})
            steps += 1; raw += json.dumps(r, ensure_ascii=False) + "\n"
            if sc.get("submit"):
                r = m.call("tools/call", {"name": "browser_click", "arguments": {
                    "element": "Submit",
                    "target": "#mainform button[type=submit], button[type=submit], #submit-btn, input[type=submit]"
                }})
                steps += 1; raw += json.dumps(r, ensure_ascii=False) + "\n"
            reported = True
    except Exception as e:
        err = repr(e); failure_type = "env"
    finally:
        m.close()
    wall = round(time.time() - t0, 2)
    attempt = {
        "tool": "playwright-mcp", "scenario": sid, "run": args.run,
        "reported_success": reported, "steps": steps, "wall_time_s": wall,
        "schema": None, "schema_tokens": 0,
        "tokens_in": len(raw)//4, "tokens_out": 0,
        "failure_type": failure_type, "needed_workaround": "no",
        "error": err, "raw_output": raw[:6000],
    }
    open(os.path.join(args.out, "attempt.json"), "w").write(json.dumps(attempt, ensure_ascii=False, indent=1))
    print(json.dumps({"reported": reported, "steps": steps, "wall": wall}))

if __name__ == "__main__":
    main()
