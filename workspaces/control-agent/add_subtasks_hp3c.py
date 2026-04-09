"""
메이써루이 프레스 #12~14 전장배선 서브태스크 27건 추가
task_id: 4842, project_id: 93
"""
import os, json, sys
from pathlib import Path
import urllib.request
import urllib.parse

# .env 로드
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

if not PASSWORD:
    print("ERROR: MES_SERVICE_PASSWORD not found in .env")
    sys.exit(1)

# 1. 로그인 → JWT 토큰 획득
login_data = json.dumps({"username": USERNAME, "password": PASSWORD}).encode()
req = urllib.request.Request(
    f"{BASE_URL}/api/auth/login",
    data=login_data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=10) as resp:
    body = json.loads(resp.read())

token = body.get("data", {}).get("access") or body.get("data", {}).get("access_token") or body.get("access_token")
if not token:
    print(f"ERROR: 토큰 획득 실패: {body}")
    sys.exit(1)

print(f"로그인 성공, 토큰 획득")

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

# 2. 27개 항목
TASK_ID = 4842
PROJECT_ID = 93

items = [
    (1,  "속판 제작 (장비 부착 전)"),
    (2,  "속판 하네스 배선 (장비 부착 후)"),
    (3,  "상부 유닛 작업"),
    (4,  "샘플링 유닛 작업"),
    (5,  "디버링 유닛 작업"),
    (6,  "저울 유닛 작업"),
    (7,  "스테이션 유닛 작업"),
    (8,  "상부 케이블 연장 및 포설"),
    (9,  "Y축 작업"),
    (10, "FD 축 작업"),
    (11, "EV 축 작업"),
    (12, "SOL 판 작업"),
    (13, "SOL 이콘 배선"),
    (14, "ATC 이콘 배선"),
    (15, "ETC 이콘 배선"),
    (16, "트랜스 작업"),
    (17, "PDU 브라켓 작업"),
    (18, "메인스위치 브라켓 작업"),
    (19, "PC 배선"),
    (20, "OP 판넬"),
    (21, "메인도어 모니터 작업"),
    (22, "백도어 모니터 작업"),
    (23, "도어락"),
    (24, "타워램프"),
    (25, "JAW 툴 작업"),
    (26, "사진 및 스티커 작업"),
    (27, "하부 덕트 및 덕트커버"),
]

# 3. 추가 실행
success, failed = 0, []
for order, name in items:
    code = f"CM-HP3C-{order:03d}"
    payload = json.dumps({
        "task_id": TASK_ID,
        "project_id": PROJECT_ID,
        "task_item_code": code,
        "task_item_name": name,
        "order": order,
        "status": "not_started"
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/production/project-detailed-schedules/append_subtask",
        data=payload,
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        print(f"  [OK] {code} {name}")
        success += 1
    except Exception as e:
        print(f"  [FAIL] {code} {name} — {e}")
        failed.append(code)

print(f"\n완료: {success}/27 성공, 실패: {len(failed)}건 {failed if failed else ''}")
