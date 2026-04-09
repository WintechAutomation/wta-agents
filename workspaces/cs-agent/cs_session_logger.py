"""
CS 세션 로거 — 대화 그룹핑 지원

같은 웹챗 대화의 연속 메시지를 하나의 session_id로 묶어
cs-sessions.jsonl에 기록한다.

그룹핑 기준:
  - message_history 없음 → 신규 세션 (session_id = webchat-{request_id})
  - message_history 있음 → 첫 번째 user 메시지로 기존 세션 검색 → 동일 session_id 사용
  - 매칭 실패 시 → 신규 세션으로 기록
"""

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

SESSIONS_PATH = os.path.join(os.path.dirname(__file__), "reports", "cs-sessions.jsonl")

KST = timezone(timedelta(hours=9))


def _load_sessions() -> list[dict]:
    sessions = []
    if not os.path.exists(SESSIONS_PATH):
        return sessions
    with open(SESSIONS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                sessions.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return sessions


def _update_session_in_file(session_id: str, new_entry: dict) -> None:
    """기존 session_id의 마지막 turn을 업데이트하거나 새 turn을 append한다."""
    sessions = _load_sessions()

    # 같은 session_id의 기존 마지막 항목에 turns 필드로 누적
    # → 새 turn 추가 방식: session_id가 같으면 append (대시보드가 개수로 카운트)
    with open(SESSIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(new_entry, ensure_ascii=False) + "\n")


def resolve_session_id(request_id: str, message_history: list[dict]) -> str:
    """
    message_history를 분석해 session_id를 결정한다.

    - history 없음 → 새 세션: webchat-{request_id}
    - history 있음 → 첫 번째 user 메시지로 기존 세션 검색
    - 매칭 실패 → 새 세션: webchat-{request_id}
    """
    if not message_history:
        return f"webchat-{request_id}"

    # 첫 번째 user 메시지 추출
    first_user_msg = next(
        (m.get("content", "").strip() for m in message_history if m.get("role") == "user"),
        None,
    )
    if not first_user_msg:
        return f"webchat-{request_id}"

    # cs-sessions.jsonl에서 첫 번째 user 메시지와 query가 일치하는 세션 검색
    sessions = _load_sessions()
    for entry in reversed(sessions):  # 최근 항목부터 검색
        if entry.get("query", "").strip() == first_user_msg:
            sid = entry.get("session_id", "")
            if sid and sid.startswith("webchat-"):
                return sid
            # session_id 없는 레거시 항목은 request_id로 새 session_id 파생
            rid = entry.get("request_id", "")
            if rid:
                return f"webchat-{rid}"

    # 매칭 실패 시 첫 메시지 해시로 session_id 생성 (안정적 식별자)
    hash_id = hashlib.md5(first_user_msg.encode()).hexdigest()[:8]
    return f"webchat-{hash_id}"


def log_session(
    request_id: str,
    query: str,
    response: str,
    message_history: list[dict] | None = None,
    status: str = "completed",
    rag_source: str = "",
    channel: str = "web-chat",
    attachments: list[dict] | None = None,
) -> str:
    """
    CS 세션을 cs-sessions.jsonl에 기록한다.
    message_history를 기반으로 session_id를 자동 결정한다.

    반환: 사용된 session_id
    """
    history = message_history or []
    session_id = resolve_session_id(request_id, history)

    now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry: dict = {
        "request_id": request_id,
        "session_id": session_id,
        "channel": channel,
        "timestamp": now,
        "query": query,
        "response": response,
        "status": status,
        "rag_source": rag_source,
    }
    if attachments:
        entry["attachments"] = attachments

    _update_session_in_file(session_id, entry)
    return session_id


if __name__ == "__main__":
    # 테스트
    import sys

    # 시나리오: 신규 세션
    sid1 = log_session(
        request_id="test001",
        query="파스텍 E-004 에러가 뭐야",
        response="E-004 과부하 이상...",
        message_history=[],
        status="completed",
        rag_source="test",
    )
    print(f"신규 세션: {sid1}")

    # 시나리오: 연속 대화 (history 포함)
    sid2 = log_session(
        request_id="test002",
        query="매뉴얼 보내줘",
        response="PDF 링크...",
        message_history=[
            {"role": "user", "content": "파스텍 E-004 에러가 뭐야"},
            {"role": "assistant", "content": "E-004 과부하 이상..."},
        ],
        status="completed",
        rag_source="test",
    )
    print(f"연속 세션: {sid2}")
    print(f"같은 세션: {sid1 == sid2}")
