"""
APScheduler one-shot health check.
Runs system health check once and sends results to MAX via dashboard API.
"""
import os
import sys
import json
import socket
import subprocess
import urllib.request
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")

KST = timezone(timedelta(hours=9))
DASHBOARD_URL = "http://localhost:5555"
REPO = "C:/MES/wta-agents"


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def send_to_max(message: str):
    payload = json.dumps({
        "from": "admin-agent",
        "to": "MAX",
        "content": message,
        "type": "chat",
    }).encode()
    req = urllib.request.Request(
        f"{DASHBOARD_URL}/api/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[send fail] {e}")
        return False


def check_http(name, url, timeout=5):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)[:60]


def check_port(host, port):
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False


def check_process_pid(pid_file):
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True
        )
        alive = str(pid) in result.stdout
        return alive, pid
    except Exception:
        return False, -1


def check_docker_exited():
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "status=exited",
             "--filter", "status=dead", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        return [n.strip() for n in result.stdout.splitlines() if n.strip()]
    except Exception:
        return []


def run_health_check():
    ts = now_kst()
    issues = []
    ok_items = []

    # MES backend
    ok, detail = check_http("MES backend", "http://localhost:8100/health")
    (ok_items if ok else issues).append(
        f"MES backend(8100): {'OK' if ok else 'FAIL - ' + detail}")

    # MES frontend
    ok, detail = check_http("MES frontend", "http://localhost:3100/")
    (ok_items if ok else issues).append(
        f"MES frontend(3100): {'OK' if ok else 'FAIL - ' + detail}")

    # Dashboard
    ok, detail = check_http("Dashboard", "http://localhost:5555/api/status")
    (ok_items if ok else issues).append(
        f"Dashboard(5555): {'OK' if ok else 'FAIL - ' + detail}")

    # Slack bot PID
    pid_file = os.path.join(REPO, "logs", "slack-bot.pid")
    alive, pid = check_process_pid(pid_file)
    (ok_items if alive else issues).append(
        f"Slack bot: {'OK(PID ' + str(pid) + ')' if alive else 'DOWN'}")

    # Docker
    exited = check_docker_exited()
    if exited:
        issues.append(f"Docker exited: {', '.join(exited)}")
    else:
        ok_items.append("Docker: all OK")

    # Ollama
    ok, detail = check_http("Ollama", "http://182.224.6.147:11434/", timeout=5)
    (ok_items if ok else issues).append(
        f"Ollama(182.224.6.147): {'OK' if ok else 'FAIL - ' + detail}")

    if issues:
        body = f"[health-check {ts}] issues found:\n"
        for i in issues:
            body += f"- {i}\n"
        body += f"\nOK {len(ok_items)} | WARN {len(issues)}"
    else:
        body = f"[health-check {ts}] all OK ({len(ok_items)} items)"

    return body, bool(issues)


def main():
    report, has_issues = run_health_check()
    print(report)
    if has_issues:
        send_to_max(report)
        print("[alert sent to MAX]")


if __name__ == "__main__":
    main()
