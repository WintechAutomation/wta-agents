"""
Atlassian User Management API 상세 테스트
- managed accounts / lifecycle 제어 API 경로 탐색
"""
import json, sys, requests
from requests.auth import HTTPBasicAuth
import psycopg2, os
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

# Org Token (파일에서)
with open("C:/MES/wta-agents/config/atlassian-org-id.txt") as f:
    ORG_ID = f.read().strip()
with open("C:/MES/wta-agents/config/atlassian-org-token.txt") as f:
    ORG_TOKEN = f.read().strip()

org_headers = {
    "Authorization": f"Bearer {ORG_TOKEN}",
    "Accept": "application/json",
}

# Jira API Token (DB에서)
load_dotenv("C:/MES/backend/.env")
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 55432)),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "postgres"),
}
conn = psycopg2.connect(**DB_CONFIG)
with conn.cursor() as cur:
    cur.execute("SELECT config_data FROM api_systemconfig WHERE system_type = 'jira' LIMIT 1")
    row = cur.fetchone()
    config = row[0] if row else {}
    if isinstance(config, str):
        config = json.loads(config)
conn.close()

jira_url = config.get("url") or config.get("base_url")
jira_email = config.get("email") or config.get("username")
jira_token = config.get("api_token") or config.get("token")
jira_auth = HTTPBasicAuth(jira_email, jira_token)
jira_headers = {"Accept": "application/json", "Content-Type": "application/json"}

SAMPLE_ACCOUNT_ID = "6013525165f20b0070cc6593"  # 조한종 (본인)

def check(label, resp):
    print(f"\n[{label}]")
    print(f"  Status: {resp.status_code}")
    try:
        body = resp.json()
        print(f"  Body: {json.dumps(body, ensure_ascii=False)[:500]}")
    except Exception:
        print(f"  Body: {resp.text[:300]}")
    return resp.status_code, resp

print("=" * 60)
print("Atlassian User Management API 테스트")
print(f"Org ID: {ORG_ID}")
print("=" * 60)

# 1. User Management API v1 (accountId로 직접 조회)
r = requests.get(
    f"https://api.atlassian.com/users/{SAMPLE_ACCOUNT_ID}/manage",
    headers=org_headers, timeout=10
)
check("1. User manage 조회 (org token)", r)

# 2. lifecycle 상태 조회
r = requests.get(
    f"https://api.atlassian.com/users/{SAMPLE_ACCOUNT_ID}/manage/lifecycle/enable",
    headers=org_headers, timeout=10
)
check("2. lifecycle/enable (GET)", r)

# 3. Org managed accounts 조회 (v2)
r = requests.get(
    f"https://api.atlassian.com/admin/v1/orgs/{ORG_ID}/directory/users",
    headers=org_headers, timeout=10
)
check("3. directory/users (v1)", r)

# 4. SCIM Users (Atlassian Access SCIM)
r = requests.get(
    f"https://api.atlassian.com/scim/directory/{ORG_ID}/Users",
    headers=org_headers, timeout=10
)
check("4. SCIM Users", r)

# 5. Jira API로 특정 사용자 조회 + groups 확인
r = requests.get(
    f"{jira_url}/rest/api/3/user",
    params={"accountId": SAMPLE_ACCOUNT_ID, "expand": "groups,applicationRoles"},
    auth=jira_auth, headers=jira_headers, timeout=10
)
s5, r5 = check("5. Jira user 상세 (groups)", r)
if s5 == 200:
    groups = r5.json().get("groups", {}).get("items", [])
    print(f"  → 소속 그룹: {[g['name'] for g in groups]}")

# 6. Jira API로 그룹 멤버 추가/제거 가능 여부 확인 (OPTIONS)
r = requests.options(
    f"{jira_url}/rest/api/3/group/user",
    auth=jira_auth, headers=jira_headers, timeout=10
)
check("6. Jira 그룹 멤버 관리 OPTIONS", r)
if r.status_code < 400:
    print(f"  → Allow: {r.headers.get('Allow', 'N/A')}")

print("\n" + "=" * 60)
print("테스트 완료 (모든 요청은 읽기 전용)")
