#!/usr/bin/env python3
"""BMQ MON — a terminal-style operations console for a local BlazingMQ broker.

Zero dependencies (stdlib only).  Serves a single page that looks like a trading-floor
terminal screen and a small JSON API that runs the real routing-conformance probe
(tools/oncall/priority-check.sh) against the broker on tcp://localhost:30114.

    tools/oncall/console/server.py            # http://localhost:8787
    tools/oncall/console/server.py --port 9000 --interval 0   # no auto-probe
"""
import argparse
import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PROBE = os.path.join(ROOT, "tools", "oncall", "priority-check.sh")
INCIDENT_FILE = os.environ.get("BMQ_INCIDENT_FILE", os.path.join(HERE, "incident.json"))

QUEUES = [  # display names only; every probe runs on its own in-memory priority queue
    "bmq.prod.orders.us",
    "bmq.prod.orders.eu",
    "bmq.prod.orders.apac",
    "bmq.prod.settlement",
]

STATE = {
    "broker": {"up": False, "checked_at": None},
    "last": None,          # last probe result
    "history": [],         # most recent first, max 40
    "running": False,
    "started_at": time.time(),
}
LOCK = threading.Lock()


def git(*args):
    try:
        return subprocess.check_output(["git", "-C", ROOT, *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def broker_up():
    import socket
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 30114))
        return True
    except OSError:
        return False
    finally:
        s.close()


def run_probe(queue=None):
    with LOCK:
        if STATE["running"]:
            return STATE["last"]
        STATE["running"] = True
    queue = queue or QUEUES[int(time.time()) % len(QUEUES)]
    env = dict(os.environ, URI="bmq://bmq.test.mem.priority/console-%d" % int(time.time() * 1000),
               OUT="/tmp/bmq-console-probe")
    t0 = time.time()
    try:
        p = subprocess.run([PROBE], env=env, capture_output=True, text=True, timeout=60)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        out = "probe timed out"
    m = re.search(r"posted=(\d+)\s+primary\(priority 10\) received=(\d+)\s+standby\(priority 1\) received=(\d+)", out)
    posted, primary, standby = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)
    result = {
        "ts": time.time(),
        "queue": queue,
        "posted": posted,
        "primary": primary,
        "standby": standby,
        "ok": bool(m) and standby == 0 and primary == posted,
        "line": m.group(0) if m else (out.strip().splitlines() or ["probe produced no output"])[-1],
        "duration_s": round(time.time() - t0, 1),
        "broker_commit": git("rev-parse", "--short", "HEAD"),
        "broker_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
    }
    with LOCK:
        STATE["last"] = result
        STATE["history"].insert(0, result)
        del STATE["history"][40:]
        STATE["running"] = False
    return result


def incident():
    try:
        with open(INCIDENT_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def snapshot():
    STATE["broker"] = {"up": broker_up(), "checked_at": time.time()}
    with LOCK:
        hist = list(STATE["history"])
        last = STATE["last"]
        running = STATE["running"]
    per_queue = {}
    for q in QUEUES:
        per_queue[q] = next((h for h in hist if h["queue"] == q), None)
    return {
        "now": time.time(),
        "broker": STATE["broker"],
        "head": {"commit": git("rev-parse", "--short", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                 "subject": git("log", "-1", "--format=%s")},
        "queues": QUEUES,
        "per_queue": per_queue,
        "last": last,
        "running": running,
        "history": hist[:12],
        "incident": incident(),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            return self._json(snapshot())
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/api/probe"):
            q = None
            m = re.search(r"queue=([\w.\-]+)", self.path)
            if m:
                q = m.group(1)
            return self._json(run_probe(q))
        self.send_error(404)


def auto_probe(interval):
    while interval > 0:
        if broker_up():
            run_probe()
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--interval", type=int, default=45, help="seconds between automatic probes (0 = manual only)")
    a = ap.parse_args()
    threading.Thread(target=auto_probe, args=(a.interval,), daemon=True).start()
    print("BMQ MON console on http://localhost:%d  (broker tcp://localhost:30114)" % a.port, flush=True)
    ThreadingHTTPServer(("0.0.0.0", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
