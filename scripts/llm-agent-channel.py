#!/usr/bin/env python3
"""
LLM Agent Channel — lightweight P2P agent channel for external LLM server.
Runs on port 5620, receives messages from internal agents (via direct HTTP),
sends messages to internal agents via Cloudflare relay proxy.

Usage: python3 llm-agent-channel.py
"""

import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

AGENT_ID = "llm-agent"
PORT = 5620
KST = timezone(timedelta(hours=9))

# Cloudflare relay for sending to internal agents
RELAY_BASE_URL = os.environ.get("RELAY_BASE_URL", "https://agent.mes-wta.com/api/agent-relay")
RELAY_TOKEN = os.environ.get("AGENT_RELAY_TOKEN", "wta-relay-2026")

# message inbox (thread-safe via list append)
inbox: list[dict] = []
inbox_lock = threading.Lock()


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[llm-channel] {ts} {msg}", file=sys.stderr, flush=True)


def send_via_relay(target: str, message: str) -> str:
    """Send message to internal agent via Cloudflare relay."""
    url = f"{RELAY_BASE_URL}/{target}"
    body = json.dumps({
        "from": AGENT_ID,
        "to": target,
        "content": message,
        "ts": datetime.now(KST).isoformat(),
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Relay-Token": RELAY_TOKEN,
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = resp.read().decode("utf-8")
        log(f"relay -> {target}: OK ({len(message)}chars)")
        return f"sent to {target} via relay"
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        log(f"relay -> {target}: HTTP {e.code} {err[:100]}")
        return f"relay error: {e.code}"
    except Exception as e:
        log(f"relay -> {target}: {e}")
        return f"relay error: {e}"


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP handler for agent-channel P2P protocol."""
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # suppress default access log
        pass

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/ping":
            self._json_response(200, {
                "agent": AGENT_ID,
                "status": "online",
                "ts": now_kst(),
            })
            return

        if self.path == "/inbox":
            with inbox_lock:
                msgs = list(inbox)
                inbox.clear()
            self._json_response(200, {"messages": msgs})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/message":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"invalid json"}')
                return

            sender = data.get("from", "unknown")
            content = data.get("content", "")
            log(f"recv <- {sender}: {content[:80]}")

            with inbox_lock:
                inbox.append({
                    "from": sender,
                    "content": content,
                    "ts": data.get("ts", now_kst()),
                })

            self._json_response(200, {"ok": True})
            return

        if self.path == "/send":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "invalid json"})
                return

            target = data.get("to", "")
            message = data.get("message", "")
            if not target or not message:
                self._json_response(400, {"error": "to and message required"})
                return

            result = send_via_relay(target, message)
            self._json_response(200, {"ok": True, "result": result})
            return

        self.send_response(404)
        self.end_headers()


def main():
    server = HTTPServer(("0.0.0.0", PORT), AgentHandler)
    log(f"LLM Agent Channel started on port {PORT}")
    log(f"Relay: {RELAY_BASE_URL}")

    # Start notification to MAX via relay
    try:
        send_via_relay("MAX", f"[{AGENT_ID}] agent-channel 시작됨 (port {PORT})")
    except Exception as e:
        log(f"startup notification failed: {e}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
