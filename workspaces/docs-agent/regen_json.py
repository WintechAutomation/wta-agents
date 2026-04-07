# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
import openpyxl, json

wb = openpyxl.load_workbook(r'C:\MES\wta-agents\reports\중국자재변경리스트.xlsx')
ws = wb.active

rows = []
for row in ws.iter_rows(values_only=True):
    if any(c is not None for c in row):
        rows.append(list(row))

# 헤더 제거
header = rows[0]
data = rows[1:]

# 원본 그대로 모든 행 보존 (None 포함)
records = []
for r in data:
    records.append({
        "orig_code": str(r[1]).strip() if r[1] is not None else "",
        "part_name": str(r[2]).strip() if r[2] is not None else "",
        "cn_code":   str(r[3]).strip() if r[3] is not None else "",
        "qty":       str(r[4]).strip() if r[4] is not None else ""
    })

out = r'C:\MES\wta-agents\reports\중국자재변경리스트.json'
payload = {
    "generated": "2026-04-01",
    "source": "김근형 제공 (2026-04-01)",
    "count": len(records),
    "records": records
}
with open(out, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"JSON 재생성 완료: {len(records)}건")

# 검증
diffs = 0
for i, (xrow, jrec) in enumerate(zip(data, records)):
    orig = str(xrow[1] or '').strip()
    name = str(xrow[2] or '').strip()
    cn   = str(xrow[3] or '').strip()
    qty  = str(xrow[4] or '').strip()
    if (orig != jrec['orig_code'] or name != jrec['part_name'] or
        cn   != jrec['cn_code']   or qty  != jrec['qty']):
        diffs += 1
        print(f"[행{i+1}] 불일치: xlsx=({orig},{name},{cn},{qty}) json=({jrec['orig_code']},{jrec['part_name']},{jrec['cn_code']},{jrec['qty']})")

if diffs == 0:
    print("✅ 원본 xlsx와 JSON 완전 일치 확인")
else:
    print(f"⚠️ 여전히 {diffs}건 불일치")
