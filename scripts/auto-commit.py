"""
WTA 에이전트 데이터 자동 커밋 + push
APScheduler --once 모드 전용. 1회 실행 후 종료.
대시보드 jobs.json에서 호출됨.
사용법: python auto-commit.py [--repo <경로>]
  --repo 미지정 시 기본 리포(wta-agents)만 커밋
"""
import subprocess
import sys
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KST = timezone(timedelta(hours=9))
DEFAULT_REPO = "C:/MES/wta-agents"


def run_git(repo_dir, *args):
    """git 명령 실행"""
    result = subprocess.run(
        ["git", "-C", repo_dir] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def auto_commit_repo(repo_dir):
    """단일 리포지토리 변경사항 감지 후 커밋+push"""
    run_git(repo_dir, "add", "-A")

    rc, diff, _ = run_git(repo_dir, "diff", "--cached", "--name-only")
    if not diff:
        return False

    timestamp = now_kst()
    rc, out, err = run_git(repo_dir, "commit", "-m", f"자동 저장 — {timestamp}")
    if rc != 0:
        if "nothing to commit" in out or "nothing to commit" in err:
            return False
        print(f"[커밋 실패] {repo_dir}: {err}")
        return False

    print(f"[커밋] {repo_dir} — {timestamp}")

    rc, out, err = run_git(repo_dir, "push")
    if rc == 0:
        print(f"[push] {repo_dir} 완료")
    else:
        print(f"[push 실패] {repo_dir}: {err}")

    return True


if __name__ == "__main__":
    # --repo 인자 파싱
    repo = DEFAULT_REPO
    if "--repo" in sys.argv:
        idx = sys.argv.index("--repo")
        if idx + 1 < len(sys.argv):
            repo = sys.argv[idx + 1]

    try:
        result = auto_commit_repo(repo)
        print(f"[{now_kst()}] {'커밋 완료' if result else '변경 없음'}")
    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)
