"""
Stop hook — 슬랙 메시지 응답 완료 시각 기록 + 처리 내역 md 저장
임시 파일(slack-measure-receive.py가 기록)이 없으면 슬랙 메시지가 아닌 것으로 간주
"""
import sys
import json
import os
import re
import tempfile
import glob
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
LOG_DIR = r"C:\MES\wta-agents\workspaces\cs-agent\logs\slack-response"
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"


def extract_steps_from_transcript(transcript_path: str) -> list[str]:
    """transcript JSONL에서 도구 사용 내역 추출 (처리 절차)"""
    steps = []
    if not transcript_path or not os.path.exists(transcript_path):
        return steps

    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 도구 사용 이벤트
                if entry.get("type") == "tool_use":
                    tool = entry.get("name", "")
                    inp = entry.get("input", {})
                    if tool == "mcp__agent-channel__send_message":
                        to = inp.get("to", "")
                        msg = inp.get("message", "")[:80]
                        steps.append(f"- `send_message → {to}`: {msg}…")
                    elif tool == "Bash":
                        cmd = inp.get("command", "")[:80]
                        steps.append(f"- `Bash`: {cmd}…")
                    elif tool == "Read":
                        fp = inp.get("file_path", "")
                        steps.append(f"- `Read`: {fp}")
                    elif tool in ("WebFetch", "WebSearch"):
                        url = inp.get("url", inp.get("query", ""))[:80]
                        steps.append(f"- `{tool}`: {url}…")
                    elif tool:
                        steps.append(f"- `{tool}`")
    except Exception:
        pass

    # 중복 제거, 최대 20개
    seen = set()
    unique = []
    for s in steps:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:20]


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    transcript_path = data.get("transcript_path", "")

    # 임시 파일 찾기 (session_id 정확히 일치하거나, 가장 최근 것 사용)
    tmp_path = os.path.join(tempfile.gettempdir(), f"cs-slack-{session_id}.json")
    if not os.path.exists(tmp_path):
        # 세션 ID 불일치 대비: 가장 최근 임시 파일 사용
        candidates = sorted(
            glob.glob(os.path.join(tempfile.gettempdir(), "cs-slack-*.json")),
            key=os.path.getmtime, reverse=True
        )
        if not candidates:
            sys.exit(0)
        tmp_path = candidates[0]

    try:
        with open(tmp_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        sys.exit(0)

    now = datetime.now(KST)
    received_at_str = state.get("received_at", "")

    # 소요 시간 계산
    elapsed_sec = None
    if received_at_str:
        try:
            received_at = datetime.fromisoformat(received_at_str)
            elapsed_sec = (now - received_at).total_seconds()
        except Exception:
            pass

    # 처리 절차 추출
    steps = extract_steps_from_transcript(transcript_path)
    if not steps:
        steps = ["(처리 절차 정보 없음)"]

    # md 파일 생성
    os.makedirs(LOG_DIR, exist_ok=True)
    filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".md"
    md_path = os.path.join(LOG_DIR, filename)

    elapsed_str = f"{elapsed_sec:.1f}초" if elapsed_sec is not None else "측정 불가"

    md_content = f"""# CS-Agent 슬랙 응답 처리 내역

## 수신 정보
- **채널**: #{state.get('channel', 'unknown')}
- **수신 시각**: {received_at_str}
- **메시지 요약**: {state.get('message_summary', '(없음)')}

## 처리 절차
{chr(10).join(steps)}

## 응답 완료
- **응답 시각**: {now.strftime('%Y-%m-%d %H:%M:%S KST')}
- **소요 시간**: {elapsed_str}
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 임시 파일 정리
    try:
        os.remove(tmp_path)
    except Exception:
        pass


if __name__ == "__main__":
    main()
