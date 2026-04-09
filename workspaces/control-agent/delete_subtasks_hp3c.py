"""
메이써루이 전장배선(task_id=4842) 서브태스크 전체 삭제
"""
import os, json, sys
from pathlib import Path
import urllib.request

env_path = Path("C:/MES/backend/.env")
env = {}
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

BASE_URL = "http://localhost:8100"
USERNAME = env.get("MES_SERVICE_USERNAME", "max")
PASSWORD = env.get("MES_SERVICE_PASSWORD", "")

# 로그인
login_data = json.dumps({"username": USERNAME, "password": PASSWORD}).encode()
req = urllib.request.Request(
    f"{BASE_URL}/api/auth/login",
    data=login_data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=10) as resp:
    body = json.loads(resp.read())

token = body.get("data", {}).get("access")
if not token:
    print(f"ERROR: 토큰 획득 실패")
    sys.exit(1)

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

# task_id=4842 서브태스크 목록 조회
req = urllib.request.Request(
    f"{BASE_URL}/api/production/project-detailed-schedules/4842/task_with_subtasks",
    headers=headers,
    method="GET"
)
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read())

subtasks = data.get("data", {}).get("subtasks", [])
print(f"삭제 대상: {len(subtasks)}건")

success, failed = 0, []
for st in subtasks:
    sid = st.get("id")
    name = st.get("task_item_name", "")
    req = urllib.request.Request(
        f"{BASE_URL}/api/production/project-detailed-schedules/subtasks/{sid}",
        headers=headers,
        method="DELETE"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        print(f"  [OK] id={sid} {name}")
        success += 1
    except Exception as e:
        print(f"  [FAIL] id={sid} {name} — {e}")
        failed.append(sid)

print(f"\n완료: {success}/{len(subtasks)} 삭제, 실패: {len(failed)}건")
