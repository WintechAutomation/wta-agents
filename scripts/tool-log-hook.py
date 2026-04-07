#!/usr/bin/env python3
"""
PostToolUse 훅 — 도구 사용 내역을 대시보드에 전송.

Claude Code hooks 참조:
  환경변수: CLAUDE_HOOK_TOOL_NAME, CLAUDE_HOOK_AGENT_ID (없으면 stdin JSON 파싱)
  stdin JSON: { "tool_name": "...", ... }

사용법 (settings.json):
  "hooks": {
    "PostToolUse": [
      { "matcher": ".*", "hooks": [{ "type": "command", "command": "python C:/MES/wta-agents/scripts/tool-log-hook.py" }] }
    ]
  }
"""
import sys
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

DASHBOARD_URL = "http://localhost:5555/api/tool-log"
KST = timezone(timedelta(hours=9))

def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

def main():
    # stdin에서 훅 데이터 읽기
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    tool_name = (
        os.environ.get("CLAUDE_HOOK_TOOL_NAME")
        or data.get("tool_name")
        or data.get("toolName")
        or "unknown"
    )
    # 커맨드 인자로 agent_id 전달 가능: python tool-log-hook.py <agent_id>
    agent_id = (
        (sys.argv[1] if len(sys.argv) > 1 else None)
        or os.environ.get("CLAUDE_AGENT_ID")
        or os.environ.get("CLAUDE_HOOK_AGENT_ID")
        or data.get("agent_id")
        or "unknown"
    )

    payload = json.dumps({
        "agent_id": agent_id,
        "tool_name": tool_name,
        "timestamp": now_kst(),
    }).encode()

    req = urllib.request.Request(
        DASHBOARD_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass  # 응답 무시, 빠르게 반환
    except Exception:
        pass  # 대시보드 다운 시 훅 실패가 에이전트 작업을 막으면 안 됨

if __name__ == "__main__":
    main()
