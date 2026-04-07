"""
제어팀 주간업무보고서 자동 생성 스크립트
매주 월요일 07:00 KST - APScheduler에서 호출

동작:
1. 현재 주차(ISO week) 계산
2. 전주차 Confluence 페이지 조회
3. 본문 복사 + 날짜 shift (+7일)
4. 새 주차 페이지 생성
"""
import json
import base64
import http.client
import ssl
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# --- Config ---
CONFLUENCE_HOST = "iwta.atlassian.net"
SPACE_KEY = "businessreport"
PARENT_PAGE_ID = "9429581825"  # "2026년 주간 업무 보고서"
TOKEN_FILE = r"C:\MES\wta-agents\config\atlassian-api-token.txt"
EMAIL = "hjcho@wta.kr"


def log(msg: str):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    print(f"[{now}] {msg}")


def get_auth() -> str:
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()
    return base64.b64encode(f"{EMAIL}:{token}".encode()).decode()


def confluence_request(method: str, path: str, body=None):
    auth = get_auth()
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(CONFLUENCE_HOST, context=ctx)
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    conn.request(method, path, body=body_bytes, headers=headers)
    resp = conn.getresponse()
    result = resp.read().decode("utf-8")
    return resp.status, json.loads(result) if result else {}


def find_page_by_title(title: str):
    """CQL search for a page in the businessreport space."""
    import urllib.parse
    cql = urllib.parse.quote(f'space = "{SPACE_KEY}" AND title = "{title}"')
    status, data = confluence_request("GET", f"/wiki/rest/api/search?cql={cql}&limit=1")
    if status == 200 and data.get("results"):
        return data["results"][0]["content"]["id"]
    return None


def get_page_body_adf(page_id: str):
    """Get ADF body of a page via v2 API."""
    status, data = confluence_request(
        "GET",
        f"/wiki/api/v2/pages/{page_id}?body-format=atlas_doc_format",
    )
    if status == 200:
        body_str = data.get("body", {}).get("atlas_doc_format", {}).get("value", "")
        return json.loads(body_str) if body_str else None
    # Fallback: v1 API
    status, data = confluence_request(
        "GET",
        f"/wiki/rest/api/content/{page_id}?expand=body.atlas_doc_format",
    )
    if status == 200:
        body_str = data.get("body", {}).get("atlas_doc_format", {}).get("value", "")
        return json.loads(body_str) if body_str else None
    return None


def shift_dates(body_json: dict, prev_friday: str, new_friday: str,
                prev_prev_friday: str, prev_friday_for_new: str) -> dict:
    """Replace dates in ADF body.
    prev_prev_friday (old '지난주') -> prev_friday_for_new (new '지난주')
    prev_friday (old '금주') -> new_friday (new '금주')
    Order matters to avoid double-replacement.
    """
    body_str = json.dumps(body_json, ensure_ascii=False)
    # Replace old '금주' -> new '금주' first
    body_str = body_str.replace(prev_friday, new_friday)
    # Replace old '지난주' -> new '지난주'
    body_str = body_str.replace(prev_prev_friday, prev_friday_for_new)
    return json.loads(body_str)


def create_page(title: str, body_adf: dict) -> tuple:
    """Create a new page under the parent."""
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": SPACE_KEY},
        "ancestors": [{"id": PARENT_PAGE_ID}],
        "status": "current",
        "body": {
            "atlas_doc_format": {
                "value": json.dumps(body_adf, ensure_ascii=False),
                "representation": "atlas_doc_format",
            }
        },
    }
    status, data = confluence_request("POST", "/wiki/rest/api/content", payload)
    if status in (200, 201):
        page_id = data.get("id", "")
        links = data.get("_links", {})
        url = links.get("base", "") + links.get("webui", "")
        return True, page_id, url
    return False, None, json.dumps(data, ensure_ascii=False)[:300]


def get_friday_of_week(year: int, week: int) -> datetime:
    """Get the Friday date of a given ISO week."""
    # ISO week 1 day 1 (Monday)
    jan4 = datetime(year, 1, 4, tzinfo=KST)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    monday = start_of_week1 + timedelta(weeks=week - 1)
    friday = monday + timedelta(days=4)
    return friday


def main():
    now = datetime.now(KST)
    current_week = now.isocalendar()[1]
    current_year = now.isocalendar()[0]

    prev_week = current_week - 1
    prev_year = current_year
    if prev_week < 1:
        prev_year -= 1
        prev_week = datetime(prev_year, 12, 28, tzinfo=KST).isocalendar()[1]

    log(f"Current: {current_year}Y {current_week}W / Previous: {prev_year}Y {prev_week}W")

    # 1. Find previous week page
    prev_title = f"[제어팀] {prev_year}년 {prev_week}주차 주간 업무 보고"
    log(f"Searching: {prev_title}")
    prev_page_id = find_page_by_title(prev_title)
    if not prev_page_id:
        log(f"[ERROR] Previous week page not found: {prev_title}")
        sys.exit(1)
    log(f"Found previous page: {prev_page_id}")

    # 2. Check if current week page already exists
    new_title = f"[제어팀] {current_year}년 {current_week}주차 주간 업무 보고"
    existing = find_page_by_title(new_title)
    if existing:
        log(f"[SKIP] Page already exists: {new_title} (ID: {existing})")
        sys.exit(0)

    # 3. Get body
    body = get_page_body_adf(prev_page_id)
    if not body:
        log("[ERROR] Failed to get page body")
        sys.exit(1)
    log("Got previous page body")

    # 4. Calculate dates
    # Previous week: '지난주' = friday of (prev_week - 1), '금주' = friday of prev_week
    # Current week: '지난주' = friday of prev_week, '금주' = friday of current_week
    friday_prev_prev = get_friday_of_week(prev_year, prev_week - 1 if prev_week > 1 else 52)
    friday_prev = get_friday_of_week(prev_year, prev_week)
    friday_current = get_friday_of_week(current_year, current_week)

    old_prev = friday_prev_prev.strftime("%m/%d")
    old_curr = friday_prev.strftime("%m/%d")
    new_prev = friday_prev.strftime("%m/%d")
    new_curr = friday_current.strftime("%m/%d")

    log(f"Date shift: prev {old_prev}->{new_prev}, curr {old_curr}->{new_curr}")

    # 5. Shift dates (order: old_curr -> new_curr first, then old_prev -> new_prev)
    body_str = json.dumps(body, ensure_ascii=False)
    body_str = body_str.replace(old_curr, new_curr)
    body_str = body_str.replace(old_prev, new_prev)
    body = json.loads(body_str)
    log("Dates shifted")

    # 6. Create new page
    success, page_id, url = create_page(new_title, body)
    if success:
        log(f"[OK] Created: {new_title} (ID: {page_id})")
        log(f"URL: {url}")
    else:
        log(f"[ERROR] Failed to create page: {url}")
        sys.exit(1)


if __name__ == "__main__":
    main()
