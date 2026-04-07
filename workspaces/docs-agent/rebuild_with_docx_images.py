# -*- coding: utf-8 -*-
"""
매뉴얼 HTML의 figure 이미지를 docx 원본 이미지(pvd_images_named/)로 교체
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from bs4 import BeautifulSoup
import os, base64, re

HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
IMG_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'

def img_to_b64(fpath):
    with open(fpath, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    ext = fpath.rsplit('.',1)[-1].lower()
    mime = 'image/jpeg' if ext in ('jpg','jpeg') else 'image/png'
    return f'data:{mime};base64,{data}'

# 파일명 → 경로 매핑 (캡션 텍스트 기반)
file_map = {}
for fname in os.listdir(IMG_DIR):
    m = re.match(r'^\d{3}_(.+)\.(jpeg|jpg|png)$', fname, re.I)
    if m:
        cap_key = m.group(1).replace('_', ' ')
        file_map[cap_key] = os.path.join(IMG_DIR, fname)

print(f"docx 이미지 {len(file_map)}개 로드")

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

replaced = 0
skipped = []

for fig_div in soup.find_all('div', class_='figure'):
    cap_el = fig_div.find('div', class_='figure-caption')
    if not cap_el:
        continue
    caption = cap_el.get_text(strip=True)
    fpath = file_map.get(caption)

    if not fpath:
        skipped.append(caption)
        continue

    img = fig_div.find('img')
    if img:
        img['src'] = img_to_b64(fpath)
        img['alt'] = caption
        replaced += 1
        kb = round(os.path.getsize(fpath)/1024)
        print(f"  [{replaced:02d}] {caption} ({kb}KB)")
    else:
        placeholder = fig_div.find('div', style=lambda s: s and 'dashed' in s)
        if placeholder:
            new_img = soup.new_tag('img')
            new_img['src'] = img_to_b64(fpath)
            new_img['alt'] = caption
            new_img['style'] = 'max-width:100%; max-height:180mm; display:block; margin:0 auto; border:1px solid #e0e0e0;'
            placeholder.replace_with(new_img)
            replaced += 1
            kb = round(os.path.getsize(fpath)/1024)
            print(f"  [{replaced:02d}] {caption} ({kb}KB)")

print(f"\n총 {replaced}개 교체 완료")
if skipped:
    print(f"이미지 없음 ({len(skipped)}개): {', '.join(skipped)}")

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(str(soup))

size_mb = round(os.path.getsize(HTML_PATH)/1024/1024, 1)
print(f"저장 완료 ({size_mb}MB)")
