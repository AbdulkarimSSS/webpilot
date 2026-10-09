#!/usr/bin/env python3
"""Local evaluation lab server (stdlib only).

Usage:
  python3 server.py --port 8900 [--state-dir ./state] [--faults]

Endpoints:
  GET  /                     index of scenarios
  GET  /s/<SID>              scenario page
  GET  /search?q=&seq=       async typeahead backend (out-of-order capable)
  GET  /csrf                 rotate + return a CSRF token
  GET  /fault?mode=          configure fault injection (500|slow|offline|none)
  POST /submit               record a submission
  POST /log                  record an event
  GET  /state                dump submissions + events (for the checker)
  POST /reset?scenario=SID   clear state for a scenario
"""
import argparse
import json
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from scenarios import SCENARIOS

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
LOCK = threading.Lock()
FAULTS = {"mode": "none", "rate": 0.0}
CSRF = {"token": "seed", "n": 0}


def _path(name):
    return os.path.join(STATE_DIR, name)


def _load(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(name, data):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = _path(name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(name))


class Handler(BaseHTTPRequestHandler):
    server_version = "EvalLab/1.0"

    def log_message(self, *a):
        pass

    def _json(self, code, obj, cors=False):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, code, html):
        body = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            rows = "".join(
                f'<li><a href="/s/{sid}">{sid}: {s["title"]}</a> (T{s["tier"]})</li>'
                for sid, s in sorted(SCENARIOS.items()))
            return self._html(200, f"<h1>Eval Lab</h1><ul>{rows}</ul>")
        if u.path.startswith("/s/"):
            sid = u.path.split("/", 2)[2]
            if sid in SCENARIOS:
                return self._html(200, SCENARIOS[sid]["html"])
            return self._html(404, "unknown scenario")
        if u.path == "/search":
            term = (q.get("q", [""])[0] or "").lower()
            seq = q.get("seq", ["0"])[0]
            universe = ["Springfield", "Shelbyville", "Ogdenville", "North Haverbrook",
                        "Capital City", "Brockway", "Ogdenville East"]
            hits = [c for c in universe if term in c.lower()][:6]
            # simulate out-of-order: later seq may answer first
            delay = random.uniform(0.05, 0.5)
            if seq.isdigit() and int(seq) % 2 == 0:
                delay += 0.6
            time.sleep(delay)
            return self._json(200, {"results": hits, "seq": seq})
        if u.path == "/csrf":
            with LOCK:
                CSRF["n"] += 1
                CSRF["token"] = f"csrf-{random.randint(10**6, 10**7)}-{CSRF['n']}"
                return self._json(200, {"token": CSRF["token"]})
        if u.path == "/fault":
            mode = q.get("mode", ["none"])[0]
            FAULTS["mode"] = mode
            FAULTS["rate"] = float(q.get("rate", ["0.5"])[0])
            return self._json(200, FAULTS)
        if u.path == "/state":
            return self._json(200, {
                "submissions": _load("submissions.json", []),
                "events": _load("events.json", []),
            }, cors=True)
        if u.path == "/health":
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8") if n else ""
        ct = self.headers.get("Content-Type", "")
        if "application/json" in ct:
            try:
                return json.loads(raw)
            except Exception:
                return {}
        # urlencoded
        from urllib.parse import parse_qs as pq
        d = pq(raw)
        return {k: (v[0] if len(v) == 1 else v) for k, v in d.items()}

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if FAULTS["mode"] == "offline":
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if FAULTS["mode"] == "500" and random.random() < max(0.1, FAULTS["rate"]):
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if FAULTS["mode"] == "slow":
            time.sleep(3)

        data = self._body()

        if u.path == "/submit":
            with LOCK:
                subs = _load("submissions.json", [])
                subs.append({"t": time.time(), "data": data})
                _save("submissions.json", subs)
            return self._json(200, {"ok": True})
        if u.path == "/log":
            with LOCK:
                ev = _load("events.json", [])
                if isinstance(data, dict):
                    ev.append({"t": time.time(), **data})
                _save("events.json", ev)
            return self._json(200, {"ok": True})
        if u.path == "/reset":
            with LOCK:
                if q.get("scenario"):
                    _save("submissions.json", [])
                    _save("events.json", [])
                else:
                    _save("submissions.json", [])
                    _save("events.json", [])
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})


def main():
    global STATE_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--state-dir", default=STATE_DIR)
    ap.add_argument("--faults", action="store_true")
    args = ap.parse_args()
    STATE_DIR = args.state_dir
    os.makedirs(STATE_DIR, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[lab] serving on http://127.0.0.1:{args.port} state={STATE_DIR}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
