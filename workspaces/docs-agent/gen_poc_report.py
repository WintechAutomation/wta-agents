"""PoC 통합 HTML 리포트 생성"""
import json
from pathlib import Path

a = json.load(open('poc_analysis.json', encoding='utf-8'))
per_file = a['per_file']
ts = a['token_stats']
hist = a['token_hist']
by_lang = a['by_lang']

rows = []
for r in per_file:
    rows.append(
        '<tr>'
        f'<td><code>{r["file_id"][:25]}</code></td>'
        f'<td>{r["cat"]}</td>'
        f'<td>{r["mfr"]}</td>'
        f'<td>{r["model"]}</td>'
        f'<td>{r["dt"]}</td>'
        f'<td class="lang-{r["lang"]}">{r["lang"]}</td>'
        f'<td class="num">{r["chunks"]:,}</td>'
        f'<td class="num">{r["tok_avg"]}</td>'
        f'<td class="num">{r["tok_median"]}</td>'
        f'<td class="num">{r["fig_total_refs"]:,}</td>'
        f'<td class="num">{r["tbl_total_refs"]:,}</td>'
        f'<td class="num">{r["fig_match_rate"]}%</td>'
        f'<td class="num">{r["unique_pages"]}</td>'
        '</tr>'
    )

# Histogram bars
hist_html = ''
max_h = max(hist.values())
total_h = sum(hist.values())
for label, count in hist.items():
    pct = count / total_h * 100
    w = count / max_h * 100
    hist_html += (
        '<div class="bar-row">'
        f'<div class="bar-label">{label}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{w:.1f}%"></div></div>'
        f'<div class="bar-val">{count:,} ({pct:.1f}%)</div>'
        '</div>\n'
    )

lang_rows = ''
for lang, s in by_lang.items():
    lang_rows += f'<tr><td class="lang-{lang}">{lang}</td><td class="num">{s["n"]:,}</td><td class="num">{s["avg"]}</td><td class="num">{s["median"]}</td></tr>\n'

match_rank_rows = ''
for i, r in enumerate(sorted(per_file, key=lambda x: -x['fig_match_rate']), 1):
    match_rank_rows += (
        f'<tr><td>{i}</td><td>{r["mfr"]} {r["model"]}</td>'
        f'<td class="lang-{r["lang"]}">{r["lang"]}</td>'
        f'<td class="num">{r["chunks"]:,}</td>'
        f'<td class="num">{r["fig_match_rate"]}%</td>'
        f'<td class="num">{r["tok_avg"]}</td></tr>\n'
    )

total_chunks = a['total_chunks']
total_figs = a['total_fig_refs']
total_tbls = a['total_tbl_refs']
total_vlm = a['total_vlm']

css = """
body { font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif; max-width:1200px; margin:30px auto; padding:20px; color:#222; background:#fafafa; }
h1 { color:#4472C4; border-bottom:3px solid #4472C4; padding-bottom:8px; }
h2 { color:#4472C4; margin-top:40px; border-left:4px solid #4472C4; padding-left:10px; }
h3 { color:#2c3e50; margin-top:25px; }
table { border-collapse:collapse; width:100%; font-size:13px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.08); }
th { background:#4472C4; color:#fff; padding:8px 10px; text-align:left; }
td { padding:7px 10px; border-bottom:1px solid #e4e4e4; }
td.num { text-align:right; font-family:Consolas,monospace; }
tr:hover { background:#f0f6ff; }
code { background:#eef; padding:1px 4px; border-radius:3px; font-size:11px; }
.kpi { display:flex; gap:15px; margin:20px 0; flex-wrap:wrap; }
.kpi .card { flex:1; min-width:180px; background:#fff; padding:18px; border-radius:8px; border-left:4px solid #4472C4; box-shadow:0 1px 3px rgba(0,0,0,.08); }
.kpi .card .v { font-size:28px; font-weight:bold; color:#4472C4; }
.kpi .card .l { font-size:12px; color:#666; text-transform:uppercase; letter-spacing:.5px; }
.bar-row { display:flex; align-items:center; margin:5px 0; font-family:Consolas,monospace; font-size:13px; }
.bar-label { width:90px; text-align:right; padding-right:10px; color:#555; }
.bar-track { flex:1; height:22px; background:#eef; border-radius:3px; overflow:hidden; }
.bar-fill { height:100%; background:linear-gradient(90deg,#4472C4,#6a8ed8); }
.bar-val { width:140px; text-align:right; padding-left:10px; color:#333; }
.lang-KO { color:#c0392b; font-weight:bold; }
.lang-EN { color:#2980b9; font-weight:bold; }
.lang-JA { color:#8e44ad; font-weight:bold; }
.finding { background:#fffbe6; border-left:4px solid #f5a623; padding:12px 16px; margin:12px 0; border-radius:4px; }
.good { background:#e8f8ef; border-left:4px solid #27ae60; padding:12px 16px; margin:12px 0; border-radius:4px; }
.bad  { background:#ffeaea; border-left:4px solid #e74c3c; padding:12px 16px; margin:12px 0; border-radius:4px; }
ul { line-height:1.8; }
.meta { color:#666; font-size:12px; margin-top:-10px; }
"""

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>manuals-v2 PoC 통합 리포트 (10 files)</title>
<style>{css}</style>
</head>
<body>

<h1>manuals-v2 RAG+GraphRAG PoC — 통합 리포트 (10 files)</h1>
<p class="meta">작성: docs-agent (독스) · 날짜: 2026-04-12 · 파이프라인: Docling 2.86.0 + HierarchicalChunker 512/64 + Qwen3-Embedding-8B (2000d MRL) + Qwen2.5-VL-7B + Supabase Storage (vector 버킷)</p>

<h2>1. 핵심 KPI</h2>
<div class="kpi">
  <div class="card"><div class="v">10 / 10</div><div class="l">파일 파싱 성공</div></div>
  <div class="card"><div class="v">{total_chunks:,}</div><div class="l">DB 적재 청크</div></div>
  <div class="card"><div class="v">{total_figs:,}</div><div class="l">Figure refs (전수 VLM 포함)</div></div>
  <div class="card"><div class="v">{total_tbls:,}</div><div class="l">Table refs</div></div>
  <div class="card"><div class="v">{total_vlm:,}</div><div class="l">VLM 설명 생성</div></div>
  <div class="card"><div class="v">0</div><div class="l">VLM/업로드/적재 에러</div></div>
</div>

<p>db-manager 적재 누적: <strong>10,215 rows / 10 files / 3 categories (1_robot, 2_sensor, 5_inverter) / 5 manufacturers</strong>. HNSW self-dist 0.0 sanity check 통과, UPSERT 멱등성 검증.</p>

<h2>2. 파일별 통계</h2>
<table>
<tr><th>file_id</th><th>cat</th><th>mfr</th><th>model</th><th>doctype</th><th>lang</th><th>chunks</th><th>tok avg</th><th>tok med</th><th>fig refs</th><th>tbl refs</th><th>fig 매칭율</th><th>pages</th></tr>
{''.join(rows)}
</table>

<h2>3. 토큰 히스토그램 (전체 {total_chunks:,} chunks)</h2>
<p class="meta">통계: min={ts['min']} / max={ts['max']} / avg={ts['avg']} / median={ts['median']} / p10={ts['p10']} / p50={ts['p50']} / p90={ts['p90']}</p>
{hist_html}

<div class="bad">
<strong>발견: 청크의 88.2%가 50 토큰 미만 (0-9: 47.4%, 10-49: 40.8%)</strong><br>
중위값 10 토큰. HierarchicalChunker가 섹션 경계에서 단일 레이블/캡션을 하나의 청크로 만드는 경우가 빈발. 단독 노이즈 청크가 검색 품질을 떨어뜨릴 수 있음. 검색 시 이웃 청크 ±2 병합 또는 청킹 재설계 필요.
</div>

<h2>4. 언어별 토큰 분포</h2>
<table>
<tr><th>lang</th><th>n chunks</th><th>avg tokens</th><th>median tokens</th></tr>
{lang_rows}
</table>

<div class="bad">
<strong>CJK 과분할:</strong> EN=240.3 avg / KO=53.7 / <strong>JA=11.5</strong>. JA 파일 청크의 98.9%가 20 토큰 미만 (median 4).<br>
<strong>조치:</strong>
<ul>
<li>CJK 토크나이저 적용 (sudachi/mecab 등)</li>
<li>HierarchicalChunker → tokenizer-aware chunker 교체 검토</li>
<li>후처리: 인접 청크 자동 concat (목표 tok avg ≥ 150)</li>
</ul>
</div>

<h2>5. Figure 매칭율 순위</h2>
<p>figure_refs를 가진 청크 / 전체 청크. 페이지 경계 기반 매칭이므로 문서 레이아웃 및 청크 단편화에 민감.</p>
<table>
<tr><th>rank</th><th>파일</th><th>lang</th><th>chunks</th><th>매칭율</th><th>tok avg</th></tr>
{match_rank_rows}
</table>

<div class="finding">
<strong>인사이트</strong>
<ul>
<li><strong>Sanyo SanmotionR (79.1%, EN)</strong> — spec sheet 스타일, figure 밀도 높음 → 매칭율 최고</li>
<li><strong>BFP-A8586-D KO (30.1%, 3,927 chunks)</strong> — 과분할 영향으로 페이지당 figure가 전 청크에 붙지 못함</li>
<li><strong>BFP-A8614 JA (25.2%)</strong> — CJK 과분할 + 137 pages / 1229 chunks → 최저</li>
</ul>
</div>

<h2>6. VLM 캡션 & Storage 업로드</h2>
<div class="good">
<strong>Qwen2.5-VL-7B:</strong> 총 1,346개 figure 전수 캡션 생성 성공, 에러 0. 한국어 기술 설명 (3~5문장) 부착.<br>
<strong>Supabase Storage:</strong> 원본 1,346 + 썸네일 1,346 = 2,692 PNG 업로드 완료<br>
경로: <code>vector/manual_images/{{cat}}/{{file_id}}/page_XXXX_fig_XXX_XXX.png</code>
</div>

<h2>7. 권장 조치 (다음 단계)</h2>
<ol>
<li><strong>청킹 재설계</strong> — CJK tokenizer + 후처리 병합으로 avg 150~200 달성. <code>min_chunk_tokens=40</code> 필터 제안(db-manager 리포트 6장과 동일 결론).</li>
<li><strong>대형 테이블 분할</strong> — 파일 10 Yaskawa V1000에서 25,263 토큰 단일 청크 관찰. 표 행 단위 50 행 분할 적용.</li>
<li><strong>저품질 파일 pre-filter</strong> — <code>unique_pages &lt; 5 AND chunks &lt; 10</code> 케이스는 파싱 전 skip (파일 1 Yaskawa RS232C 같은 표지 PDF).</li>
<li><strong>Reranker</strong> — Qwen3-Reranker-4B 드래프트 완료(<code>qwen3_reranker_draft.py</code>). Ollama 기반 yes/no 파싱 → 정밀 score 필요 시 vLLM 전환.</li>
<li><strong>LightRAG GraphRAG</strong> — 엔티티/관계 추출 qwen3.5:35b-a3b 기반 PoC를 다음 단계로.</li>
<li><strong>카테고리 확장</strong> — 본 PoC로 1_robot/2_sensor/5_inverter 검증 완료. 나머지 5개 카테고리 동일 파이프라인 적용 가능.</li>
</ol>

<h2>8. 검증 쿼리 (db-manager 실행 대기)</h2>
<p>SQL: <code>workspaces/docs-agent/poc_validation_queries.sql</code></p>
<ol>
<li><strong>Q1 V1000 서보 결선도</strong> — Yaskawa + 5_inverter 필터, figure_refs 포함 확인</li>
<li><strong>Q2 에러코드 E401</strong> — 정규식 필터(<code>E\\s*401</code>), Mitsubishi 문서군 히트 기대</li>
<li><strong>Q3 Mitsubishi CR 로봇 셋업</strong> — doctype ILIKE '%setup%', figure storage_path + VLM 설명 확인</li>
<li><strong>Q4 로봇 가반중량</strong> — ProductSpec doctype, 다국어 교차(KO/EN/JA)</li>
<li><strong>Q5 CC-Link 국번 설정</strong> — BFP-A8615 히트, VLM 설명 내 '스위치/국번' 키워드 매칭</li>
</ol>
<p>부가: V1 카테고리별 분포 / V2 storage_path 누락 / V3 VLM 누락 체크.</p>

<h2>9. 산출물</h2>
<ul>
<li><code>workspaces/docs-agent/v2_poc/{{file_id}}/chunks.jsonl</code> — 파일별 청크(10건)</li>
<li><code>workspaces/docs-agent/v2_poc/{{file_id}}/document.json</code> — Docling 원본</li>
<li><code>workspaces/docs-agent/v2_poc/{{file_id}}/images/</code> — 원본 + 썸네일 PNG</li>
<li><code>workspaces/docs-agent/poc_analysis.json</code> — 통계 원본</li>
<li><code>workspaces/docs-agent/qwen3_reranker_draft.py</code> — Reranker 파싱 드래프트 (134 lines)</li>
<li><code>workspaces/docs-agent/poc_validation_queries.sql</code> — 검증 SQL 5건 + 부가 3건</li>
<li><code>workspaces/db-manager/poc_v2_ingestion_report.md</code> — db-manager 적재 리포트 (부가)</li>
</ul>

<hr>
<p class="meta">생성: gen_poc_report.py · docs-agent · (주)윈텍오토메이션 생산관리팀 (AI운영팀)</p>
</body>
</html>
"""

outdir = Path('C:/MES/wta-agents/reports/docs-agent')
outdir.mkdir(parents=True, exist_ok=True)
out = outdir / 'manuals-v2-poc-report.html'
out.write_text(html, encoding='utf-8')
print(f'written: {out}  ({len(html):,} bytes)')
