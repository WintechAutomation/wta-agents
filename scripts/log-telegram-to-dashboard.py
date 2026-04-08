"""텔레그램 메시지 수신 시 대시보드에 자동 로깅하는 hook 스크립트.

Claude Code Notification hook에서 호출됨.
stdin으로 hook payload(JSON)를 받아 텔레그램 메시지만 필터링 후
대시보드 /api/send로 전송.
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta

# Windows cp949 인코딩 에러 방지
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

import requests

DASHBOARD_URL = "http://localhost:5555/api/send"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEGRAM_JSONL = os.path.join(BASE_DIR, "slack_chatlog", "telegram.jsonl")
TELEGRAM_FILES = os.path.join(BASE_DIR, "slack_chatlog", "telegram_files")
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
    match = re.search(
        r'<channel\s+source="plugin:telegram:telegram"'
        r'(?P<attrs>[^>]*)>'
        r'(?P<body>.*?)'
        r'</channel>',
        content,
        re.DOTALL,
    )
    if not match:
        return

    attrs = match.group("attrs")
    message_text = match.group("body").strip()

    # 모든 파일 경로 속성 추출 (image_path, file_path, document_path, video_path 등)
    file_attrs = re.findall(r'(\w+_path)="([^"]*)"', attrs)

    # 첨부 파일 복사
    saved_files = []
    if file_attrs:
        os.makedirs(TELEGRAM_FILES, exist_ok=True)
        ts_prefix = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        for i, (attr_name, src_path) in enumerate(file_attrs):
            if not os.path.exists(src_path):
                continue
            ext = os.path.splitext(src_path)[1] or ".bin"
            suffix = f"_{i}" if i > 0 else ""
            dest = os.path.join(TELEGRAM_FILES, f"{ts_prefix}{suffix}{ext}")
            try:
                shutil.copy2(src_path, dest)
                saved_files.append({"type": attr_name.replace("_path", ""), "path": dest})
            except Exception:
                pass

    if not message_text and not saved_files:
        return

    # JSONL 파일에 인바운드 로깅
    record = {
        "ts": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "inbound",
        "user": "boss",
        "text": message_text,
    }
    if saved_files:
        record["files"] = saved_files
    _append_to_jsonl(record)

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
