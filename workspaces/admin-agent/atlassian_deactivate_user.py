"""
김근형 계정 — Jira/Confluence 그룹 접근 차단
- jira-software-users 그룹에서 제거
- confluence-users 그룹에서 제거 (있는 경우)
"""
import json, sys, os, requests
from requests.auth import HTTPBasicAuth
import psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv("C:/MES/backend/.env")
DB_CONFIG = {
    "host": os.getenv("DB_HOST","localhost"),
    "port": int(os.getenv("DB_PORT",55432)),
    "user": os.getenv("DB_USER","postgres"),
    "password": os.getenv("DB_PASSWORD",""),
    "dbname": os.getenv("DB_NAME","postgres"),
}
conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute("SELECT config_data FROM api_systemconfig WHERE system_type = 'jira' LIMIT 1")
    row = cur.fetchone()
    config = row[0] if row else {}
    if isinstance(config, str): config = json.loads(config)
conn.close()

jira_url = config.get("url") or config.get("base_url")
email = config.get("email") or config.get("username")
token = config.get("api_token") or config.get("token")
auth = HTTPBasicAuth(email, token)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

ACCOUNT_ID = "712020:f8633732-48ef-460d-91a5-3b0eda10907a"
TARGET_NAME = "김근형"

print(f"대상: {TARGET_NAME} ({ACCOUNT_ID})")
print("=" * 60)

# 1. 현재 소속 그룹 조회
r = requests.get(
    f"{jira_url}/rest/api/3/user",
    params={"accountId": ACCOUNT_ID, "expand": "groups,applicationRoles"},
    auth=auth, headers=headers, timeout=10
)
if r.status_code != 200:
    print(f"사용자 조회 실패: {r.status_code} {r.text}")
    sys.exit(1)

user_data = r.json()
groups = user_data.get("groups", {}).get("items", [])
app_roles = user_data.get("applicationRoles", {}).get("items", [])
print(f"현재 소속 그룹: {[g['name'] for g in groups]}")
print(f"애플리케이션 역할: {[a['key'] for a in app_roles]}")

# 2. 제거 대상 그룹 (존재하는 것만)
REMOVE_GROUPS = [g["name"] for g in groups if g["name"] not in ("administrators", "jira-administrators", "org-admins")]
print(f"\n제거 대상 그룹: {REMOVE_GROUPS}")

results = []
for group_name in REMOVE_GROUPS:
    # groupId 조회
    r_grp = requests.get(
        f"{jira_url}/rest/api/3/group",
        params={"groupname": group_name},
        auth=auth, headers=headers, timeout=10
    )
    if r_grp.status_code != 200:
        results.append({"group": group_name, "status": "그룹 조회 실패", "code": r_grp.status_code})
        continue
    group_id = r_grp.json().get("groupId")

    # 그룹 멤버 제거
    r_del = requests.delete(
        f"{jira_url}/rest/api/3/group/user",
        params={"groupId": group_id, "accountId": ACCOUNT_ID},
        auth=auth, headers=headers, timeout=10
    )
    status_label = "제거 완료" if r_del.status_code == 200 else f"실패({r_del.status_code})"
    results.append({"group": group_name, "status": status_label, "code": r_del.status_code})
    print(f"  [{group_name}] → {status_label}")

# 3. 처리 후 그룹 재확인
r2 = requests.get(
    f"{jira_url}/rest/api/3/user",
    params={"accountId": ACCOUNT_ID, "expand": "groups"},
    auth=auth, headers=headers, timeout=10
)
remaining = []
if r2.status_code == 200:
    remaining = [g["name"] for g in r2.json().get("groups", {}).get("items", [])]

print(f"\n처리 후 잔여 그룹: {remaining}")
print("\n처리 요약:")
for res in results:
    print(f"  {res['group']}: {res['status']}")

# JSON 결과 저장
output = {
    "target": TARGET_NAME,
    "accountId": ACCOUNT_ID,
    "removed_groups": [r["group"] for r in results if r["code"] == 200],
    "failed_groups": [r["group"] for r in results if r["code"] != 200],
    "remaining_groups": remaining,
}
with open("C:/MES/wta-agents/workspaces/admin-agent/deactivate_result.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n결과 저장 완료")
