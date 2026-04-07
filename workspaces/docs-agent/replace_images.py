# -*- coding: utf-8 -*-
"""
base64 인라인 이미지를 '별도 첨부' 표시로 교체
- 유지: cover-logo, back-cover 안의 이미지 (로고)
- 교체: page-header, figure 등 본문/캡처 이미지 → 첨부 표시
"""
from bs4 import BeautifulSoup
import re

src = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
dst = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'

with open(src, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# 로고 이미지 보호 (cover-logo, back-cover)
protected = set()
for div in soup.find_all('div', class_=['cover-logo', 'back-cover']):
    for img in div.find_all('img'):
        protected.add(id(img))

count = 0
for img in soup.find_all('img'):
    if id(img) in protected:
        continue
    src_val = img.get('src', '')
    if src_val.startswith('data:image'):
        count += 1
        # 이미지 크기 추정 (bytes)
        b64_len = len(src_val)
        size_kb = round(b64_len * 0.75 / 1024)

        # 이미지가 속한 컨텍스트 파악
        parent_classes = []
        p = img.parent
        for _ in range(4):
            if p and p.get('class'):
                parent_classes.extend(p.get('class', []))
            if p:
                p = p.parent

        # 첨부 표시로 교체
        placeholder = soup.new_tag('div')
        placeholder['style'] = (
            'border:2px dashed #aaa; border-radius:6px; padding:18px; '
            'text-align:center; color:#666; background:#f8f8f8; margin:10px 0; '
            'font-size:9pt;'
        )
        placeholder.string = f'📎 첨부 이미지 {count}  (약 {size_kb}KB — 원본 파일 별도 첨부)'
        img.replace_with(placeholder)

with open(dst, 'w', encoding='utf-8') as f:
    f.write(str(soup))

print(f"완료: {count}개 이미지 → 첨부 표시로 교체")
