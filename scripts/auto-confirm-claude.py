"""
Claude Code 개발 채널 경고 프롬프트 자동 확인 래퍼.
'WARNING: Loading development channels' 프롬프트가 나오면
자동으로 '1' (I am using this for local development)을 선택한다.

Usage: python auto-confirm-claude.py [claude args...]
Example: python auto-confirm-claude.py --model sonnet --dangerously-skip-permissions --dangerously-load-development-channels server:agent-channel
"""

import sys
import subprocess
import threading
import os
import shutil
import time

CLAUDE_PATH = shutil.which("claude") or "claude"

def reader(pipe, name, trigger_event):
    """stdout/stderr 읽기 + 프롬프트 감지"""
    buffer = ""
    try:
        while True:
            chunk = pipe.read(1)
            if not chunk:
                break
            ch = chunk.decode("utf-8", errors="replace")
            sys.stdout.write(ch)
            sys.stdout.flush()
            buffer += ch
            # 프롬프트 감지: "Enter to confirm" 또는 "Esc to cancel"
            if "Enter to confirm" in buffer or "Esc to cancel" in buffer:
                trigger_event.set()
                buffer = ""
            # 버퍼 크기 제한
            if len(buffer) > 500:
                buffer = buffer[-200:]
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    cmd = [CLAUDE_PATH] + args

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    prompt_detected = threading.Event()

    # stdout, stderr 리더 스레드
    t_out = threading.Thread(target=reader, args=(proc.stdout, "stdout", prompt_detected), daemon=True)
    t_err = threading.Thread(target=reader, args=(proc.stderr, "stderr", prompt_detected), daemon=True)
    t_out.start()
    t_err.start()

    # 프롬프트 대기 (최대 15초)
    if prompt_detected.wait(timeout=15):
        time.sleep(0.3)  # 프롬프트 완전히 출력될 때까지 대기
        proc.stdin.write(b"\n")  # Enter = 1번 선택 (기본값)
        proc.stdin.flush()

    # 이후 stdin 전달 (대화형 세션 유지)
    try:
        while True:
            data = sys.stdin.buffer.read(1)
            if not data:
                break
            proc.stdin.write(data)
            proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass

    proc.wait()
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
