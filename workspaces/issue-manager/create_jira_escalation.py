"""
Critical NC 기한초과 Jira 에스컬레이션 이슈 생성
- DB에서 Jira 설정 읽기
- Critical 10건 그룹핑 후 이슈 생성
"""
# -*- coding: utf-8 -*-
import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
from requests.auth import HTTPBasicAuth
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# .env 로드
load_dotenv("C:/MES/backend/.env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 55432)),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "dbname": os.getenv("DB_NAME", "postgres"),
}

# Critical NC 10건 데이터 (nc-manager 제공)
CRITICAL_NCS = [
    {"id": 186,  "title": "스토퍼 길이 부족 설계 결함",              "manager": "조광현", "overdue_days": 232},
    {"id": 342,  "title": "대칭 가공 표시 누락",                      "manager": "정정일", "overdue_days": 199},
    {"id": 343,  "title": "레이던트 코팅 누락 설계 결함",              "manager": "정정일", "overdue_days": 199},
    {"id": 344,  "title": "볼스크류와 서포트 너트 피치 불일치",        "manager": "정정일", "overdue_days": 199},
    {"id": 349,  "title": "볼스크류 키자리 설계 누락",                 "manager": "정정일", "overdue_days": 197},
    {"id": 352,  "title": "풀리고정볼트 체결 설계 결함",               "manager": "정정일", "overdue_days": 197},
    {"id": 367,  "title": "조립 불가한 핀 설계 결함",                  "manager": "정정일", "overdue_days": 189},
    {"id": 368,  "title": "렌치 사용 불가 표시 위치 설계 결함",        "manager": "정정일", "overdue_days": 189},
    {"id": 370,  "title": "설계 불균형으로 인한 부위 치우침",          "manager": "정정일", "overdue_days": 189},
    {"id": 371,  "title": "설계 간섭으로 인한 문제 발생",              "manager": "정정일", "overdue_days": 189},
]

PROJECT_NAME = "MMC 검사기 F2 #1"
JIRA_PROJECT_KEY = "JPJMMHIM0001"  # jira_created.json에서 확인


def get_jira_config():
    """MES DB에서 Jira 설정 조회"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT config_data FROM api_systemconfig WHERE system_type = 'jira' LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Jira 설정을 찾을 수 없습니다")
            data = row[0]
            if isinstance(data, str):
                data = json.loads(data)
            return data
    finally:
        conn.close()


def get_jira_user_account_id(jira_url, auth, display_name):
    """담당자 이름으로 Jira account ID 조회"""
    resp = requests.get(
        f"{jira_url}/rest/api/3/user/search",
        params={"query": display_name, "maxResults": 5},
        auth=auth,
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code == 200:
        users = resp.json()
        if users:
            return users[0].get("accountId")
    return None


def create_jira_issue(jira_url, auth, project_key, summary, description, assignee_id=None):
    """Jira 이슈 생성"""
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
            "issuetype": {"id": "11621"},  # 작업 (Task)
            "priority": {"name": "Highest"},
        }
    }
    if assignee_id:
        payload["fields"]["assignee"] = {"accountId": assignee_id}

    resp = requests.post(
        f"{jira_url}/rest/api/3/issue",
        json=payload,
        auth=auth,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15,
    )
    if not resp.ok:
        print(f"  ERROR {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp.json()


def build_issue_description(ncs, manager_name, project_name):
    """그룹별 이슈 설명 생성"""
    today = datetime.now().strftime("%Y-%m-%d")
    nc_list = "\n".join(
        f"• NC#{nc['id']} — {nc['title']} ({nc['overdue_days']}일 초과)"
        for nc in ncs
    )
    return (
        f"[에스컬레이션] {project_name} 부적합 미조치 건 일괄 처리 요청\n\n"
        f"생성일: {today}\n"
        f"담당자: {manager_name}\n"
        f"우선순위: Critical (기준 3일)\n\n"
        f"■ 미조치 부적합 목록\n{nc_list}\n\n"
        f"즉시 조치 및 결과 MES 시스템 등록 요청드립니다."
    )


def main():
    print("=== Jira 에스컬레이션 이슈 생성 시작 ===")

    # Jira 설정 조회
    cfg = get_jira_config()
    jira_url = (cfg.get("url") or cfg.get("jira_url", "")).rstrip("/")
    username = cfg.get("username") or cfg.get("email", "")
    api_token = cfg.get("api_token", "")

    if not all([jira_url, username, api_token]):
        print("ERROR: Jira 설정 불완전 (url/username/api_token 필요)")
        sys.exit(1)

    auth = HTTPBasicAuth(username, api_token)
    print(f"Jira URL: {jira_url}")
    print(f"Project: {JIRA_PROJECT_KEY}")

    # 담당자별 그룹핑
    groups = {}
    for nc in CRITICAL_NCS:
        mgr = nc["manager"]
        groups.setdefault(mgr, []).append(nc)

    created_issues = []
    workspace = "C:/MES/wta-agents/workspaces/issue-manager"

    for manager_name, ncs in groups.items():
        print(f"\n담당자: {manager_name} ({len(ncs)}건)")

        # 담당자 Jira account ID 조회
        account_id = get_jira_user_account_id(jira_url, auth, manager_name)
        if account_id:
            print(f"  account_id: {account_id}")
        else:
            print(f"  WARNING: {manager_name} Jira 계정 미확인 (담당자 미지정)")

        # 이슈 제목 및 설명
        nc_ids = ", ".join(f"NC#{nc['id']}" for nc in ncs)
        summary = f"[에스컬레이션] {PROJECT_NAME} Critical 부적합 미조치 — {manager_name} 담당 ({len(ncs)}건)"
        description = build_issue_description(ncs, manager_name, PROJECT_NAME)

        # 이슈 생성
        result = create_jira_issue(jira_url, auth, JIRA_PROJECT_KEY, summary, description, account_id)
        issue_key = result.get("key", "")
        issue_url = f"{jira_url}/browse/{issue_key}"
        print(f"  OK 생성: {issue_key} -- {issue_url}")

        created_issues.append({
            "manager": manager_name,
            "nc_count": len(ncs),
            "nc_ids": nc_ids,
            "project": JIRA_PROJECT_KEY,
            "key": issue_key,
            "url": issue_url,
        })

    # 결과 저장
    output_file = f"{workspace}/jira_escalation_2026-03-31.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(created_issues, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_file}")

    # 결과 출력
    print("\n=== 생성 완료 ===")
    for item in created_issues:
        print(f"* {item['key']} ({item['manager']}, {item['nc_count']}건) -- {item['url']}")

    return created_issues


if __name__ == "__main__":
    main()
