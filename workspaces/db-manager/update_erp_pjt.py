"""
erp_data.json의 프로젝트 필드를 가장 최근 발주이력 기준으로 업데이트
[7] = last_po_dt, [8] = last_pjt_name (발주 없으면 last_plan_dt / plan_pjt_name 폴백)
"""
import json, shutil, datetime

V5_PATH = "C:/MES/wta-agents/workspaces/db-manager/erp_inventory_full_v5.json"
DATA_PATH = "C:/MES/wta-agents/reports/김근형/erp_data.json"

# v5 데이터 로드 → item_cd 기준 맵
with open(V5_PATH, encoding="utf-8") as f:
    v5 = json.load(f)

v5_items = v5.get("data", {}).get("items", [])
v5_map = {r["item_cd"]: r for r in v5_items}

# 기존 erp_data.json 로드
with open(DATA_PATH, encoding="utf-8") as f:
    erp_data = json.load(f)

updated = 0
no_po = 0
not_found = 0

for row in erp_data["data"]:
    item_cd = row[1]
    v5r = v5_map.get(item_cd)
    if not v5r:
        not_found += 1
        continue

    po_dt = v5r.get("last_po_dt")        # 최근 발주일
    pjt_name = v5r.get("last_pjt_name")  # 최근 발주 프로젝트명

    if po_dt and pjt_name:
        # 발주 이력 있는 경우 — 발주 기준으로 교체
        row[7] = po_dt
        row[8] = pjt_name
        updated += 1
    else:
        # 발주 없는 경우 — 계획 기준 폴백 (기존값 유지 또는 plan 사용)
        plan_dt = v5r.get("last_plan_dt")
        plan_pjt = v5r.get("plan_pjt_name")
        row[7] = plan_dt or row[7]
        row[8] = plan_pjt or row[8]
        no_po += 1

# 백업 후 저장
backup = DATA_PATH.replace(".json", f"_bak_{datetime.date.today()}.json")
shutil.copy2(DATA_PATH, backup)

with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(erp_data, f, ensure_ascii=False, separators=(",", ":"))

print(f"완료: 발주기준 업데이트 {updated}건, 발주없음(계획폴백) {no_po}건, v5미존재 {not_found}건")
print(f"백업: {backup}")
