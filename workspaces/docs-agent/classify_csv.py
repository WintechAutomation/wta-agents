"""부품판매관리 / 판매자재관리 CSV를 분류 정리하여 HTML 보고서 생성"""
import csv
import io
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST).strftime("%Y-%m-%d")

REPORTS_DIR = r"C:\MES\wta-agents\reports\김근형"
SRC1 = r"C:\MES\wta-agents\reports\20260414.csv"
SRC2 = r"C:\MES\wta-agents\reports\20260414_1.csv"

# --- 1. 부품판매관리: 장비별 + 판매형번별 ---
def parse_csv_multiline(path):
    """멀티라인 CSV 파싱"""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
        return rows

def build_parts_report(rows):
    """부품판매관리 → 장비별, 판매형번별 분류"""
    # 장비별 분류
    by_equip = defaultdict(list)
    # 판매형번별 분류
    by_code = defaultdict(list)

    for r in rows:
        equip = (r.get("장비모델구분") or "").strip()
        if not equip:
            equip = "(미분류)"
        code = (r.get("판매형번") or "").strip()
        if not code:
            code = "(미등록)"

        by_equip[equip].append(r)
        by_code[code].append(r)

    return by_equip, by_code

def fmt_price(val):
    """가격 포맷"""
    val = (val or "").strip()
    if not val:
        return "-"
    try:
        return f"{int(float(val)):,}"
    except ValueError:
        return val

def parts_html(by_equip, by_code, total):
    """부품판매관리 HTML 생성"""
    html = []
    html.append(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>부품판매관리 분류 정리 — {NOW}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'맑은 고딕','Malgun Gothic',sans-serif; background:#f5f5f5; color:#333; padding:20px; }}
  .container {{ max-width:1200px; margin:0 auto; }}
  h1 {{ color:#CC0000; font-size:24px; margin-bottom:6px; }}
  .subtitle {{ color:#888; font-size:14px; margin-bottom:20px; }}
  .summary {{ background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:16px 20px; margin-bottom:24px; display:flex; gap:30px; flex-wrap:wrap; }}
  .summary-item {{ text-align:center; }}
  .summary-item .num {{ font-size:28px; font-weight:bold; color:#CC0000; }}
  .summary-item .label {{ font-size:13px; color:#888; }}
  .section {{ margin-bottom:28px; }}
  .section-title {{ font-size:18px; font-weight:bold; color:#222; border-left:4px solid #CC0000; padding-left:10px; margin-bottom:12px; cursor:pointer; }}
  .section-title:hover {{ color:#CC0000; }}
  .badge {{ display:inline-block; background:#CC0000; color:#fff; font-size:12px; padding:2px 8px; border-radius:10px; margin-left:6px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:6px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); margin-bottom:8px; }}
  th {{ background:#f8f8f8; border-bottom:2px solid #CC0000; padding:8px 10px; text-align:left; font-size:13px; color:#555; white-space:nowrap; }}
  td {{ padding:7px 10px; border-bottom:1px solid #eee; font-size:13px; }}
  tr:hover td {{ background:#fafafa; }}
  .tab-nav {{ display:flex; gap:4px; margin-bottom:16px; }}
  .tab-btn {{ padding:8px 20px; border:1px solid #ddd; background:#fff; cursor:pointer; font-size:14px; border-radius:6px 6px 0 0; }}
  .tab-btn.active {{ background:#CC0000; color:#fff; border-color:#CC0000; }}
  .tab-content {{ display:none; }}
  .tab-content.active {{ display:block; }}
  .footer {{ text-align:center; color:#aaa; font-size:12px; margin-top:30px; }}
</style>
</head>
<body>
<div class="container">
  <h1>부품판매관리 분류 정리</h1>
  <div class="subtitle">(주)윈텍오토메이션 · 생산관리팀 · {NOW} · 총 {total}건</div>

  <div class="summary">
    <div class="summary-item"><div class="num">{total}</div><div class="label">전체 부품</div></div>
    <div class="summary-item"><div class="num">{len(by_equip)}</div><div class="label">장비 유형</div></div>
    <div class="summary-item"><div class="num">{len(by_code)}</div><div class="label">판매형번</div></div>
  </div>

  <div class="tab-nav">
    <div class="tab-btn active" onclick="showTab('equip')">장비별 분류</div>
    <div class="tab-btn" onclick="showTab('code')">판매형번별 분류</div>
  </div>

  <div id="tab-equip" class="tab-content active">
""")

    # 장비별
    for equip in sorted(by_equip.keys()):
        items = by_equip[equip]
        html.append(f'    <div class="section"><div class="section-title">{equip} <span class="badge">{len(items)}건</span></div>')
        html.append('    <table><tr><th>ID</th><th>상태</th><th>ERP코드</th><th>품명</th><th>판매형번</th><th>단가</th><th>제조사</th></tr>')
        for r in items:
            html.append(f'    <tr><td>{r.get("*ID","")}</td><td>{r.get("상태","")}</td><td>{r.get("ERP 품목코드","")}</td><td>{r.get("품명","")}</td><td>{r.get("판매형번","")}</td><td style="text-align:right">{fmt_price(r.get("단가",""))}</td><td>{r.get("제조사","")}</td></tr>')
        html.append('    </table></div>')

    html.append('  </div>')

    # 판매형번별
    html.append('  <div id="tab-code" class="tab-content">')
    for code in sorted(by_code.keys()):
        items = by_code[code]
        html.append(f'    <div class="section"><div class="section-title">{code} <span class="badge">{len(items)}건</span></div>')
        html.append('    <table><tr><th>ID</th><th>상태</th><th>ERP코드</th><th>품명</th><th>단가</th><th>장비구분</th><th>제조사</th></tr>')
        for r in items:
            html.append(f'    <tr><td>{r.get("*ID","")}</td><td>{r.get("상태","")}</td><td>{r.get("ERP 품목코드","")}</td><td>{r.get("품명","")}</td><td style="text-align:right">{fmt_price(r.get("단가",""))}</td><td>{r.get("장비모델구분","")}</td><td>{r.get("제조사","")}</td></tr>')
        html.append('    </table></div>')

    html.append("""  </div>
  <div class="footer">(주)윈텍오토메이션 생산관리팀 (AI운영팀) · CONFIDENTIAL</div>
</div>
<script>
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(e => e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e => e.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}
</script>
</body></html>""")
    return "\n".join(html)


# --- 2. 판매자재관리: 판매형번별 분류 ---
def parse_sales_csv(path):
    """판매자재관리 CSV — 멀티행 프로젝트 병합"""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 프로젝트 병합 (ID가 빈 행은 이전 프로젝트의 부품 리스트 연장)
    projects = []
    current = None
    for r in rows:
        rid = (r.get("*ID") or "").strip()
        if rid:
            current = {
                "id": rid,
                "상태": r.get("상태", ""),
                "프로젝트": r.get("ERP 판매프로젝트 이름", ""),
                "고객사": r.get("고객사", "") or r.get("고객사명", ""),
                "국가": r.get("국가(연동)", ""),
                "장비명": r.get("장비명", ""),
                "영업담당자": r.get("영업담당자", ""),
                "납기요청일": r.get("납기요청일", ""),
                "판매형번": (r.get("판매형번") or "").strip(),
                "부품명": r.get("부품명", ""),
                "단가": r.get("단가", ""),
                "부품리스트": [],
            }
            projects.append(current)

        # 부품 리스트 행
        pno = (r.get("판매 부품 리스트-No.") or "").strip()
        pname = (r.get("판매 부품 리스트-부품명") or "").strip()
        pcode = (r.get("판매 부품 리스트-판매코드명") or "").strip()
        pqty = (r.get("판매 부품 리스트-수량") or "").strip()
        pprice = (r.get("판매 부품 리스트-단가") or "").strip()
        pmfr = (r.get("판매 부품 리스트-제조사") or "").strip()
        premark = (r.get("판매 부품 리스트-비고") or "").strip()
        if current and (pname or pcode):
            current["부품리스트"].append({
                "no": pno, "부품명": pname, "코드": pcode,
                "수량": pqty, "단가": pprice, "제조사": pmfr, "비고": premark
            })

    return projects

def build_sales_by_code(projects):
    """판매자재관리 판매형번별 분류"""
    by_code = defaultdict(list)

    # 프로젝트 단위 + 부품리스트 내 코드 모두 수집
    for p in projects:
        # 프로젝트 자체 판매형번
        code = p["판매형번"] or "(미등록)"
        by_code[code].append(p)

        # 부품리스트 내 코드별로도 추가 인덱싱
        for part in p["부품리스트"]:
            pc = part["코드"]
            if pc and pc != code:
                if p not in by_code.get(pc, []):
                    by_code[pc].append(p)

    return by_code

def sales_html(projects, by_code):
    """판매자재관리 HTML"""
    # 상태별 집계
    status_cnt = defaultdict(int)
    for p in projects:
        s = p["상태"] or "(없음)"
        status_cnt[s] += 1

    html = []
    html.append(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>판매자재관리 분류 정리 — {NOW}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'맑은 고딕','Malgun Gothic',sans-serif; background:#f5f5f5; color:#333; padding:20px; }}
  .container {{ max-width:1300px; margin:0 auto; }}
  h1 {{ color:#CC0000; font-size:24px; margin-bottom:6px; }}
  .subtitle {{ color:#888; font-size:14px; margin-bottom:20px; }}
  .summary {{ background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:16px 20px; margin-bottom:24px; display:flex; gap:30px; flex-wrap:wrap; }}
  .summary-item {{ text-align:center; }}
  .summary-item .num {{ font-size:28px; font-weight:bold; color:#CC0000; }}
  .summary-item .label {{ font-size:13px; color:#888; }}
  .status-bar {{ display:flex; gap:8px; margin-bottom:20px; flex-wrap:wrap; }}
  .status-chip {{ padding:4px 12px; border-radius:12px; font-size:12px; background:#eee; }}
  .status-chip.판매접수 {{ background:#FFF3E0; color:#E65100; }}
  .status-chip.부품준비 {{ background:#E3F2FD; color:#1565C0; }}
  .status-chip.판매완료 {{ background:#E8F5E9; color:#2E7D32; }}
  .status-chip.견적 {{ background:#F3E5F5; color:#7B1FA2; }}
  .section {{ margin-bottom:24px; }}
  .section-title {{ font-size:17px; font-weight:bold; color:#222; border-left:4px solid #CC0000; padding-left:10px; margin-bottom:10px; }}
  .badge {{ display:inline-block; background:#CC0000; color:#fff; font-size:12px; padding:2px 8px; border-radius:10px; margin-left:6px; }}
  .project-card {{ background:#fff; border:1px solid #e0e0e0; border-radius:6px; padding:12px 16px; margin-bottom:10px; }}
  .project-header {{ display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:8px; }}
  .project-title {{ font-weight:bold; font-size:14px; }}
  .project-meta {{ font-size:12px; color:#888; }}
  .project-meta span {{ margin-right:12px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
  th {{ background:#f8f8f8; border-bottom:2px solid #CC0000; padding:6px 8px; text-align:left; font-size:12px; color:#555; white-space:nowrap; }}
  td {{ padding:5px 8px; border-bottom:1px solid #eee; font-size:12px; }}
  .search-box {{ margin-bottom:16px; }}
  .search-box input {{ padding:8px 14px; border:1px solid #ddd; border-radius:6px; width:300px; font-size:14px; }}
  .footer {{ text-align:center; color:#aaa; font-size:12px; margin-top:30px; }}
  .hidden {{ display:none; }}
</style>
</head>
<body>
<div class="container">
  <h1>판매자재관리 — 판매형번별 분류</h1>
  <div class="subtitle">(주)윈텍오토메이션 · 생산관리팀 · {NOW} · 프로젝트 {len(projects)}건 · 판매형번 {len(by_code)}종</div>

  <div class="summary">
    <div class="summary-item"><div class="num">{len(projects)}</div><div class="label">판매 프로젝트</div></div>
    <div class="summary-item"><div class="num">{len(by_code)}</div><div class="label">판매형번</div></div>
    <div class="summary-item"><div class="num">{sum(len(p["부품리스트"]) for p in projects)}</div><div class="label">부품 항목</div></div>
  </div>

  <div class="status-bar">
""")
    for s, cnt in sorted(status_cnt.items(), key=lambda x: -x[1]):
        html.append(f'    <div class="status-chip {s}">{s}: {cnt}건</div>')

    html.append("""  </div>
  <div class="search-box"><input type="text" id="searchInput" placeholder="판매형번 또는 부품명 검색..." oninput="filterSections()"></div>
""")

    for code in sorted(by_code.keys()):
        plist = by_code[code]
        html.append(f'  <div class="section code-section" data-code="{code}">')
        html.append(f'    <div class="section-title">{code} <span class="badge">{len(plist)}건</span></div>')

        for p in plist:
            status_cls = p["상태"].replace(" ", "")
            customer = p["고객사"] or "-"
            html.append(f'    <div class="project-card">')
            html.append(f'      <div class="project-header"><div class="project-title">[{p["id"]}] {p["프로젝트"] or "-"}</div><div class="status-chip {status_cls}">{p["상태"] or "-"}</div></div>')
            html.append(f'      <div class="project-meta"><span>고객사: {customer}</span><span>국가: {p["국가"] or "-"}</span><span>담당: {p["영업담당자"] or "-"}</span><span>납기: {p["납기요청일"] or "-"}</span></div>')

            if p["부품리스트"]:
                html.append('      <table><tr><th>No</th><th>부품명</th><th>판매코드</th><th>수량</th><th>단가</th><th>제조사</th><th>비고</th></tr>')
                for part in p["부품리스트"]:
                    html.append(f'      <tr><td>{part["no"]}</td><td>{part["부품명"]}</td><td>{part["코드"]}</td><td style="text-align:right">{part["수량"]}</td><td style="text-align:right">{fmt_price(part["단가"])}</td><td>{part["제조사"]}</td><td>{part["비고"]}</td></tr>')
                html.append('      </table>')
            html.append('    </div>')

        html.append('  </div>')

    html.append("""
  <div class="footer">(주)윈텍오토메이션 생산관리팀 (AI운영팀) · CONFIDENTIAL</div>
</div>
<script>
function filterSections() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  document.querySelectorAll('.code-section').forEach(sec => {
    const code = sec.getAttribute('data-code').toLowerCase();
    const text = sec.textContent.toLowerCase();
    sec.classList.toggle('hidden', q && !code.includes(q) && !text.includes(q));
  });
}
</script>
</body></html>""")
    return "\n".join(html)


# --- main ---
if __name__ == "__main__":
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # 1) 부품판매관리
    rows1 = parse_csv_multiline(SRC1)
    by_equip, by_code1 = build_parts_report(rows1)
    html1 = parts_html(by_equip, by_code1, len(rows1))
    out1 = os.path.join(REPORTS_DIR, "부품판매관리_분류_20260414.html")
    with open(out1, "w", encoding="utf-8") as f:
        f.write(html1)
    print(f"[1] 부품판매관리: {len(rows1)}건 → 장비 {len(by_equip)}종, 형번 {len(by_code1)}종")
    print(f"    장비별: {', '.join(f'{k}({len(v)})' for k,v in sorted(by_equip.items()))}")
    print(f"    저장: {out1}")

    # 2) 판매자재관리
    projects = parse_sales_csv(SRC2)
    by_code2 = build_sales_by_code(projects)
    html2 = sales_html(projects, by_code2)
    out2 = os.path.join(REPORTS_DIR, "판매자재관리_형번별_20260414.html")
    with open(out2, "w", encoding="utf-8") as f:
        f.write(html2)
    print(f"\n[2] 판매자재관리: 프로젝트 {len(projects)}건 → 형번 {len(by_code2)}종")
    print(f"    저장: {out2}")
