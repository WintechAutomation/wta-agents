"""PoC 10건 통합 분석 — 토큰 히스토그램, lang×cat 교차, figure 매칭율 등"""
import json, os, statistics
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path('C:/MES/wta-agents/workspaces/docs-agent/v2_poc')

# file_id → metadata
FILES = {
    '1_robot_2d70fa79608e': ('Yaskawa', 'RS232C', 'ParameterManual', 'KO', '1_robot'),
    '1_robot_2d77a92d4066': ('Mitsubishi', 'BFP-A8662', 'Troubleshooting', 'EN', '1_robot'),
    '1_robot_3c1dcc39da41': ('Mitsubishi', 'BFP-A8615', 'CCLinkInterface', 'KO', '1_robot'),
    '1_robot_c7fe37c1ed98': ('Mitsubishi', 'BFP-A8601-D', 'SetupGuide', 'KO', '1_robot'),
    '1_robot_54fdb56329f0': ('ABB', 'IRB360', 'ProductSpec', 'EN', '1_robot'),
    '1_robot_0b0c3108c6c9': ('Sanyo', 'SanmotionR', 'ProductSpec', 'EN', '1_robot'),
    '1_robot_c5a220711bc5': ('Mitsubishi', 'BFP-A8614', 'TrackingManual', 'JA', '1_robot'),
    '2_sensor_2e6136a51564': ('Cognex', 'IS5000', 'QuickStart', 'KO', '2_sensor'),
    '1_robot_314928a33268': ('Mitsubishi', 'BFP-A8586-D', 'MaintenanceManual', 'KO', '1_robot'),
    '5_inverter_c6f52f93cca5': ('Yaskawa', 'V1000', 'TechnicalManual', 'KO', '5_inverter'),
}

per_file = []
all_tokens = []
all_fig_match = []
by_lang = defaultdict(list)  # lang -> [tokens...]

for fid, (mfr, model, dt, lang, cat) in FILES.items():
    jsonl = BASE / fid / 'chunks.jsonl'
    if not jsonl.exists():
        print(f'MISS {fid}'); continue
    chunks = [json.loads(l) for l in open(jsonl, encoding='utf-8')]
    toks = [c.get('tokens') or len((c.get('content') or '').split()) for c in chunks]
    with_fig = sum(1 for c in chunks if c.get('figure_refs'))
    with_tbl = sum(1 for c in chunks if c.get('table_refs'))
    vlm_populated = sum(1 for c in chunks for f in (c.get('figure_refs') or []) if f.get('vlm_description'))
    fig_total = sum(len(c.get('figure_refs') or []) for c in chunks)
    tbl_total = sum(len(c.get('table_refs') or []) for c in chunks)
    unique_pages = set()
    for c in chunks:
        ps, pe = c.get('page_start'), c.get('page_end')
        if ps and pe:
            for p in range(ps, pe+1): unique_pages.add(p)
    row = {
        'file_id': fid, 'mfr': mfr, 'model': model, 'dt': dt, 'lang': lang, 'cat': cat,
        'chunks': len(chunks),
        'tok_min': min(toks), 'tok_max': max(toks),
        'tok_avg': round(statistics.mean(toks), 1),
        'tok_median': statistics.median(toks),
        'tok_p90': round(statistics.quantiles(toks, n=10)[-1], 1) if len(toks) >= 10 else max(toks),
        'fig_ref_chunks': with_fig,
        'fig_match_rate': round(with_fig / len(chunks) * 100, 1),
        'tbl_ref_chunks': with_tbl,
        'vlm_populated': vlm_populated,
        'fig_total_refs': fig_total,
        'tbl_total_refs': tbl_total,
        'unique_pages': len(unique_pages),
    }
    per_file.append(row)
    all_tokens.extend(toks)
    all_fig_match.append(row['fig_match_rate'])
    by_lang[lang].extend(toks)

# 전체 집계
print('=' * 90)
print('PoC 통합 통계 (10 files)')
print('=' * 90)
print(f'총 chunks: {sum(r["chunks"] for r in per_file):,}')
print(f'총 figure refs: {sum(r["fig_total_refs"] for r in per_file):,}')
print(f'총 table refs: {sum(r["tbl_total_refs"] for r in per_file):,}')
print(f'총 VLM populated: {sum(r["vlm_populated"] for r in per_file):,}')
print()
print(f'토큰 (전체 {len(all_tokens)} chunks):')
print(f'  min={min(all_tokens)}  max={max(all_tokens)}  avg={statistics.mean(all_tokens):.1f}  median={statistics.median(all_tokens)}')
qs = statistics.quantiles(all_tokens, n=10)
print(f'  p10={qs[0]:.0f}  p50={qs[4]:.0f}  p90={qs[-1]:.0f}')
# 히스토그램 bins
bins = [0, 10, 50, 100, 200, 300, 500, 1000, 99999]
labels = ['0-9', '10-49', '50-99', '100-199', '200-299', '300-499', '500-999', '1000+']
hist = [0]*len(labels)
for t in all_tokens:
    for i in range(len(bins)-1):
        if bins[i] <= t < bins[i+1]:
            hist[i] += 1; break
print('\n  히스토그램:')
for l, h in zip(labels, hist):
    pct = h/len(all_tokens)*100
    bar = '█' * int(pct/2)
    print(f'    {l:>10}: {h:>5} ({pct:5.1f}%) {bar}')

print()
print('언어별 토큰 평균:')
for lang, toks in sorted(by_lang.items()):
    print(f'  {lang}: n={len(toks):>5}  avg={statistics.mean(toks):6.1f}  median={statistics.median(toks):6.0f}  p90={statistics.quantiles(toks,n=10)[-1]:6.0f}')

print()
print('파일별 figure 매칭율:')
for r in sorted(per_file, key=lambda x: -x['fig_match_rate']):
    print(f'  {r["lang"]} {r["mfr"]:10} {r["model"]:15} {r["chunks"]:>5}ch  match={r["fig_match_rate"]:5.1f}%  tok_avg={r["tok_avg"]:6.1f}')

# JSON 저장
with open('poc_analysis.json', 'w', encoding='utf-8') as f:
    json.dump({
        'per_file': per_file,
        'total_chunks': sum(r['chunks'] for r in per_file),
        'total_fig_refs': sum(r['fig_total_refs'] for r in per_file),
        'total_tbl_refs': sum(r['tbl_total_refs'] for r in per_file),
        'total_vlm': sum(r['vlm_populated'] for r in per_file),
        'token_hist': dict(zip(labels, hist)),
        'token_stats': {
            'min': min(all_tokens), 'max': max(all_tokens),
            'avg': round(statistics.mean(all_tokens),1),
            'median': statistics.median(all_tokens),
            'p10': round(qs[0],1), 'p50': round(qs[4],1), 'p90': round(qs[-1],1),
        },
        'by_lang': {l: {'n': len(v), 'avg': round(statistics.mean(v),1), 'median': statistics.median(v)} for l,v in by_lang.items()},
    }, f, ensure_ascii=False, indent=2)
print('\n→ poc_analysis.json 저장')
