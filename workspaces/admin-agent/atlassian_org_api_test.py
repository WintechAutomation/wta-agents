"""
Atlassian Organization API Token 유효성 및 사용자 관리 API 테스트
- 파일에서 토큰 읽기 (터미널 노출 없음)
- 실제 변경 없음, 조회만
"""
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests

ORG_ID_FILE = "C:/MES/wta-agents/config/atlassian-org-id.txt"
ORG_TOKEN_FILE = "C:/MES/wta-agents/config/atlassian-org-token.txt"

with open(ORG_ID_FILE) as f:
    ORG_ID = f.read().strip()

with open(ORG_TOKEN_FILE) as f:
    ORG_TOKEN = f.read().strip()

headers = {
    "Authorization": f"Bearer {ORG_TOKEN}",
    "Accept": "application/json",
}

def check(label, resp):
    print(f"\n[{label}]")
    print(f"  Status: {resp.status_code}")
    try:
        body = resp.json()
        print(f"  Body: {json.dumps(body, ensure_ascii=False)[:400]}")
    except Exception:
        print(f"  Body: {resp.text[:300]}")
    return resp.status_code, resp


# 1. Organization 조회 (토큰 유효성)
r = requests.get("https://api.atlassian.com/admin/v1/orgs", headers=headers, timeout=10)
status, _ = check("1. Organization 목록 조회", r)

# 2. 특정 Org 정보
r = requests.get(f"https://api.atlassian.com/admin/v1/orgs/{ORG_ID}", headers=headers, timeout=10)
check("2. Org 상세 조회", r)

# 3. Org 사용자 목록 (첫 페이지만)
r = requests.get(
    f"https://api.atlassian.com/admin/v1/orgs/{ORG_ID}/users",
    headers=headers,
    params={"limit": 5},
    timeout=10
)
status3, resp3 = check("3. Org 사용자 목록 (5명 샘플)", r)

sample_account_id = None
if status3 == 200:
    data = resp3.json()
    users = data.get("data", [])
    print(f"  → 조회된 사용자 수: {len(users)}")
    if users:
        u = users[0]
        sample_account_id = u.get("account_id") or u.get("accountId")
        print(f"  → 샘플 계정: {u.get('name') or u.get('display_name')} / {sample_account_id}")

# 4. 특정 사용자 관리 정보 조회 (조회만, 변경 없음)
if sample_account_id:
    r = requests.get(
        f"https://api.atlassian.com/users/{sample_account_id}/manage",
        headers=headers,
        timeout=10
    )
    check("4. User Management API - 사용자 조회 (변경 없음)", r)

# 5. 계정 활성/비활성 API 엔드포인트 존재 확인 (OPTIONS/HEAD)
if sample_account_id:
    r = requests.get(
        f"https://api.atlassian.com/users/{sample_account_id}/manage/lifecycle/enable",
        headers=headers,
        timeout=10
    )
    check("5. lifecycle/enable 엔드포인트 확인 (조회만)", r)

print("\n" + "=" * 60)
print("테스트 완료 (모든 요청은 읽기 전용)")
