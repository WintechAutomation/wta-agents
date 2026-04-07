"""
MES 일일 공지사항 자동 등록 스크립트
매일 07:30 KST — 전날 시스템 업데이트 및 에이전트 변경사항을 MES 공지사항에 게시
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")

KST = timezone(timedelta(hours=9))
MES_API_URL = os.environ.get("MES_API_URL", "http://localhost:8100")
MES_SERVICE_USERNAME = os.environ.get("MES_SERVICE_USERNAME", "")
MES_SERVICE_PASSWORD = os.environ.get("MES_SERVICE_PASSWORD", "")
REPO_DIR = r"C:\MES\wta-agents"


# ── 날짜 범위 계산 ──

def get_yesterday_range():
    """전날 00:00~23:59 KST 범위 반환"""
    now = datetime.now(KST)
    yesterday = now - timedelta(days=1)
    start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
    return start, end, yesterday.strftime("%Y-%m-%d")


# ── MES 로그인 → JWT 토큰 ──

def get_mes_token():
    data = json.dumps({
        "username": MES_SERVICE_USERNAME,
        "password": MES_SERVICE_PASSWORD,
    }).encode()
    req = urllib.request.Request(
        f"{MES_API_URL}/api/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
            return resp.get("data", {}).get("access_token") or resp.get("token")
    except Exception as e:
        print(f"[오류] MES 로그인 실패: {e}")
        return None


# ── git log에서 전날 커밋 추출 ──

def get_git_commits(start: datetime, end: datetime) -> list[str]:
    since = start.strftime("%Y-%m-%d %H:%M:%S")
    until = end.strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(
        ["git", "-C", REPO_DIR, "log",
         f"--after={since}", f"--before={until}",
         "--pretty=format:%s",
         "--no-merges"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    # 자동 저장 커밋 제외, 중복 제거
    filtered = []
    seen = set()
    for l in lines:
        if "자동 저장" in l:
            continue
        if l not in seen:
            seen.add(l)
            filtered.append(l)
    return filtered


# ── 작업큐에서 전날 완료 작업 추출 ──

def get_done_tasks(date_str: str) -> dict[str, list[str]]:
    try:
        req = urllib.request.Request("http://localhost:5555/api/task-queue")
        with urllib.request.urlopen(req, timeout=5) as r:
            tasks = json.loads(r.read())
    except Exception:
        return {}

    by_agent: dict[str, list[str]] = {}
    for t in tasks:
        completed = t.get("completed_at") or t.get("updated_at") or ""
        if t.get("status") == "done" and completed.startswith(date_str):
            agent = t.get("agent", "unknown")
            task_name = t.get("task") or t.get("message", "")[:60]
            by_agent.setdefault(agent, []).append(task_name)
    return by_agent


# ── 공지 본문 생성 ──

def build_content(date_str: str, commits: list[str], done_tasks: dict[str, list[str]]) -> tuple[str, str]:
    """(title, content) 반환"""
    title = f"[일일 업데이트] {date_str} 시스템 변경사항"

    lines = []
    lines.append(f"## {date_str} 시스템 업데이트 요약\n")

    # 시스템 업데이트 (git commits)
    if commits:
        lines.append("### 시스템 변경사항")
        for c in commits[:10]:  # 최대 10건
            lines.append(f"- {c}")
        if len(commits) > 10:
            lines.append(f"- 외 {len(commits) - 10}건")
        lines.append("")
    else:
        lines.append("### 시스템 변경사항\n- 해당 없음\n")

    # 에이전트 완료 작업
    if done_tasks:
        lines.append("### 에이전트 완료 작업")
        for agent, tasks in sorted(done_tasks.items()):
            lines.append(f"\n**{agent}**")
            for task in tasks[:5]:
                lines.append(f"- {task}")
            if len(tasks) > 5:
                lines.append(f"- 외 {len(tasks) - 5}건")
        lines.append("")
    else:
        lines.append("### 에이전트 완료 작업\n- 해당 없음\n")

    lines.append("---")
    lines.append("*본 공지는 admin-agent가 자동 생성했습니다.*")

    content = "\n".join(lines)
    return title, content


# ── MES 공지사항 등록 ──

def post_notice(token: str, title: str, content: str, date_str: str) -> bool:
    summary = f"{date_str} 시스템 업데이트 자동 공지"
    payload = json.dumps({
        "title": title,
        "content": content,
        "summary": summary,
        "category": "system",
        "priority": "normal",
        "status": "published",
        "is_pinned": False,
        "is_popup": False,
    }).encode()
    req = urllib.request.Request(
        f"{MES_API_URL}/api/announcements",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
            notice_id = resp.get("data", {}).get("id") or resp.get("id")
            print(f"[공지] 등록 완료 (id={notice_id})")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[오류] 공지 등록 실패: HTTP {e.code} — {body[:200]}")
        return False
    except Exception as e:
        print(f"[오류] 공지 등록 실패: {e}")
        return False


# ── 메인 ──

def main():
    start, end, date_str = get_yesterday_range()
    print(f"[daily-notice] {date_str} 공지 생성 시작")

    # 환경변수 로드 (대시보드 APScheduler 환경에서는 .env 필요)
    env_path = r"C:\MES\backend\.env"
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)
        global MES_SERVICE_USERNAME, MES_SERVICE_PASSWORD
        MES_SERVICE_USERNAME = os.environ.get("MES_SERVICE_USERNAME", MES_SERVICE_USERNAME)
        MES_SERVICE_PASSWORD = os.environ.get("MES_SERVICE_PASSWORD", MES_SERVICE_PASSWORD)

    # 데이터 수집
    commits = get_git_commits(start, end)
    done_tasks = get_done_tasks(date_str)
    print(f"  git 커밋: {len(commits)}건, 완료 작업: {sum(len(v) for v in done_tasks.values())}건")

    # 공지 내용이 없으면 스킵
    if not commits and not done_tasks:
        print("[daily-notice] 변경사항 없음 — 공지 등록 스킵")
        return

    # 제목/본문 생성
    title, content = build_content(date_str, commits, done_tasks)

    # MES 로그인
    token = get_mes_token()
    if not token:
        print("[daily-notice] MES 토큰 획득 실패 — 종료")
        sys.exit(1)

    # 공지 등록
    ok = post_notice(token, title, content, date_str)
    if ok:
        print(f"[daily-notice] 완료")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
