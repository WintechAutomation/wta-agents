"""
PostToolUse hook — CS 슬랙 세션의 도구 사용 추적 + 응답 본문 캡처

동작:
  1) 현재 세션에 cs-slack 임시 파일이 있으면 (= 슬랙 CS 문의 세션)
     → tools_used 배열에 사용된 도구 누적
  2) send_message(to="slack-bot") 감지 시
     → 응답 본문 추출 → 상태 파일에 저장
  3) Read로 이미지 파일 접근 시
     → images 배열에 파일 경로 기록

내부 처리 전용 — 사용자(슬랙)에게 노출되지 않음
"""
import sys
import json
import os
import re
import glob
import tempfile

# 누적 추적할 도구 목록 (내부 처리 관련 도구만)
TRACK_TOOLS = {
    "mcp__agent-channel__send_message",
    "mcp__agent-channel__check_status",
    "Bash",
    "Read",
    "Write",
    "WebFetch",
    "WebSearch",
    "TaskCreate",
    "TaskUpdate",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}


def find_state_file(session_id: str) -> str | None:
    """세션 ID로 임시 상태 파일 찾기"""
    tmp_dir = tempfile.gettempdir()
    exact = os.path.join(tmp_dir, f"cs-slack-{session_id}.json")
    if os.path.exists(exact):
        return exact
    # session_id가 짧게 전달되는 경우 대비: 가장 최근 파일 사용
    candidates = sorted(
        glob.glob(os.path.join(tmp_dir, "cs-slack-*.json")),
        key=os.path.getmtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def extract_slack_response(message: str) -> str:
    """send_message 내용에서 슬랙 응답 본문 추출 (slack:#채널명 접두어 제거)"""
    # "slack:#채널명 응답내용" 형식
    m = re.match(r'slack:#\S+\s*(.*)', message, re.DOTALL)
    if m:
        return m.group(1).strip()
    return message.strip()


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    # CS 슬랙 세션인지 확인
    state_path = find_state_file(session_id)
    if not state_path:
        sys.exit(0)  # 슬랙 CS 세션 아님 — 무시

    state = load_state(state_path)
    if not state:
        sys.exit(0)

    changed = False

    # ── 도구 누적 추적 ──────────────────────────────────────────
    if tool_name in TRACK_TOOLS:
        tools_used: list = state.get("tools_used") or []
        # 연속 중복 제거 (같은 도구가 연달아 쌓이지 않게)
        if not tools_used or tools_used[-1] != tool_name:
            tools_used.append(tool_name)
            state["tools_used"] = tools_used
            changed = True

    # ── 슬랙 응답 본문 캡처 ────────────────────────────────────
    if tool_name == "mcp__agent-channel__send_message":
        to = tool_input.get("to", "")
        message = tool_input.get("message", "")
        if to == "slack-bot" and message:
            response_text = extract_slack_response(message)
            state["agent_response"] = response_text
            changed = True

    # ── 이미지 파일 접근 추적 ──────────────────────────────────
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                images: list = state.get("images") or []
                # 중복 방지
                existing_paths = {img.get("path") for img in images}
                if file_path not in existing_paths:
                    images.append({"path": file_path, "caption": ""})
                    state["images"] = images
                    changed = True

    if changed:
        save_state(state_path, state)


if __name__ == "__main__":
    main()
