"""
UserPromptSubmit hook — 슬랙 메시지 수신 시각 기록
슬랙 메시지인 경우 세션 ID 기반 임시 파일에 시작 시각과 메타데이터 저장
"""
import sys
import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def is_slack_message(prompt: str) -> bool:
    """슬랙 채널에서 온 메시지인지 판별"""
    return 'from="slack-bot"' in prompt or "from='slack-bot'" in prompt


def extract_slack_meta(prompt: str) -> dict:
    """슬랙 메시지에서 채널명, 내용 추출"""
    # channel 태그 내부 텍스트 추출
    tag_match = re.search(r'<channel[^>]*>(.*?)</channel>', prompt, re.DOTALL)
    inner = tag_match.group(1).strip() if tag_match else prompt.strip()

    # 채널명: slack:#채널명
    channel_match = re.search(r'slack:#(\S+)', inner)
    channel = channel_match.group(1) if channel_match else "unknown"

    # slack:#채널명 제거 후 나머지가 메시지 본문
    body = re.sub(r'slack:#\S+\s*', '', inner).strip()

    # 200자 초과 시 말줄임
    if len(body) > 200:
        body = body[:200] + "..."

    return {
        "channel": channel,
        "message_summary": body or "(내용 없음)",
    }


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = data.get("prompt", "")
    session_id = data.get("session_id", "unknown")

    if not is_slack_message(prompt):
        sys.exit(0)

    now = datetime.now(KST)
    meta = extract_slack_meta(prompt)

    state = {
        "session_id": session_id,
        "received_at": now.isoformat(),
        "channel": meta["channel"],
        "message_summary": meta["message_summary"],
        "steps": [],
    }

    # 세션 ID 기반 임시 파일에 저장
    tmp_path = os.path.join(tempfile.gettempdir(), f"cs-slack-{session_id}.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
