# -*- coding: utf-8 -*-
"""
docx에서 이미지 전후 텍스트를 분석해서 어떤 방식으로 캡션이 붙는지 파악
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
import os, re, zipfile, base64

DOCX_PATH = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\PVD_Unloading_Manual_Revised_20220328.docx'
OUT_HTML  = r'C:\MES\wta-agents\reports\pvd_docx_이미지_순서_분석.html'

doc = Document(DOCX_PATH)
NS_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NS_A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def is_korean(text):
    return bool(re.search(r'[가-힣]', text))

# 모든 paragraph를 순서대로 수집 (텍스트 + 이미지 여부)
paras = list(doc.element.body.iter(f'{NS_W}p'))
items = []  # (type, content)  type: 'text' or 'image'
for p in paras:
    t = ''.join(x.text or '' for x in p.iter(f'{NS_W}t')).strip()
    blips = p.findall(f'.//{NS_A}blip')
    if blips:
        for blip in blips:
            rId = blip.get(f'{NS_R}embed')
            rel = doc.part.rels.get(rId) if rId else None
            items.append(('image', rId, rel, t))
    elif t:
        items.append(('text', t))

# 이미지 전후 각 3개 텍스트 수집
def get_context(idx, before=3, after=3):
    pre, post = [], []
    j = idx - 1
    while j >= 0 and len(pre) < before:
        if items[j][0] == 'text':
            pre.insert(0, items[j][1])
        j -= 1
    j = idx + 1
    while j < len(items) and len(post) < after:
        if items[j][0] == 'text':
            post.append(items[j][1])
        j += 1
    return pre, post

# docx zip에서 이미지 바이트 추출
def get_b64(rel, max_kb=100):
    if not rel:
        return None
    fname = os.path.basename(rel.target_ref)
    ext = fname.rsplit('.', 1)[-1].lower()
    with zipfile.ZipFile(DOCX_PATH, 'r') as z:
        target = rel.target_ref
        path = 'word/' + target if not target.startswith('word/') else target
        try:
            data = z.read(path)
        except KeyError:
            for n in z.namelist():
                if os.path.basename(n) == fname:
                    data = z.read(n)
                    break
            else:
                return None
    if len(data) > max_kb * 1024:
        return None  # 너무 큰 이미지 스킵
    mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
    b64 = base64.b64encode(data).decode('ascii')
    return f'data:{mime};base64,{b64}'

# 이미지만 필터링
image_items = [(i, item) for i, item in enumerate(items) if item[0] == 'image']
print(f"총 이미지: {len(image_items)}개")

# 한국어 컨텍스트가 있는 이미지 찾기 (앞뒤 모두 확인)
kr_images = []
for idx, (i, item) in enumerate(image_items):
    pre, post = get_context(i)
    all_text = pre + post
    has_kr = any(is_korean(t) for t in all_text)
    # "그림" 패턴 찾기
    fig_pattern = re.compile(r'그림\s*\d+[-–]\d+')
    fig_matches = [t for t in all_text if fig_pattern.search(t)]
    if has_kr or fig_matches:
        kr_images.append((idx + 1, i, item, pre, post))

print(f"한국어 컨텍스트 이미지: {len(kr_images)}개")

# 처음 10개 출력
for seq, i, item, pre, post in kr_images[:10]:
    print(f"\n  [{seq}] 이전: {' / '.join(pre[-2:])[:60]}")
    print(f"       이후: {' / '.join(post[:2])[:60]}")

# HTML 리포트 생성 (한국어 이미지만)
cards = ''
for seq, i, item, pre, post in kr_images:
    rId, rel, inline_t = item[1], item[2], item[3]
    fname = os.path.basename(rel.target_ref) if rel else '?'
    b64 = get_b64(rel)
    img_tag = f'<img src="{b64}" style="width:100%;max-height:140px;object-fit:contain;background:#f9f9f9;border:1px solid #eee;">' if b64 else '<div style="background:#fee;padding:20px;text-align:center;color:#999">이미지 로드 실패</div>'
    pre_html = '<br>'.join(f'<span style="color:#888;font-size:8pt">{t[:60]}</span>' for t in pre[-2:])
    post_html = '<br>'.join(f'<span style="color:#1a237e;font-size:8pt;font-weight:600">{t[:60]}</span>' for t in post[:2])
    has_kr_pre = any(is_korean(t) for t in pre)
    has_kr_post = any(is_korean(t) for t in post)
    bg = '#e8f5e9' if has_kr_post else ('#fff8e1' if has_kr_pre else '#fff')
    cards += f'''
    <div class="card" style="background:{bg}">
      <div class="seq">docx #{seq} | {fname}</div>
      {img_tag}
      <div style="margin-top:6px">
        <div style="font-size:7pt;color:#bbb">▲ 이전</div>
        {pre_html}
      </div>
      <div style="margin-top:4px">
        <div style="font-size:7pt;color:#bbb">▼ 이후</div>
        {post_html}
      </div>
    </div>'''

html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>PVD docx 이미지 순서 분석</title>
<style>
  body {{ font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; font-size: 9pt; }}
  h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }}
  .info {{ color: #555; margin-bottom: 16px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .seq {{ font-size: 8pt; color: #aaa; margin-bottom: 4px; }}
</style>
</head>
<body>
<h1>PVD docx 이미지 순서 분석 — 한국어 컨텍스트 이미지</h1>
<div class="info">
  전체 이미지: {len(image_items)}개 | 한국어 컨텍스트: {len(kr_images)}개<br>
  초록 = 이후 텍스트에 한국어 | 노랑 = 이전 텍스트에만 한국어
</div>
<div class="grid">{cards}
</div>
</body>
</html>'''

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

size_kb = round(os.path.getsize(OUT_HTML) / 1024)
print(f"\n저장: {OUT_HTML} ({size_kb}KB)")
