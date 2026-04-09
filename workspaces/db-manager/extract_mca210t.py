"""MCA210T 1년치 데이터 CSV 추출 스크립트"""
import urllib.request
import json
import csv
import os

FROM_DT = "2025-04-09"
TO_DT   = "2026-04-09"
OUTPUT  = r"C:\MES\wta-agents\reports\김근형\MCA210T_1year.csv"
API_BASE = "http://localhost:8100"
PAGE_SIZE = 500

# ── 1. 로그인 ──
def get_token():
    env = {}
    with open("C:/MES/backend/.env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v
    data = json.dumps({
        "username": env["MES_SERVICE_USERNAME"],
        "password": env["MES_SERVICE_PASSWORD"],
    }).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    r = urllib.request.urlopen(req, timeout=10)
    result = json.loads(r.read().decode("utf-8"))
    return result["data"]["access"]

# ── 2. 페이징 조회 (날짜 DESC — 오래된 날짜 나오면 중단) ──
def fetch_all(token):
    headers = {"Authorization": f"Bearer {token}"}
    rows = []
    page = 1
    total_pages = None
    stopped_early = False

    while True:
        url = f"{API_BASE}/api/erp/purchase/mca210t?limit={PAGE_SIZE}&page={page}"
        req = urllib.request.Request(url, headers=headers)
        r = urllib.request.urlopen(req, timeout=30)
        d = json.loads(r.read().decode("utf-8"))
        payload = d.get("data", d)
        items = payload.get("items", [])
        total = payload.get("total", 0)

        if total_pages is None and total:
            total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
            print(f"전체 {total:,}건 / 예상 {total_pages}페이지")

        if not items:
            break

        added = 0
        for item in items:
            po_dt = item.get("po_dt") or ""
            if po_dt and po_dt < FROM_DT:
                # 기준일 이전 데이터 — 이후 페이지는 모두 더 오래됨
                stopped_early = True
                break
            if po_dt <= TO_DT:
                rows.append(item)
                added += 1

        print(f"  page {page}: {added}건 추가 (누적 {len(rows):,}건)")

        if stopped_early or page == total_pages:
            break
        page += 1

    return rows

# ── 3. CSV 저장 ──
COLUMNS = [
    "po_plan_no", "po_no", "po_seq", "po_dt",
    "item_cd", "item_nm", "spec",
    "po_unit_qty", "acpt_qty", "remain_qty",
    "po_price", "po_amt", "po_unit",
    "dvry_dt", "sts", "sts_desc",
    "pjt_no", "pjt_name", "cust_name",
    "p_item_cd", "so_no", "rmk",
]

def save_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV 저장 완료: {path} ({len(rows):,}건)")

if __name__ == "__main__":
    print(f"MCA210T 1년치 추출 ({FROM_DT} ~ {TO_DT})")
    token = get_token()
    print("로그인 성공")
    rows = fetch_all(token)
    save_csv(rows, OUTPUT)
