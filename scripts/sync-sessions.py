"""
Claude Code 세션 JSONL → wta-agents/sessions/ 동기화
auto-commit.py에서 git add 전에 호출됨
당일 수정된 파일만 복사 (히스토리 비대 방지)
"""
import os
import shutil
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
CLAUDE_PROJECTS = r"C:/Users/Administrator/.claude/projects"
SESSIONS_DIR = r"C:/MES/wta-agents/sessions"
# 오늘 날짜 기준 수정된 파일만 동기화
PROJECT_PREFIXES = [
    "C--MES-wta-agents",
]


def today_kst():
    return datetime.now(KST).date()


def sync_sessions():
    today = today_kst()
    copied = 0
    skipped = 0

    os.makedirs(SESSIONS_DIR, exist_ok=True)

    for project_dir in os.listdir(CLAUDE_PROJECTS):
        # wta-agents 관련 프로젝트만 처리
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

            # 수정 시간 확인 — 오늘 날짜인 것만
            mtime = datetime.fromtimestamp(os.path.getmtime(src_path), tz=KST).date()
            if mtime != today:
                skipped += 1
                continue

            shutil.copy2(src_path, dst_path)
            copied += 1

    print(f"[sync-sessions] 복사: {copied}개, 건너뜀(구일자): {skipped}개")
    return copied


if __name__ == "__main__":
    sync_sessions()
