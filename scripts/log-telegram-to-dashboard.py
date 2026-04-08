"""텔레그램 메시지 수신 시 대시보드에 자동 로깅하는 hook 스크립트.

Claude Code Notification hook에서 호출됨.
stdin으로 hook payload(JSON)를 받아 텔레그램 메시지만 필터링 후
대시보드 /api/send로 전송.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Windows cp949 인코딩 에러 방지
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

import requests

DASHBOARD_URL = "http://localhost:5555/api/send"
TELEGRAM_JSONL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "slack_chatlog", "telegram.jsonl",
)
KST = timezone(timedelta(hours=9))


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        return

    # UserPromptSubmit: {"prompt": "..."} / Notification: {"content": "..."}
    content = payload.get("prompt", "") or payload.get("content", "")

    # 텔레그램 메시지만 필터링
    if "plugin:telegram:telegram" not in content:
        return

    # <channel source="plugin:telegram:telegram" ...> 태그에서 메시지 추출
    import re
    match = re.search(
        r'<channel\s+source="plugin:telegram:telegram"'
        r'[^>]*user="([^"]*)"'
        r'[^>]*>'
        r'(.*?)'
        r'</channel>',
        content,
        re.DOTALL,
    )
    if not match:
        return

    user = match.group(1)
    message_text = match.group(2).strip()

    if not message_text:
        return

    # JSONL 파일에 인바운드 로깅
    _append_to_jsonl({
        "ts": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "inbound",
        "user": "boss",
        "text": message_text,
    })

    # 대시보드에 로깅
    data = {
        "from": "boss",
        "to": "MAX",
        "content": message_text,
        "type": "telegram",
    }

    try:
        requests.post(DASHBOARD_URL, json=data, timeout=3)
    except Exception:
        pass


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
