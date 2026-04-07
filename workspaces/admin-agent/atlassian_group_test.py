"""
Jira 그룹 기반 권한 부여/철회 API 상세 점검
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
        print(f"  Body: {json.dumps(body, ensure_ascii=False)[:400]}")
    except:
        print(f"  Body: {resp.text[:200]}")
    return resp.status_code

if __name__ == "__main__":
    config = get_jira_config()
    jira_url = config.get("url") or config.get("base_url") or config.get("jira_url")
    email = config.get("email") or config.get("username") or config.get("user")
    token = config.get("api_token") or config.get("token") or config.get("password")
    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    print(f"Jira URL: {jira_url}")
    print("=" * 60)

    # 1. 전체 그룹 목록 (54개)
    r = requests.get(
        f"{jira_url}/rest/api/3/group/bulk",
        params={"maxResults": 50},
        auth=auth, headers=headers, timeout=10
    )
    check("1. 전체 그룹 목록 (bulk)", r)
    if r.status_code == 200:
        groups = r.json().get("values", [])
        print(f"\n  주요 그룹 목록:")
        for g in groups[:30]:
            print(f"    - {g['name']} (id: {g['groupId']})")

    # 2. 애플리케이션 역할 상세 (jira-software)
    r = requests.get(f"{jira_url}/rest/api/3/applicationrole", auth=auth, headers=headers, timeout=10)
    check("2. 애플리케이션 역할 전체", r)
    if r.status_code == 200:
        roles = r.json()
        for role in roles:
            print(f"\n  역할: {role['key']}")
            print(f"    groups: {role.get('groups', [])}")
            print(f"    defaultGroups: {role.get('defaultGroups', [])}")
            print(f"    userCount: {role.get('userCount', '?')}")

    # 3. 그룹에 사용자 추가 API (권한 점검만 — 실제 변경 없음, 존재하지 않는 계정 사용)
    # POST /rest/api/3/group/user → 그룹에 사용자 추가
    # DELETE /rest/api/3/group/user → 그룹에서 사용자 제거
    # 테스트: 잘못된 accountId로 시도하여 API 응답 형태만 확인
    print("\n[3. 그룹 사용자 추가 API 응답 형태 확인 (dry-run)]")
    print("  POST /rest/api/3/group/user — 그룹에 사용자 추가")
    print("  DELETE /rest/api/3/group/user — 그룹에서 사용자 제거")
    print("  → 실제 변경은 수행하지 않음 (확인 목적)")

    # 4. jira-software-users 그룹 전체 멤버 수 확인
    r = requests.get(
        f"{jira_url}/rest/api/3/group/member",
        params={"groupname": "jira-software-users", "maxResults": 1},
        auth=auth, headers=headers, timeout=10
    )
    check("4. jira-software-users 전체 멤버 수", r)
    if r.status_code == 200:
        total = r.json().get("total", "?")
        print(f"  → 총 {total}명")

    # 5. Atlassian Org Admin API 토큰 유형 확인
    # api.atlassian.com 은 별도 API 토큰 필요
    r = requests.get(
        "https://api.atlassian.com/admin/v1/orgs",
        headers={**headers, "Authorization": f"Bearer {token}"},
        timeout=10
    )
    check("5. Admin API (Bearer 토큰 방식)", r)

    print("\n" + "=" * 60)
    print("점검 완료")
