"""
APScheduler daily report trigger.
Sends daily report request to MAX via MCP agent channel.
"""
import sys
import json
import urllib.request
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")

KST = timezone(timedelta(hours=9))

# slack-bot excluded from report targets
REPORT_AGENTS = [
    "db-manager", "cs-agent", "crafter", "dev-agent", "admin-agent",
    "nc-manager", "qa-agent", "issue-manager", "sales-agent",
    "schedule-agent", "docs-agent", "design-agent", "control-agent",
    "purchase-agent",
]


def main():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    message = (
        f"[daily-report-trigger] {today}\n"
        f"daily report collection requested.\n"
        f"target: reports/daily-reports/{today}/{{agent}}.md\n"
        f"agents: {', '.join(REPORT_AGENTS)}"
    )

    payload = json.dumps({
        "from": "dashboard-scheduler",
        "to": "MAX",
        "content": message,
        "type": "chat",
    }).encode()

    try:
        req = urllib.request.Request(
            "http://localhost:5600/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[{today}] trigger sent to MAX (HTTP {resp.status})")
    except Exception as e:
        print(f"[{today}] trigger failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
