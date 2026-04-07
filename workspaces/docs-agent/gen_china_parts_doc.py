# -*- coding: utf-8 -*-
import openpyxl
import json
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime('%Y-%m-%d')

wb = openpyxl.load_workbook(r'C:\MES\wta-agents\reports\중국자재변경리스트.xlsx')
ws = wb.active

rows = []
for row in ws.iter_rows(values_only=True):
    if any(c is not None for c in row):
        rows.append(list(row))

# 헤더 제거 (첫 행: 품목코드, 품명, 중국산 품목코드, 수량)
header = rows[0]
data = rows[1:]

# 유효한 데이터 행만 필터 (품목코드 또는 품명 있는 행)
records = []
for r in data:
    orig_code = r[1]
    part_name = r[2]
    cn_code = r[3]
    qty = r[4]
    if part_name or orig_code:
        records.append({
            "orig_code": orig_code or "",
            "part_name": part_name or "",
            "cn_code": cn_code or "",
            "qty": qty or ""
        })

# --- HTML 문서 생성 ---
rows_html = ""
for i, rec in enumerate(records):
    bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
    rows_html += f"""
      <tr style="background:{bg}">
        <td>{i+1}</td>
        <td style="font-weight:600;color:#1a237e">{rec['orig_code']}</td>
        <td>{rec['part_name']}</td>
        <td style="font-weight:600;color:#b71c1c">{rec['cn_code']}</td>
        <td style="text-align:center">{rec['qty']}</td>
      </tr>"""

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>중국산 자재 변경 리스트 — (주)윈텍오토메이션</title>
<style>
  body {{ font-family: '맑은 고딕', 'Malgun Gothic', sans-serif; font-size: 10pt; background: #f4f6fa; margin: 0; padding: 20px; }}
  .container {{ max-width: 960px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 30px; }}
  h1 {{ font-size: 18pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 6px; }}
  .meta {{ font-size: 9pt; color: #666; margin-bottom: 20px; }}
  .summary {{ display: flex; gap: 16px; margin-bottom: 20px; }}
  .summary-card {{ background: #e8eaf6; border-radius: 6px; padding: 10px 18px; text-align: center; }}
  .summary-card .val {{ font-size: 20pt; font-weight: 700; color: #1a237e; }}
  .summary-card .lbl {{ font-size: 8pt; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
  th {{ background: #1a237e; color: #fff; padding: 8px 10px; text-align: left; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #eee; }}
  .footer {{ margin-top: 20px; font-size: 8pt; color: #999; text-align: right; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .container {{ box-shadow: none; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>중국산 자재 변경 리스트</h1>
  <div class="meta">작성일: {today} | 출처: 김근형 | 담당: docs-agent</div>
  <div class="summary">
    <div class="summary-card"><div class="val">{len(records)}</div><div class="lbl">총 항목 수</div></div>
    <div class="summary-card"><div class="val">{len(set(r['part_name'] for r in records if r['part_name']))}</div><div class="lbl">품명 종류</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th style="width:40px">No.</th>
        <th style="width:200px">기존 품목코드</th>
        <th>품명</th>
        <th style="width:240px">중국산 품목코드</th>
        <th style="width:60px">수량</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <div class="footer">생성: docs-agent | {today}</div>
</div>
</body>
</html>"""

out_html = r'C:\MES\wta-agents\reports\중국자재변경리스트.html'
with open(out_html, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML 저장 완료: {out_html}")

# --- DB 등록용 JSON 생성 ---
out_json = r'C:\MES\wta-agents\reports\중국자재변경리스트.json'
payload = {
    "generated": today,
    "source": "김근형 제공 (2026-04-01)",
    "count": len(records),
    "records": records
}
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"JSON 저장 완료: {out_json}")
print(f"총 {len(records)}건 처리 완료")
