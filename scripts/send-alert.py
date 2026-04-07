#!/usr/bin/env python3
"""
MCP 채널을 통해 지정 에이전트에게 알림 메시지 전송.
사용법: python send-alert.py <to> <message>
"""
import sys
import json
import urllib.request

if len(sys.argv) < 3:
    print("Usage: send-alert.py <to> <message>")
    sys.exit(1)

to = sys.argv[1]
message = sys.argv[2]

# MCP agent-channel: MAX 포트(5600)에 직접 HTTP POST
# 형식: { from, to, content }
AGENT_PORTS = {
    "MAX": 5600,
    "db-manager": 5601,
    "cs-agent": 5602,
    "nc-manager": 5603,
    "dev-agent": 5604,
    "crafter": 5605,
    "issue-manager": 5606,
    "qa-agent": 5607,
    "sales-agent": 5608,
    "admin-agent": 5609,
    "slack-bot": 5610,
}
port = AGENT_PORTS.get(to, 5600)
MCP_URL = f"http://localhost:{port}/message"

payload = json.dumps({
    "from": "admin-agent",
    "to": to,
    "content": message
}).encode()
req = urllib.request.Request(
    MCP_URL,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(f"전송 완료 → {to} (HTTP {resp.status})")
except Exception as e:
    print(f"전송 실패: {e}", file=sys.stderr)
    sys.exit(1)
