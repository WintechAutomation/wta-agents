# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
import openpyxl, json

# 원본 xlsx 읽기
wb = openpyxl.load_workbook(r'C:\MES\wta-agents\reports\중국자재변경리스트.xlsx')
ws = wb.active
xlsx_rows = []
for row in ws.iter_rows(values_only=True):
    if any(c is not None for c in row):
        xlsx_rows.append(list(row))

# 헤더 제거
xlsx_data = xlsx_rows[1:]  # [None, orig_code, part_name, cn_code, qty]

# JSON 읽기
with open(r'C:\MES\wta-agents\reports\중국자재변경리스트.json', 'r', encoding='utf-8') as f:
    json_data = json.load(f)['records']

print(f"원본 xlsx 데이터 행 수: {len(xlsx_data)}")
print(f"JSON 레코드 수: {len(json_data)}")
print()

diffs = []
json_idx = 0
for i, xrow in enumerate(xlsx_data):
    orig = str(xrow[1] or '').strip()
    name = str(xrow[2] or '').strip()
    cn   = str(xrow[3] or '').strip()
    qty  = str(xrow[4] or '').strip()

    if json_idx >= len(json_data):
        diffs.append(f"[xlsx#{i+1}] JSON에 없음: orig={orig}, name={name}")
        continue

    jrec = json_data[json_idx]
    j_orig = str(jrec.get('orig_code','')).strip()
    j_name = str(jrec.get('part_name','')).strip()
    j_cn   = str(jrec.get('cn_code','')).strip()
    j_qty  = str(jrec.get('qty','')).strip()

    row_diffs = []
    if orig != j_orig:  row_diffs.append(f"orig_code: '{orig}' → '{j_orig}'")
    if name != j_name:  row_diffs.append(f"part_name: '{name}' → '{j_name}'")
    if cn   != j_cn:    row_diffs.append(f"cn_code: '{cn}' → '{j_cn}'")
    if qty  != j_qty:   row_diffs.append(f"qty: '{qty}' → '{j_qty}'")

    if row_diffs:
        diffs.append(f"[행 {i+1}] {'; '.join(row_diffs)}")

    json_idx += 1

if json_idx < len(json_data):
    for j in range(json_idx, len(json_data)):
        jrec = json_data[j]
        diffs.append(f"[JSON 추가분#{j+1}] {jrec}")

if not diffs:
    print("✅ 원본 xlsx와 JSON 데이터가 완전히 일치합니다.")
else:
    print(f"⚠️ 차이 발견: {len(diffs)}건")
    for d in diffs[:30]:
        print(d)
    if len(diffs) > 30:
        print(f"... 이하 {len(diffs)-30}건 생략")
