"""
에이전트 상시 대기 루프 — WebSocket(SocketIO) 기반
- 대시보드에 WebSocket 연결 유지
- 메시지 실시간 수신 → claude -p 처리 → 응답 전송
- 자동 재연결 + 하트비트
"""
import sys
import os
import time
import subprocess

# Windows UTF-8 강제 (SocketIO 스레드 포함)
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# 기존 stdout/stderr도 교체
if hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
import socketio

DASHBOARD_URL = "http://localhost:5555"
CLAUDE_PATH = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
RECONNECT_DELAY = 5  # 재연결 대기 (초)


def create_agent(agent_id, workspace_dir):
    """SocketIO 클라이언트 에이전트 생성"""
    sio = socketio.Client(reconnection=True, reconnection_delay=RECONNECT_DELAY)

    @sio.event
    def connect():
        print(f"[연결] 대시보드 연결 성공")
        # 에이전트 등록
        sio.emit("register", {"agent_id": agent_id})

    @sio.on("registered")
    def on_registered(data):
        print(f"[등록] {data.get('agent_id')} 등록 완료 ({data.get('time')})")
        # 준비 완료 보고
        sio.emit("message", {
            "from": agent_id,
            "to": "MAX",
            "content": f"{agent_id} 에이전트 기동 완료. 실시간 대기 중.",
        })

    @sio.on("new_message")
    def on_message(msg):
        """메시지 수신 — 자기에게 온 것만 처리"""
        target = msg.get("to", "")
        sender = msg.get("from", "")
        content = msg.get("content", "")

        # 자기에게 온 메시지만 처리 (broadcast 중 to=all도 무시)
        if target != agent_id:
            return

        # 자기가 보낸 메시지 무시
        if sender == agent_id:
            return

        # 빈 메시지 무시
        if not content.strip():
            print(f"[무시] {sender} → {agent_id}: (빈 메시지)")
            return

        print(f"[수신] {sender} → {agent_id}: {content[:100]}")

        # claude -p 실행
        response = run_claude(agent_id, workspace_dir, sender, content)

        # 응답 전송
        sio.emit("message", {
            "from": agent_id,
            "to": sender,
            "content": response,
        })
        print(f"[응답] {agent_id} → {sender}: {response[:100]}...")

    @sio.on("heartbeat_ack")
    def on_heartbeat_ack(data):
        pass  # 조용히 처리

    @sio.event
    def disconnect():
        print(f"[연결 해제] 대시보드 연결 끊김. 재연결 시도...")

    return sio


def run_claude(agent_id, workspace_dir, sender, content):
    """claude -p --continue 로 메시지 처리 — 상시 세션 유지"""
    prompt = f"[{sender}으로부터 메시지] {content}\n\n작업 완료 후 결과만 간결하게 출력해줘."

    try:
        # --continue: 이전 대화 맥락 유지
        cmd = f'"{CLAUDE_PATH}" -p - --continue --dangerously-skip-permissions'
        result = subprocess.run(
            cmd,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            input=prompt,
            timeout=300,
            encoding="utf-8",
            errors="replace",
            shell=True,
        )
        response = result.stdout.strip()
        if not response:
            response = f"(처리 완료, 출력 없음. stderr: {result.stderr[:200]})"
        return response
    except subprocess.TimeoutExpired:
        return "(처리 시간 초과 — 5분)"
    except Exception as e:
        return f"(처리 오류: {e})"


def kill_existing(agent_id, workspace_dir):
    """이전 동일 에이전트 프로세스 종료 (PID 파일 기반)"""
    pid_file = os.path.join(workspace_dir, f"{agent_id}.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # 존재 확인
            print(f"[정리] 이전 프로세스 종료: PID {old_pid}")
            import signal
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(1)
        except (ProcessLookupError, ValueError, OSError):
            pass
    # 현재 PID 저장
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))


def main():
    if len(sys.argv) < 2:
        print("사용법: python agent-loop.py <agent_id>")
        sys.exit(1)

    agent_id = sys.argv[1]
    workspace_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "workspaces", agent_id,
    )

    if not os.path.isdir(workspace_dir):
        print(f"[오류] 워크스페이스 없음: {workspace_dir}")
        sys.exit(1)

    # 중복 방지
    kill_existing(agent_id, workspace_dir)

    print(f"=== {agent_id} 에이전트 (WebSocket) ===")
    print(f"워크스페이스: {workspace_dir}")
    print(f"대시보드: {DASHBOARD_URL}")
    print()

    sio = create_agent(agent_id, workspace_dir)

    while True:
        try:
            sio.connect(DASHBOARD_URL)
            sio.wait()  # 연결 유지 — 이벤트 루프
        except socketio.exceptions.ConnectionError as e:
            print(f"[연결 실패] {e}. {RECONNECT_DELAY}초 후 재시도...")
            time.sleep(RECONNECT_DELAY)
        except KeyboardInterrupt:
            print(f"\n[종료] {agent_id} 에이전트 종료")
            if sio.connected:
                sio.emit("message", {
                    "from": agent_id,
                    "to": "MAX",
                    "content": f"{agent_id} 에이전트 종료됨.",
                })
                sio.disconnect()
            break
        except Exception as e:
            print(f"[오류] {e}. {RECONNECT_DELAY}초 후 재시도...")
            time.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    main()
