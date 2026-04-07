#!/usr/bin/env python3
"""
PostToolUse 훅: MAX가 send_message로 팀원에게 작업 지시 시 task-queue에 자동 등록
- stdin: Claude Code hook JSON (tool_name, tool_input, tool_response, ...)
- 등록 조건: to가 팀원이고 message가 충분히 길면 (단순 확인/질문 제외)
- 실패해도 exit 0 — 훅 실패가 메인 프로세스를 방해하면 안 됨
"""
import json
import sys
import os
import urllib.request
import urllib.error

# Windows cp949 인코딩 에러 방지
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DASHBOARD_URL = "http://localhost:5555"

# 작업 지시 대상이 아닌 수신자 (등록 제외)
SKIP_TARGETS = {"MAX", "slack-bot", "all"}

# 최소 메시지 길이 (단순 알림/확인 메시지 제외)
MIN_MESSAGE_LEN = 30


def extract_task_name(message: str) -> str:
    """메시지에서 작업 이름 추출 — 첫 번째 비어있지 않은 줄, 최대 100자"""
    for line in message.splitlines():
        stripped = line.strip()
        if stripped:
            # 마크다운 헤더 기호 제거
            stripped = stripped.lstrip("#").strip()
            return stripped[:100]
    return message[:100]


def is_task_message(message: str) -> bool:
    """작업 지시성 메시지 여부 판단 — 실제 새 작업 지시만 등록"""
    stripped = message.strip()
    if not stripped or len(stripped) < MIN_MESSAGE_LEN:
        return False
    # 짧은 질문형 메시지 제외 (50자 미만 + 물음표 끝)
    if stripped.endswith("?") and len(stripped) < 60:
        return False
    # 단순 확인/전달/재검증 패턴 제외 (중간 지시는 작업이 아님)
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    skip_prefixes = [
        "[MAX 확인]", "[MAX 전달]", "[MAX 승인]",
        "[MAX 확인 요청]", "[MAX 긴급]",
    ]
    if any(first_line.startswith(p) for p in skip_prefixes):
        return False
    # 재검증/재확인/상태보고 요청은 제외
    skip_keywords = [
        "재검증", "재확인", "상태 보고", "보고해주세요",
        "확인해주세요", "진행 상황", "중간 보고",
        "여전히 미동작", "미동작", "미반영",
    ]
    if any(kw in first_line for kw in skip_keywords):
        return False
    # 단순 확인 패턴 제외
    skip_patterns = ["준비됐어", "상태 알려줘", "어떻게 됐어", "완료됐어", "확인해줘"]
    if len(stripped) < 20 and any(p in stripped for p in skip_patterns):
        return False
    return True


def post_task(to: str, message: str) -> bool:
    task_name = extract_task_name(message)
    data = {
        "agent": to,
        "task": task_name,
        "message": message,
        "status": "pending",
        "priority": "medium",
    }
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8", errors="replace")
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/task-queue",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        sys.stderr.write(f"[task-queue-hook] 등록 실패 ({to}): {e}\n")
        return False


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    # send_message 도구 호출인지 확인
    tool_name = data.get("tool_name", "")
    if "send_message" not in tool_name:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    to = tool_input.get("to", "")
    message = tool_input.get("message", "")

    # 등록 조건 확인
    if not to or to in SKIP_TARGETS:
        sys.exit(0)
    if not is_task_message(message):
        sys.exit(0)

    post_task(to, message)
    sys.exit(0)  # 항상 성공으로 종료


if __name__ == "__main__":
    main()
