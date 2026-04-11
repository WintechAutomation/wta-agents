"""
LLM 서버 VLM 로드 테스트 및 로그 확인 (인코딩 안전)
"""
import os, sys

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

import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=user, password=password, timeout=15)
print("SSH 접속 성공\n")

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

# Ollama 로그 (영문만)
print("=== Ollama 로그 (최근 30줄) ===")
out, _ = run("journalctl -u ollama -n 30 --no-pager -o cat 2>/dev/null | strings | tail -30")
print(out or "(로그 없음)")

# CUDA/GPU 상세
print("=== GPU CUDA 정보 ===")
out, _ = run("nvidia-smi -q 2>/dev/null | grep -E 'Product Name|Total|Free|Used|CUDA' | head -20")
print(out or "(정보 없음)")

# qwen2.5vl 로드 테스트 (API 방식)
print("=== qwen2.5vl:7b API 로드 테스트 ===")
import subprocess
result = subprocess.run(
    ["curl", "-s", "--connect-timeout", "20", "--max-time", "90",
     "-X", "POST", f"http://{host}:11434/api/generate",
     "-H", "Content-Type: application/json",
     "-d", '{"model":"qwen2.5vl:7b","prompt":"hello","stream":false,"options":{"num_predict":5}}'],
    capture_output=True, text=True, timeout=100
)
print(result.stdout[:500] or "(응답 없음)")

# GPU 사용량 (로드 직후)
print("\n=== GPU 로드 후 상태 ===")
out, _ = run("nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv 2>/dev/null")
print(out or "(확인 불가)")

client.close()
