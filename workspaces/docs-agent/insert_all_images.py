# -*- coding: utf-8 -*-
"""
HTML 매뉴얼의 '별도 첨부' 표시를 pvd_images_named 폴더의 실제 이미지로 교체
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from bs4 import BeautifulSoup
import os, base64, re

HTML_PATH  = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
NAMED_DIR  = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'

def img_to_b64(fpath):
    with open(fpath, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    ext = fpath.rsplit('.',1)[-1].lower()
    mime = 'image/jpeg' if ext in ('jpg','jpeg') else 'image/png'
    return f'data:{mime};base64,{data}'

# named 폴더 파일 목록: {번호: (파일경로, 캡션텍스트)}
named_files = {}
for fname in sorted(os.listdir(NAMED_DIR)):
    m = re.match(r'^(\d{3})_(.+)\.(jpeg|jpg|png)$', fname, re.I)
    if m:
        seq = int(m.group(1))
        caption = m.group(2).replace('_', ' ')
        named_files[seq] = (os.path.join(NAMED_DIR, fname), caption)

print(f"named 이미지 수: {len(named_files)}")

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# figure-caption 순서대로 처리
captions_els = soup.find_all('div', class_='figure-caption')
replaced = 0

for cap_el in captions_els:
    cap_text = cap_el.get_text(strip=True)
    # 순번 찾기 (named_files에서 캡션 텍스트 매칭)
    matched_seq = None
    for seq, (fpath, caption) in named_files.items():
        if caption == cap_text:
            matched_seq = seq
            break

    if matched_seq is None:
        continue

    fpath, _ = named_files[matched_seq]
    if not os.path.exists(fpath):
        continue

    # 현재 figure div 찾기
    figure_div = cap_el.find_parent('div', class_='figure')
    if not figure_div:
        continue

    # 별도 첨부 표시(dashed border div)를 이미지로 교체
    placeholder = figure_div.find('div', style=lambda s: s and 'dashed' in s)
    if placeholder:
        b64 = img_to_b64(fpath)
        new_img = soup.new_tag('img')
        new_img['src'] = b64
        new_img['alt'] = cap_text
        new_img['style'] = 'max-width:100%; max-height:180mm; display:block; margin:0 auto; border:1px solid #e0e0e0;'
        placeholder.replace_with(new_img)
        replaced += 1
        kb = round(os.path.getsize(fpath)/1024)
        print(f"  [{replaced:02d}] {cap_text} ({kb}KB)")

print(f"\n총 {replaced}개 이미지 교체 완료")

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(str(soup))

import os as _os
size_mb = round(_os.path.getsize(HTML_PATH) / 1024 / 1024, 1)
print(f"저장 완료 ({size_mb}MB)")
