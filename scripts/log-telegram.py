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
from datetime import datetime, timezone, timedelta

# Windows cp949 인코딩 에러 방지
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")
HUB_URL = "http://localhost:5600"
TELEGRAM_JSONL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "slack_chatlog", "telegram.jsonl",
)
KST = timezone(timedelta(hours=9))


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
    # PostToolUse 훅: stdin으로 JSON 수신 {"tool_name": ..., "tool_input": {...}, ...}
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    text = tool_input.get("text", "")
    if not text:
        sys.exit(0)

    # JSONL 파일에 아웃바운드 로깅
    _append_to_jsonl({
        "ts": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "outbound",
        "user": "MAX",
        "text": text,
    })

    # 아웃바운드 (MAX → 부서장) 로깅
    log_to_hub("outbound", "boss", text)


def _ensure_header():
    """JSONL 파일이 없거나 빈 경우 헤더 행 작성."""
    if os.path.exists(TELEGRAM_JSONL) and os.path.getsize(TELEGRAM_JSONL) > 0:
        return
    os.makedirs(os.path.dirname(TELEGRAM_JSONL), exist_ok=True)
    with open(TELEGRAM_JSONL, "a", encoding="utf-8") as f:
        header = {"_header": True, "channel": "telegram", "chat_id": "6035183523"}
        f.write(json.dumps(header, ensure_ascii=False) + "\n")


def _append_to_jsonl(record: dict):
    """JSONL 파일에 레코드 1행 append."""
    try:
        _ensure_header()
        with open(TELEGRAM_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
