# -*- coding: utf-8 -*-
"""
pvd_images_named/ 파일과 HTML caption 매칭 현황을 시각 리포트로 생성
각 이미지 썸네일 + 파일명 + HTML caption 표시
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os, re, base64

IMG_DIR  = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'
OUT_HTML = r'C:\MES\wta-agents\reports\pvd_이미지_매칭_확인.html'

def img_to_b64(fpath):
    with open(fpath, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    ext = fpath.rsplit('.',1)[-1].lower()
    mime = 'image/jpeg' if ext in ('jpg','jpeg') else 'image/png'
    return f'data:{mime};base64,{data}'

# 파일 목록 파싱 (순번 순서대로)
entries = []
for fname in sorted(os.listdir(IMG_DIR)):
    m = re.match(r'^(\d{3})_(.+)\.(jpeg|jpg|png)$', fname, re.I)
    if m:
        seq = int(m.group(1))
        cap = m.group(2).replace('_', ' ')
        fpath = os.path.join(IMG_DIR, fname)
        kb = round(os.path.getsize(fpath) / 1024)
        entries.append((seq, cap, fname, fpath, kb))

# HTML 생성
cards = ''
for seq, cap, fname, fpath, kb in entries:
    b64 = img_to_b64(fpath)
    cards += f'''
    <div class="card">
      <div class="seq">{seq:03d}</div>
      <img src="{b64}" alt="{cap}">
      <div class="cap">{cap}</div>
      <div class="fname">{fname}</div>
      <div class="size">{kb} KB</div>
    </div>'''

html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>PVD 이미지 매칭 확인</title>
<style>
  body {{ font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; }}
  h1 {{ font-size: 14pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }}
  .summary {{ color: #555; font-size: 10pt; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 160px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #aaa; margin-bottom: 4px; }}
  .cap {{ font-size: 10pt; font-weight: 700; color: #1a237e; margin-top: 8px; }}
  .fname {{ font-size: 8pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .size {{ font-size: 8pt; color: #bbb; margin-top: 2px; }}
</style>
</head>
<body>
<h1>PVD Unloading 매뉴얼 — 이미지 매칭 확인</h1>
<div class="summary">총 {len(entries)}개 파일 | pvd_images_named/ | 파일명 = HTML figure-caption 기준</div>
<div class="grid">{cards}
</div>
</body>
</html>'''

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

size_kb = round(os.path.getsize(OUT_HTML) / 1024)
print(f"저장 완료: {OUT_HTML} ({size_kb}KB)")
print(f"총 {len(entries)}개 이미지 카드 생성")
