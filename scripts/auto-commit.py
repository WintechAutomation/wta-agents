"""
WTA 에이전트 데이터 자동 커밋 + push
APScheduler --once 모드 전용. 1회 실행 후 종료.
대시보드 jobs.json에서 */10 * * * * 주기로 호출됨.
"""
import subprocess
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
REPO_DIR = "C:/MES/wta-agents"


def run_git(*args):
    """git 명령 실행"""
    result = subprocess.run(
        ["git", "-C", REPO_DIR] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def auto_commit():
    """변경사항 감지 후 커밋+push (전체 프로젝트 추적)"""
    # 전체 변경사항 add
    run_git("add", "-A")

    # 스테이징된 변경사항 확인
    rc, diff, _ = run_git("diff", "--cached", "--name-only")
    if not diff:
        return False

    # 커밋
    timestamp = now_kst()
    rc, out, err = run_git("commit", "-m", f"자동 저장 — {timestamp}")
    if rc != 0:
        if "nothing to commit" in out or "nothing to commit" in err:
            return False
        print(f"[커밋 실패] {err}")
        return False

    print(f"[커밋] {timestamp}")

    # push
    rc, out, err = run_git("push")
    if rc == 0:
        print(f"[push] 완료")
    else:
        print(f"[push 실패] {err}")

    return True


if __name__ == "__main__":
    try:
        result = auto_commit()
        print(f"[{now_kst()}] {'커밋 완료' if result else '변경 없음'}")
    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)
