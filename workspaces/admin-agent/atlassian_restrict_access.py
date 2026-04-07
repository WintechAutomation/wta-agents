"""
Atlassian 액세스 제한 — 이름 기반 사용자 검색 후 소속 그룹 전체 제거
사용법: python atlassian_restrict_access.py "사용자이름"
결과: JSON 파일 (restrict_result.json)에 저장
"""
import json
import os
import sys
import requests
from requests.auth import HTTPBasicAuth
import psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("C:/MES/backend/.env")

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
RESULT_FILE = os.path.join(WORKSPACE, "restrict_result.json")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 55432)),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "postgres"),
}

# 관리자 그룹 — 제거 대상에서 제외
ADMIN_GROUPS = {"administrators", "jira-administrators", "org-admins", "site-admins"}


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


def find_user_by_name(jira_url, auth, headers, display_name):
    """displayName으로 Jira 사용자 검색 — 정확히 일치하는 계정 반환"""
    resp = requests.get(
        f"{jira_url}/rest/api/3/user/search",
        params={"query": display_name, "maxResults": 20},
        auth=auth, headers=headers, timeout=10,
    )
    if resp.status_code != 200:
        return None, f"사용자 검색 실패: {resp.status_code}"

    users = resp.json()
    # 정확히 일치하는 사용자 우선
    for u in users:
        if u.get("displayName") == display_name:
            return u, None
    # 부분 일치
    for u in users:
        if display_name in u.get("displayName", ""):
            return u, None
    if users:
        return users[0], None
    return None, f"'{display_name}' 사용자를 찾을 수 없습니다"


def get_user_groups(jira_url, auth, headers, account_id):
    """사용자 소속 그룹 조회"""
    resp = requests.get(
        f"{jira_url}/rest/api/3/user",
        params={"accountId": account_id, "expand": "groups"},
        auth=auth, headers=headers, timeout=10,
    )
    if resp.status_code != 200:
        return [], f"사용자 조회 실패: {resp.status_code}"
    groups = resp.json().get("groups", {}).get("items", [])
    return groups, None


def remove_from_groups(jira_url, auth, headers, account_id, groups):
    """관리자 그룹 제외, 나머지 그룹에서 제거"""
    results = []
    for g in groups:
        group_name = g["name"]
        if group_name in ADMIN_GROUPS:
            results.append({"group": group_name, "status": "스킵(관리자그룹)", "code": 0})
            continue

        # groupId 조회
        r_grp = requests.get(
            f"{jira_url}/rest/api/3/group",
            params={"groupname": group_name},
            auth=auth, headers=headers, timeout=10,
        )
        if r_grp.status_code != 200:
            results.append({"group": group_name, "status": "그룹 조회 실패", "code": r_grp.status_code})
            continue
        group_id = r_grp.json().get("groupId")

        # 그룹에서 제거
        r_del = requests.delete(
            f"{jira_url}/rest/api/3/group/user",
            params={"groupId": group_id, "accountId": account_id},
            auth=auth, headers=headers, timeout=10,
        )
        status_label = "제거 완료" if r_del.status_code == 200 else f"실패({r_del.status_code})"
        results.append({"group": group_name, "status": status_label, "code": r_del.status_code})
        print(f"  [{group_name}] -> {status_label}")

    return results


def restrict_access(target_name):
    """메인: 이름으로 사용자 찾아 모든 비관리자 그룹에서 제거"""
    config = get_jira_config()
    if not config:
        return {"error": "Jira 설정을 찾을 수 없습니다"}

    jira_url = config.get("url") or config.get("base_url")
    email = config.get("email") or config.get("username")
    token = config.get("api_token") or config.get("token")
    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # 1. 사용자 검색
    print(f"대상: {target_name}")
    user, err = find_user_by_name(jira_url, auth, headers, target_name)
    if err:
        return {"error": err, "target": target_name}
    account_id = user["accountId"]
    display_name = user.get("displayName", target_name)
    print(f"찾은 사용자: {display_name} ({account_id})")

    # 2. 소속 그룹 조회
    groups, err = get_user_groups(jira_url, auth, headers, account_id)
    if err:
        return {"error": err, "target": display_name, "accountId": account_id}
    print(f"소속 그룹: {[g['name'] for g in groups]}")

    # 3. 그룹에서 제거
    results = remove_from_groups(jira_url, auth, headers, account_id, groups)

    # 4. 처리 후 잔여 그룹 확인
    remaining_groups, _ = get_user_groups(jira_url, auth, headers, account_id)
    remaining = [g["name"] for g in remaining_groups]

    output = {
        "target": display_name,
        "accountId": account_id,
        "removed_groups": [r["group"] for r in results if r["code"] == 200],
        "skipped_groups": [r["group"] for r in results if r["code"] == 0],
        "failed_groups": [r["group"] for r in results if r["code"] not in (200, 0)],
        "remaining_groups": remaining,
    }
    return output


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python atlassian_restrict_access.py \"사용자이름\"")
        sys.exit(1)

    target = sys.argv[1]
    result = restrict_access(target)

    # 결과 저장
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
    if result.get("error"):
        sys.exit(1)
