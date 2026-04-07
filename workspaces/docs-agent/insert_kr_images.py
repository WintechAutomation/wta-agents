# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from bs4 import BeautifulSoup
import os, base64, re

HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
IMG_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_kr'

def safe_name(text):
    name = re.sub(r'[\\/:*?"<>|]', '', text).strip()
    return re.sub(r'\s+', '_', name)[:80]

def img_to_b64(fpath):
    with open(fpath, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    ext = fpath.rsplit('.',1)[-1].lower()
    mime = 'image/jpeg' if ext in ('jpg','jpeg') else 'image/png'
    return f'data:{mime};base64,{data}'

# 파일명 → 캡션 매핑
file_map = {}  # safe_caption -> fpath
for fname in os.listdir(IMG_DIR):
    m = re.match(r'^\d{3}_(.+)\.(png|jpg|jpeg)$', fname, re.I)
    if m:
        cap_key = m.group(1).replace('_', ' ')
        file_map[cap_key] = os.path.join(IMG_DIR, fname)

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
    if not img:
        # placeholder div인 경우
        placeholder = fig_div.find('div', style=lambda s: s and 'dashed' in s)
        if placeholder:
            new_img = soup.new_tag('img')
            new_img['src'] = img_to_b64(fpath)
            new_img['alt'] = caption
            new_img['style'] = 'max-width:100%; max-height:180mm; display:block; margin:0 auto; border:1px solid #e0e0e0;'
            placeholder.replace_with(new_img)
            replaced += 1
            print(f"  [{replaced:02d}] {caption}")
    else:
        img['src'] = img_to_b64(fpath)
        img['alt'] = caption
        replaced += 1
        print(f"  [{replaced:02d}] {caption}")

print(f"\n총 {replaced}개 교체 완료")
if skipped:
    print(f"스킵 ({len(skipped)}개): {', '.join(skipped)}")

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(str(soup))

size_mb = round(os.path.getsize(HTML_PATH) / 1024 / 1024, 1)
print(f"저장 완료 ({size_mb}MB)")
