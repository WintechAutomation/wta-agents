"""
팀원 응답 확인 — 대시보드에서 특정 에이전트의 응답 조회
사용법:
  python check-response.py <agent_id>          — 최신 응답 확인
  python check-response.py <agent_id> --save   — 응답을 last-response.txt에 저장
  python check-response.py --all               — 전체 팀원 미응답 현황
"""
import sys
import io
import os
import json
import time
import urllib.request

# Windows stdout UTF-8 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:5555/api"
WORKSPACES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workspaces")


def recv_messages(agent_id):
    """MAX 수신함에서 특정 에이전트가 보낸 메시지 필터링"""
    try:
        resp = urllib.request.urlopen(f"{BASE}/recv/MAX", timeout=10)
        data = json.loads(resp.read())
    except Exception as e:
        print(f"수신 오류: {e}")
        return []

    messages = data.get("messages", [])
    # 해당 에이전트가 보낸 메시지만 필터
    filtered = [m for m in messages if m.get("from") == agent_id]
    # 기동/준비 메시지 제외
    filtered = [
        m for m in filtered
        if "기동 완료" not in m.get("content", "")
        and "준비 완료" not in m.get("content", "")
    ]
    return filtered


def save_response(agent_id, content):
    """응답을 last-response.txt에 저장"""
    workspace = os.path.join(WORKSPACES, agent_id)
    os.makedirs(workspace, exist_ok=True)

    path = os.path.join(workspace, "last-response.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # last-task.json 상태 업데이트
    task_path = os.path.join(workspace, "last-task.json")
    if os.path.exists(task_path):
        with open(task_path, "r", encoding="utf-8") as f:
            task = json.load(f)
        task["status"] = "completed"
        task["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)

    return path


def check_all():
    """전체 팀원 위임 현황 확인"""
    if not os.path.isdir(WORKSPACES):
        print("위임 기록 없음")
        return

    for name in sorted(os.listdir(WORKSPACES)):
        task_path = os.path.join(WORKSPACES, name, "last-task.json")
        if not os.path.isfile(task_path):
            continue
        with open(task_path, "r", encoding="utf-8") as f:
            task = json.load(f)
        status = task.get("status", "unknown")
        sent = task.get("sent_at", "?")
        msg_preview = task.get("message", "")[:40]
        print(f"  {name}: [{status}] {sent} — {msg_preview}")


def check_response(agent_id, do_save=False):
    """특정 에이전트 응답 확인"""
    messages = recv_messages(agent_id)

    if not messages:
        # 위임 기록 확인
        task_path = os.path.join(WORKSPACES, agent_id, "last-task.json")
        if os.path.isfile(task_path):
            with open(task_path, "r", encoding="utf-8") as f:
                task = json.load(f)
            print(f"{agent_id}: 응답 대기 중 (위임: {task.get('sent_at', '?')})")
        else:
            print(f"{agent_id}: 응답 없음 (위임 기록도 없음)")
        return

    # 최신 응답 출력
    latest = messages[-1]
    content = latest.get("content", "")
    ts = latest.get("time", "")

    print(f"[{ts}] {agent_id} 응답:")
    print(content)

    if do_save:
        path = save_response(agent_id, content)
        print(f"\n저장 완료 → {path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python check-response.py <agent_id>        — 응답 확인")
        print("  python check-response.py <agent_id> --save — 응답 확인 + 파일 저장")
        print("  python check-response.py --all             — 전체 현황")
        sys.exit(1)

    if sys.argv[1] == "--all":
        check_all()
    else:
        agent_id = sys.argv[1]
        do_save = "--save" in sys.argv
        check_response(agent_id, do_save)
