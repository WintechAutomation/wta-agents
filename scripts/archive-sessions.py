"""
일일 세션 JSONL 아카이브
하루 한 번 (자정 이후) 수동 또는 Task Scheduler로 실행
오늘 날짜 세션 파일을 sessions/에 복사 후 git 커밋
"""
import os
import sys
import shutil
import subprocess
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
CLAUDE_PROJECTS = r"C:/Users/Administrator/.claude/projects"
SESSIONS_DIR = r"C:/MES/wta-agents/sessions"
REPO_DIR = r"C:/MES/wta-agents"
PROJECT_PREFIXES = ["C--MES-wta-agents"]


def today_kst():
    return datetime.now(KST).date()


def run_git(*args):
    result = subprocess.run(
        ["git", "-C", REPO_DIR] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def archive():
    today = today_kst()
    copied = 0

    os.makedirs(SESSIONS_DIR, exist_ok=True)

    for project_dir in os.listdir(CLAUDE_PROJECTS):
        if not any(project_dir.startswith(p) for p in PROJECT_PREFIXES):
            continue

        src_dir = os.path.join(CLAUDE_PROJECTS, project_dir)
        dst_dir = os.path.join(SESSIONS_DIR, project_dir)
        os.makedirs(dst_dir, exist_ok=True)

        for fname in os.listdir(src_dir):
            if not fname.endswith(".jsonl"):
                continue

            src_path = os.path.join(src_dir, fname)
            dst_path = os.path.join(dst_dir, fname)

            mtime = datetime.fromtimestamp(os.path.getmtime(src_path), tz=KST).date()
            if mtime != today:
                continue

            shutil.copy2(src_path, dst_path)
            copied += 1

    print(f"[archive] {today} 세션 {copied}개 복사 완료")

    if copied == 0:
        print("[archive] 복사된 파일 없음 — 종료")
        return

    # git add sessions/ (force — .gitignore 예외 처리)
    rc, out, err = run_git("add", "-f", "sessions/")
    if rc != 0:
        print(f"[git add 실패] {err}")
        return

    rc, diff, _ = run_git("diff", "--cached", "--name-only")
    if not diff:
        print("[archive] 변경 없음 — 커밋 스킵")
        return

    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    rc, out, err = run_git("commit", "-m", f"세션 아카이브 — {today}")
    if rc != 0:
        print(f"[커밋 실패] {err}")
        return

    print(f"[커밋] 세션 아카이브 {today}")

    rc, out, err = run_git("push")
    if rc == 0:
        print("[push] 완료")
    else:
        print(f"[push 실패] {err}")


if __name__ == "__main__":
    archive()
