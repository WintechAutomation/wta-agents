#!/usr/bin/env python3
"""
텔레그램 인바운드 메시지 대시보드 로깅 (UserPromptSubmit 훅)

CLAUDE_USER_PROMPT 환경변수에서 <channel source="plugin:telegram:telegram"> 태그를 감지하면
대시보드에 boss → MAX 메시지로 로깅한다.
"""
import os
import sys
import re
import json
import urllib.request
import urllib.error

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")


def main():
    prompt = os.environ.get("CLAUDE_USER_PROMPT", "")
    if not prompt:
        sys.exit(0)

    # <channel source="plugin:telegram:telegram" ...>내용</channel> 패턴 매칭
    pattern = r'<channel\s+source="plugin:telegram:telegram"[^>]*>(.*?)</channel>'
    matches = re.findall(pattern, prompt, re.DOTALL)
    if not matches:
        sys.exit(0)

    for text in matches:
        text = text.strip()
        if not text:
            continue

        payload = json.dumps({
            "from": "boss",
            "to": "MAX",
            "content": text,
            "type": "telegram",
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


if __name__ == "__main__":
    main()
