# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from docx import Document
from bs4 import BeautifulSoup
import os, re, zipfile

DOCX_PATH  = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\PVD_Unloading_Manual_Revised_20220328.docx'
HTML_PATH  = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
IMG_DIR    = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images'
OUT_HTML   = r'C:\MES\wta-agents\reports\pvd_이미지_목록.html'
OUT_MD     = r'C:\MES\wta-agents\reports\pvd_이미지_목록.md'

# ── 1. docx 이미지 등장 순서 추출 (컨텍스트 포함) ─────────────
doc = Document(DOCX_PATH)
body = doc.element.body
paras = list(body.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))

img_list = []  # [(seq, fname, ctx_text), ...]
seen_rids = set()
text_window = []

for p in paras:
    t = ''.join(x.text or '' for x in
                p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')).strip()
    if t:
        text_window = (text_window + [t])[-2:]

    blips = p.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
    for blip in blips:
        rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        if not rId or rId in seen_rids:
            continue
        seen_rids.add(rId)
        rel = doc.part.rels.get(rId)
        fname = os.path.basename(rel.target_ref) if rel else '?'
        ctx = ' / '.join(text_window) if text_window else ''
        img_list.append((len(img_list)+1, fname, ctx))

# ── 2. HTML caption 목록 추출 ─────────────────────────────────
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()
soup = BeautifulSoup(html, 'html.parser')
captions = [c.get_text(strip=True) for c in soup.find_all('div', class_='figure-caption')]

# offset 계산 (docx 이미지 수 - caption 수)
offset = len(img_list) - len(captions)

# caption 매핑
caption_map = {}  # fname -> caption
for i, cap in enumerate(captions):
    idx = offset + i
    if 0 <= idx < len(img_list):
        caption_map[img_list[idx][1]] = cap

# ── 3. 파일 크기 정보 ─────────────────────────────────────────
def fsize(fname):
    p = os.path.join(IMG_DIR, fname)
    if os.path.exists(p):
        return round(os.path.getsize(p) / 1024)
    return 0

# ── 4. HTML 보고서 생성 ───────────────────────────────────────
rows_html = ''
for seq, fname, ctx in img_list:
    caption = caption_map.get(fname, '')
    named = f"{list(captions).index(caption)+1:03d}_{re.sub(r'[ /]', '_', caption)}" if caption else ''
    ext = fname.rsplit('.',1)[-1].lower()
    kb = fsize(fname)
    tag_color = '#e8f5e9' if caption else '#fff8e1'
    caption_cell = f'<span style="color:#1b5e20;font-weight:600">{caption}</span>' if caption else '<span style="color:#aaa">—</span>'
    named_cell = f'<code style="font-size:8pt">{named}.{ext}</code>' if named else '<span style="color:#aaa">원본명 유지</span>'
    rows_html += f'''
      <tr style="background:{tag_color}">
        <td style="text-align:center">{seq}</td>
        <td><code>{fname}</code></td>
        <td style="text-align:right;color:#666">{kb}KB</td>
        <td>{caption_cell}</td>
        <td>{named_cell}</td>
        <td style="font-size:8pt;color:#888">{ctx[:60]}</td>
      </tr>'''

html_out = f'''<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8">
<title>PVD 매뉴얼 이미지 목록</title>
<style>
  body{{font-family:'맑은 고딕',sans-serif;font-size:9.5pt;background:#f5f5f5;padding:20px}}
  .wrap{{max-width:1200px;margin:0 auto;background:#fff;padding:24px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1)}}
  h1{{font-size:15pt;color:#1a237e;border-bottom:3px solid #1a237e;padding-bottom:8px}}
  .summary{{display:flex;gap:16px;margin:12px 0 20px}}
  .card{{background:#e8eaf6;border-radius:6px;padding:8px 16px;text-align:center}}
  .card .v{{font-size:18pt;font-weight:700;color:#1a237e}}
  .card .l{{font-size:8pt;color:#555}}
  table{{width:100%;border-collapse:collapse;font-size:8.5pt}}
  th{{background:#1a237e;color:#fff;padding:7px 8px;text-align:left}}
  td{{padding:5px 8px;border-bottom:1px solid #eee}}
  code{{background:#f0f0f0;padding:1px 4px;border-radius:3px;font-size:8pt}}
</style>
</head>
<body><div class="wrap">
<h1>PVD Unloading 매뉴얼 — 이미지 전체 목록</h1>
<div class="summary">
  <div class="card"><div class="v">{len(img_list)}</div><div class="l">전체 이미지</div></div>
  <div class="card"><div class="v">{len(captions)}</div><div class="l">캡션 매핑 완료</div></div>
  <div class="card"><div class="v">{len(img_list)-len(captions)}</div><div class="l">원본명 유지</div></div>
</div>
<table>
  <thead><tr>
    <th style="width:40px">순번</th>
    <th>원본 파일명</th>
    <th style="width:60px">크기</th>
    <th>캡션 (그림 제목)</th>
    <th>변경 파일명</th>
    <th>문서 내 컨텍스트</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<div style="margin-top:16px;font-size:8pt;color:#999">
  생성: docs-agent | 원본: PVD_Unloading_Manual_Revised_20220328.docx
</div>
</div></body></html>'''

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f"HTML 저장: {OUT_HTML}")

# ── 5. MD 보고서 생성 ─────────────────────────────────────────
md_lines = ['# PVD 매뉴얼 이미지 전체 목록\n',
            f'전체 {len(img_list)}개 | 캡션 매핑 {len(captions)}개 | 원본명 유지 {len(img_list)-len(captions)}개\n',
            '| 순번 | 원본 파일명 | 크기 | 캡션 | 변경 파일명 |',
            '|------|------------|------|------|------------|']
for seq, fname, ctx in img_list:
    caption = caption_map.get(fname, '')
    ext = fname.rsplit('.',1)[-1].lower()
    named = f"{list(captions).index(caption)+1:03d}_{re.sub(r'[ /]','_',caption)}.{ext}" if caption else '—'
    kb = fsize(fname)
    md_lines.append(f'| {seq} | `{fname}` | {kb}KB | {caption or "—"} | {named} |')

with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))
print(f"MD 저장: {OUT_MD}")
print(f"완료: 총 {len(img_list)}개 정리")
