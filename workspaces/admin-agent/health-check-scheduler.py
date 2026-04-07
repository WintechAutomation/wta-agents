"""
admin-agent 정기 상태점검 스케줄러
1시간마다 전체 시스템 헬스체크 실행 → 대시보드 API → MAX 보고
"""
import subprocess
import time
import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
INTERVAL = 3600  # 1시간
DASHBOARD_URL = "http://localhost:5555"
PY = r"C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
REPO = r"C:/MES/wta-agents"


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def send_to_max(message: str):
    """대시보드 /api/send를 통해 MAX에게 메시지 전송"""
    payload = json.dumps({
        "from": "admin-agent",
        "to": "MAX",
        "content": message,
        "type": "chat",
    }).encode()
    req = urllib.request.Request(
        f"{DASHBOARD_URL}/api/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[전송 실패] {e}")
        return False


def check_http(name: str, url: str, timeout: int = 5) -> tuple[bool, str]:
    """HTTP 엔드포인트 응답 확인"""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)[:60]


def check_port(host: str, port: int) -> bool:
    """포트 연결 가능 여부 확인"""
    import socket
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False


def check_process_pid(pid_file: str) -> tuple[bool, int]:
    """PID 파일로 프로세스 생존 여부 확인"""
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True
        )
        alive = str(pid) in result.stdout
        return alive, pid
    except Exception:
        return False, -1


def check_docker_exited() -> list[str]:
    """종료된 Docker 컨테이너 목록"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "status=exited",
             "--filter", "status=dead", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        names = [n.strip() for n in result.stdout.splitlines() if n.strip()]
        return names
    except Exception:
        return []


def run_health_check() -> str:
    """전체 헬스체크 실행 후 결과 문자열 반환"""
    ts = now_kst()
    issues = []
    ok_items = []

    # 1. MES 백엔드
    ok, detail = check_http("MES 백엔드", "http://localhost:8100/health")
    (ok_items if ok else issues).append(f"MES 백엔드(8100): {'정상' if ok else '이상 — ' + detail}")

    # 2. MES 프론트엔드
    ok, detail = check_http("MES 프론트엔드", "http://localhost:3100/")
    (ok_items if ok else issues).append(f"MES 프론트엔드(3100): {'정상' if ok else '이상 — ' + detail}")

    # 3. 대시보드
    ok, detail = check_http("대시보드", "http://localhost:5555/api/status")
    (ok_items if ok else issues).append(f"대시보드(5555): {'정상' if ok else '이상 — ' + detail}")

    # 4. 슬랙봇 PID
    pid_file = os.path.join(REPO, "logs", "slack-bot.pid")
    alive, pid = check_process_pid(pid_file)
    (ok_items if alive else issues).append(f"슬랙봇: {'정상(PID ' + str(pid) + ')' if alive else '프로세스 없음'}")

    # 5. 자동 커밋 PID
    pid_file = os.path.join(REPO, "logs", "auto-commit.pid")
    alive, pid = check_process_pid(pid_file)
    (ok_items if alive else issues).append(f"자동커밋: {'정상(PID ' + str(pid) + ')' if alive else '프로세스 없음 — 재시작 필요'}")

    # 6. Docker 컨테이너 비정상 종료
    exited = check_docker_exited()
    if exited:
        issues.append(f"Docker 다운 컨테이너: {', '.join(exited)}")
    else:
        ok_items.append("Docker: 모든 컨테이너 정상")

    # 7. Ollama 서버
    ok, detail = check_http("Ollama", "http://182.224.6.147:11434/", timeout=5)
    (ok_items if ok else issues).append(f"Ollama(182.224.6.147): {'정상' if ok else '응답 없음 — ' + detail}")

    # 결과 조합
    if issues:
        body = "⚠️ [정기점검 {ts}] 이상 항목:\n".format(ts=ts)
        for i in issues:
            body += f"• {i}\n"
        body += f"\n✅ 정상 {len(ok_items)}건 | ⚠️ 이상 {len(issues)}건"
    else:
        body = f"✅ [정기점검 {ts}] 전체 정상\n"
        for i in ok_items:
            body += f"• {i}\n"

    return body, bool(issues)


def main():
    pid_file = os.path.join(REPO, "logs", "health-check-scheduler.pid")
    # 이전 프로세스 종료
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old_pid = int(f.read().strip())
            subprocess.run(["taskkill", "/PID", str(old_pid), "/F"], capture_output=True)
            time.sleep(1)
        except Exception:
            pass
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    print(f"[health-check-scheduler] 시작 - {now_kst()} (1시간 주기)")

    while True:
        try:
            report, has_issues = run_health_check()
            print(report)
            send_to_max(report)
        except Exception as e:
            print(f"[오류] {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
