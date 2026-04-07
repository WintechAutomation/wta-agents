# -*- coding: utf-8 -*-
"""
원본 HTML의 각 .figure div에서 base64 이미지를 추출해서
figure-caption 텍스트를 파일명으로 저장
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from bs4 import BeautifulSoup
import os, base64, re

# 원본 HTML (이미지 손대기 전 버전)
HTML_PATH = r'C:\MES\wta-agents\dashboard\uploads\PVD_Unloading_Manual_KR.html'
OUT_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_kr'
os.makedirs(OUT_DIR, exist_ok=True)

def safe_name(text):
    name = re.sub(r'[\\/:*?"<>|]', '', text).strip()
    name = re.sub(r'\s+', '_', name)
    return name[:80]

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

saved = []
no_img = []

for fig_div in soup.find_all('div', class_='figure'):
    cap_el = fig_div.find('div', class_='figure-caption')
    caption = cap_el.get_text(strip=True) if cap_el else ''
    img = fig_div.find('img')

    if not img or not img.get('src', '').startswith('data:image'):
        no_img.append(caption or '(캡션없음)')
        continue

    src = img['src']
    # 형식: data:image/jpeg;base64,....
    m = re.match(r'data:image/(\w+);base64,(.+)', src, re.DOTALL)
    if not m:
        continue

    ext = m.group(1).lower()
    if ext == 'jpeg':
        ext = 'jpg'
    b64_data = m.group(2)

    fname = f"{len(saved)+1:03d}_{safe_name(caption)}.{ext}"
    fpath = os.path.join(OUT_DIR, fname)

    with open(fpath, 'wb') as f:
        f.write(base64.b64decode(b64_data))

    kb = round(os.path.getsize(fpath) / 1024)
    saved.append((fname, caption, kb))
    print(f"  [{len(saved):02d}] {caption} → {fname} ({kb}KB)")

print(f"\n총 {len(saved)}개 이미지 저장 완료")
print(f"저장 위치: {OUT_DIR}")

if no_img:
    print(f"\n이미지 없는 figure ({len(no_img)}개): {', '.join(no_img[:5])}")
