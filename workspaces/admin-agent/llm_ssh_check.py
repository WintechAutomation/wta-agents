"""
LLM 서버 SSH 접속 및 상태 확인 스크립트
자격증명은 .env에서만 로드, 평문 노출 금지
"""
import os
import sys

# .env 로드
env_path = r"C:\MES\wta-agents\.env"
env = {}
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

host = env.get("LLM_SSH_HOST", "182.224.6.147")
port = int(env.get("LLM_SSH_PORT", "2222"))
user = env.get("LLM_SSH_USER", "root")
password = env.get("LLM_SSH_PASSWORD", "")

if not password:
    print("ERROR: LLM_SSH_PASSWORD not found in .env")
    sys.exit(1)

try:
    import paramiko
except ImportError:
    print("paramiko 없음 — 설치 중...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

print(f"SSH 접속 시도: {user}@{host}:{port}")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, port=port, username=user, password=password, timeout=15)
    print("SSH 접속 성공\n")

    commands = [
        ("ollama --version", "Ollama 버전"),
        ("ollama list", "모델 목록"),
        ("ollama ps", "실행 중 모델"),
        ("nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader", "GPU 상태"),
        ("nvidia-smi", "nvidia-smi 전체"),
        ("journalctl -u ollama -n 50 --no-pager 2>/dev/null || cat /var/log/ollama.log 2>/dev/null | tail -50 || echo 'no ollama log'", "Ollama 로그"),
        ("ls /var/log/ollama* 2>/dev/null || echo 'no ollama log files'", "Ollama 로그 파일"),
    ]

    for cmd, label in commands:
        print(f"\n=== {label} ===")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err and "UnicodeEncode" not in err:
            print(f"[stderr] {err}")

    # qwen2.5vl:7b 직접 로드 테스트
    print("\n=== qwen2.5vl:7b 로드 테스트 ===")
    cmd = "OLLAMA_DEBUG=1 timeout 90 ollama run qwen2.5vl:7b 'hello' 2>&1 | head -30"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=100)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(out if out else "(출력 없음)")
    if err:
        print(f"[stderr] {err}")

except paramiko.AuthenticationException:
    print("인증 실패 (비밀번호 불일치 또는 키 문제)")
    sys.exit(1)
except Exception as e:
    print(f"접속 실패: {type(e).__name__}: {e}")
    sys.exit(1)
finally:
    client.close()
