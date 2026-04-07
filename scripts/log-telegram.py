#!/usr/bin/env python3
"""
텔레그램 메시지 대시보드 로깅 스크립트

1. PostToolUse 훅: mcp__plugin_telegram_telegram__reply 이후 호출
   - CLAUDE_TOOL_INPUT = {"text": "...", "chat_id": "..."}
   - 대시보드에 MAX → 부서장(텔레그램) 로깅

2. 인바운드 채널 notification이 도착하면 mcp-wta-hub.ts /telegram-log 엔드포인트로 전달
   - mcp-wta-hub.ts가 대시보드 /api/send를 호출
"""
import os
import sys
import json
import urllib.request
import urllib.error

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")
HUB_URL = "http://localhost:5600"


def log_to_hub(direction: str, from_label: str, content: str) -> None:
    """mcp-wta-hub.ts /telegram-log 엔드포인트에 로깅 요청."""
    payload = json.dumps({
        "from": from_label,
        "content": content,
        "direction": direction,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{HUB_URL}/telegram-log",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except (urllib.error.URLError, OSError):
        # 허브 오류 시 대시보드에 직접 로깅
        log_to_dashboard_direct(direction, from_label, content)


def log_to_dashboard_direct(direction: str, from_label: str, content: str) -> None:
    """대시보드 /api/send에 직접 로깅 (허브 오프라인 시 폴백)."""
    if direction == "inbound":
        from_field, to_field = from_label, "MAX"
    else:
        from_field, to_field = "MAX", from_label  # from_label = "boss"

    payload = json.dumps({
        "from": from_field,
        "to": to_field,
        "content": content,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except (urllib.error.URLError, OSError):
        pass


def main():
    tool_input_raw = os.environ.get("CLAUDE_TOOL_INPUT", "")
    if not tool_input_raw:
        sys.exit(0)

    try:
        tool_input = json.loads(tool_input_raw)
    except json.JSONDecodeError:
        sys.exit(0)

    # reply 도구: text = MAX가 보낸 메시지
    text = tool_input.get("text", "")
    if not text:
        sys.exit(0)

    # 아웃바운드 (MAX → 부서장) 로깅
    log_to_hub("outbound", "boss", text)


if __name__ == "__main__":
    main()
