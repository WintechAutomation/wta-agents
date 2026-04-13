"""
메이써루이 프레스 #12~14 전장배선 서브태스크 25건 INSERT
MES API (save_subtasks) 사용 — control-agent 요청
"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv("C:/MES/backend/.env")

BASE_URL = "http://localhost:8100/api"

# 1. 로그인 — .env에서 MES 서비스 계정 로드
admin_id = None
admin_pw = None
with open("C:/MES/backend/.env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("MES_SERVICE_USERNAME="):
            admin_id = line.split("=", 1)[1]
        elif line.startswith("MES_SERVICE_PASSWORD="):
            admin_pw = line.split("=", 1)[1]

if not admin_id or not admin_pw:
    print("[ERROR] MES_SERVICE_USERNAME/PASSWORD not found in .env")
    exit(1)

login_res = requests.post(f"{BASE_URL}/auth/login", json={
    "username": admin_id,
    "password": admin_pw,
})
if login_res.status_code != 200:
    print(f"[ERROR] 로그인 실패: {login_res.status_code} {login_res.text[:200]}")
    exit(1)

login_data = login_res.json()
token = login_data["data"]["access"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print(f"[OK] 로그인 성공")

# 2. 서브태스크 목록 구성
subtasks = [
    {"task_item_code": "CM-HP3C-001", "task_item_name": "속판 제작 (장비 부착 전)", "priority": "medium", "status": "not_started", "order": 1},
    {"task_item_code": "CM-HP3C-002", "task_item_name": "속판 하네스 배선 (장비 부착 후)", "priority": "medium", "status": "not_started", "order": 2},
    {"task_item_code": "CM-HP3C-003", "task_item_name": "상부 유닛 작업", "priority": "medium", "status": "not_started", "order": 3},
    {"task_item_code": "CM-HP3C-004", "task_item_name": "CONV 유닛 작업", "priority": "medium", "status": "not_started", "order": 4},
    {"task_item_code": "CM-HP3C-005", "task_item_name": "LIFT 유닛 작업", "priority": "medium", "status": "not_started", "order": 5},
    {"task_item_code": "CM-HP3C-006", "task_item_name": "샘플링 유닛 작업", "priority": "medium", "status": "not_started", "order": 6},
    {"task_item_code": "CM-HP3C-007", "task_item_name": "디버링 유닛 작업", "priority": "medium", "status": "not_started", "order": 7},
    {"task_item_code": "CM-HP3C-008", "task_item_name": "저울 유닛 작업", "priority": "medium", "status": "not_started", "order": 8},
    {"task_item_code": "CM-HP3C-009", "task_item_name": "스테이션 유닛 작업", "priority": "medium", "status": "not_started", "order": 9},
    {"task_item_code": "CM-HP3C-010", "task_item_name": "상부 케이블 연장 및 포설", "priority": "medium", "status": "not_started", "order": 10},
    {"task_item_code": "CM-HP3C-011", "task_item_name": "Y축 작업", "priority": "medium", "status": "not_started", "order": 11},
    {"task_item_code": "CM-HP3C-012", "task_item_name": "SOL 판 작업", "priority": "medium", "status": "not_started", "order": 12},
    {"task_item_code": "CM-HP3C-013", "task_item_name": "SOL 이콘 배선", "priority": "medium", "status": "not_started", "order": 13},
    {"task_item_code": "CM-HP3C-014", "task_item_name": "ATC 이콘 배선", "priority": "medium", "status": "not_started", "order": 14},
    {"task_item_code": "CM-HP3C-015", "task_item_name": "ETC 이콘 배선", "priority": "medium", "status": "not_started", "order": 15},
    {"task_item_code": "CM-HP3C-016", "task_item_name": "CONV 이콘 배선", "priority": "medium", "status": "not_started", "order": 16},
    {"task_item_code": "CM-HP3C-017", "task_item_name": "트랜스 작업", "priority": "medium", "status": "not_started", "order": 17},
    {"task_item_code": "CM-HP3C-018", "task_item_name": "PDU 브라켓 작업", "priority": "medium", "status": "not_started", "order": 18},
    {"task_item_code": "CM-HP3C-019", "task_item_name": "메인스위치 브라켓 작업", "priority": "medium", "status": "not_started", "order": 19},
    {"task_item_code": "CM-HP3C-020", "task_item_name": "PC 배선", "priority": "medium", "status": "not_started", "order": 20},
    {"task_item_code": "CM-HP3C-021", "task_item_name": "OP 판넬", "priority": "medium", "status": "not_started", "order": 21},
    {"task_item_code": "CM-HP3C-022", "task_item_name": "메인도어 모니터 작업", "priority": "medium", "status": "not_started", "order": 22},
    {"task_item_code": "CM-HP3C-023", "task_item_name": "도어락", "priority": "medium", "status": "not_started", "order": 23},
    {"task_item_code": "CM-HP3C-024", "task_item_name": "타워램프", "priority": "medium", "status": "not_started", "order": 24},
    {"task_item_code": "CM-HP3C-025", "task_item_name": "JAW 툴 작업", "priority": "medium", "status": "not_started", "order": 25},
]

# 3. save_subtasks API 호출
payload = {
    "project_id": 93,
    "task_id": 4842,
    "subtasks": subtasks,
}

res = requests.post(
    f"{BASE_URL}/production/project-detailed-schedules/save_subtasks",
    json=payload,
    headers=headers,
)

print(f"[STATUS] {res.status_code}")
try:
    data = res.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception:
    print(res.text[:500])
