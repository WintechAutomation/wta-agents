"""
Jira/Atlassian 전체 사용자 목록 및 마지막 활동일 조회
- DB에서 Jira API 설정 읽기
- 전체 사용자 목록 조회
"""
import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from requests.auth import HTTPBasicAuth
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

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
            cur.execute(
                "SELECT config_data FROM api_systemconfig WHERE system_type = 'jira' LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            return data
    finally:
        conn.close()

def get_all_users(jira_url, auth):
    """Jira 전체 사용자 목록 조회"""
    users = []
    start = 0
    max_results = 50
    while True:
        resp = requests.get(
            f"{jira_url}/rest/api/3/users/search",
            params={"startAt": start, "maxResults": max_results},
            auth=auth,
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"ERROR {resp.status_code}: {resp.text}")
            break
        batch = resp.json()
        if not batch:
            break
        users.extend(batch)
        if len(batch) < max_results:
            break
        start += max_results
    return users

def get_user_last_activity(jira_url, auth, account_id):
    """사용자 마지막 로그인/활동 조회 (Atlassian admin API)"""
    # Jira Cloud: /rest/api/3/user?accountId=
    resp = requests.get(
        f"{jira_url}/rest/api/3/user",
        params={"accountId": account_id, "expand": "groups,applicationRoles"},
        auth=auth,
        headers={"Accept": "application/json"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    return {}

if __name__ == "__main__":
    config = get_jira_config()
    if not config:
        print("Jira 설정을 DB에서 찾을 수 없습니다.")
        sys.exit(1)

    jira_url = config.get("url") or config.get("base_url") or config.get("jira_url")
    email = config.get("email") or config.get("username") or config.get("user")
    token = config.get("api_token") or config.get("token") or config.get("password")

    print(f"Jira URL: {jira_url}")
    print(f"Auth email: {email}")

    auth = HTTPBasicAuth(email, token)

    print("\n사용자 목록 조회 중...")
    users = get_all_users(jira_url, auth)
    print(f"총 {len(users)}명 조회됨\n")

    result = []
    for u in users:
        account_id = u.get("accountId", "")
        display_name = u.get("displayName", "")
        email_addr = u.get("emailAddress", "")
        account_type = u.get("accountType", "")
        active = u.get("active", False)

        # 비활성 또는 앱 계정 제외
        if account_type in ("app", "system") or not active:
            continue

        result.append({
            "accountId": account_id,
            "name": display_name,
            "email": email_addr,
            "active": active,
        })

    # 이름순 정렬
    result.sort(key=lambda x: x.get("name", ""))

    print(f"활성 사용자: {len(result)}명")
    for r in result:
        print(f"  - {r['name']} ({r['email']}) [active={r['active']}]")

    # JSON 저장
    output_path = "C:/MES/wta-agents/workspaces/admin-agent/jira_users_raw.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n저장 완료: {output_path}")
