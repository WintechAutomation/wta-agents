"""
Atlassian Admin API 권한 부여/철회 가능 여부 점검
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from requests.auth import HTTPBasicAuth
import psycopg2
from dotenv import load_dotenv

load_dotenv("C:/MES/backend/.env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 55432)),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "postgres"),
}

def get_jira_config():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_data FROM api_systemconfig WHERE system_type = 'jira' LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            return data
    finally:
        conn.close()

def check(label, resp):
    print(f"\n[{label}]")
    print(f"  Status: {resp.status_code}")
    try:
        body = resp.json()
        print(f"  Body (일부): {json.dumps(body, ensure_ascii=False)[:300]}")
    except:
        print(f"  Body: {resp.text[:200]}")
    return resp.status_code, resp

if __name__ == "__main__":
    config = get_jira_config()
    jira_url = config.get("url") or config.get("base_url") or config.get("jira_url")
    email = config.get("email") or config.get("username") or config.get("user")
    token = config.get("api_token") or config.get("token") or config.get("password")
    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    print(f"Jira URL: {jira_url}")
    print(f"Auth: {email}")
    print("=" * 60)

    # 1. 현재 계정 정보 및 권한 확인
    r = requests.get(f"{jira_url}/rest/api/3/myself", auth=auth, headers=headers, timeout=10)
    status, _ = check("1. 현재 계정 (myself)", r)
    if status == 200:
        me = r.json()
        print(f"  → 이름: {me.get('displayName')}, accountId: {me.get('accountId')}")

    # 2. 전역 권한 확인 (관리자 여부)
    r = requests.get(f"{jira_url}/rest/api/3/mypermissions?permissions=ADMINISTER", auth=auth, headers=headers, timeout=10)
    check("2. 전역 관리자 권한 (ADMINISTER)", r)

    # 3. Atlassian Organization ID 조회 (Admin API)
    r = requests.get(
        "https://api.atlassian.com/admin/v1/orgs",
        auth=auth, headers=headers, timeout=10
    )
    check("3. Atlassian Admin API - 조직 목록", r)

    # 4. User Management API - 사용자 조회 시도
    # account_id 샘플: 조한종
    sample_account_id = "6013525165f20b0070cc6593"
    r = requests.get(
        f"https://api.atlassian.com/users/{sample_account_id}/manage",
        auth=auth, headers=headers, timeout=10
    )
    check("4. User Management API - 사용자 조회", r)

    # 5. Jira 사용자 그룹 목록 (그룹 기반 권한 관리)
    r = requests.get(f"{jira_url}/rest/api/3/groups/picker?maxResults=20", auth=auth, headers=headers, timeout=10)
    check("5. Jira 그룹 목록", r)

    # 6. 애플리케이션 역할 목록 (jira-software, confluence 등)
    r = requests.get(f"{jira_url}/rest/api/3/applicationrole", auth=auth, headers=headers, timeout=10)
    check("6. 애플리케이션 역할 목록", r)

    # 7. 특정 그룹 멤버 확인 (jira-software-users)
    r = requests.get(
        f"{jira_url}/rest/api/3/group/member",
        params={"groupname": "jira-software-users", "maxResults": 5},
        auth=auth, headers=headers, timeout=10
    )
    check("7. jira-software-users 그룹 멤버", r)

    # 8. Confluence REST API 접근 여부 확인
    confluence_url = jira_url.replace(".atlassian.net", ".atlassian.net/wiki")
    r = requests.get(f"{confluence_url}/rest/api/user/current", auth=auth, headers=headers, timeout=10)
    check("8. Confluence API - 현재 계정", r)

    print("\n" + "=" * 60)
    print("점검 완료")
