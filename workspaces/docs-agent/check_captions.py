# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
from bs4 import BeautifulSoup
import os, re

HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
IMG_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'

# 파일 목록 파싱
file_map = {}  # cap_key -> (seq, fname)
for fname in sorted(os.listdir(IMG_DIR)):
    m = re.match(r'^(\d{3})_(.+)\.(jpeg|jpg|png)$', fname, re.I)
    if m:
        seq = int(m.group(1))
        cap_key = m.group(2).replace('_', ' ')
        file_map[cap_key] = (seq, fname)

# HTML caption 파싱
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

captions = [c.get_text(strip=True) for c in soup.find_all('div', class_='figure-caption')]

# 매칭 결과 출력
print("=" * 80)
print(f"{'HTML caption':<40} | {'매칭 파일명'}")
print("=" * 80)
matched = []
unmatched = []
for i, cap in enumerate(captions, 1):
    if cap in file_map:
        seq, fname = file_map[cap]
        matched.append((i, cap, fname))
        print(f"[{i:02d}] {cap:<38} | {fname}")
    else:
        unmatched.append((i, cap))
        print(f"[{i:02d}] {cap:<38} | *** 미매칭 ***")

print()
print(f"총 HTML caption: {len(captions)}개")
print(f"매칭 성공: {len(matched)}개")
print(f"미매칭: {len(unmatched)}개")
if unmatched:
    print("\n미매칭 목록:")
    for i, cap in unmatched:
        print(f"  [{i:02d}] {cap}")

# 파일은 있는데 HTML에 없는 것
print()
file_caps = set(file_map.keys())
html_caps = set(captions)
extra = file_caps - html_caps
if extra:
    print(f"\n파일은 있으나 HTML에 없는 캡션 ({len(extra)}개):")
    for k in sorted(extra):
        seq, fname = file_map[k]
        print(f"  [{seq:03d}] {k} → {fname}")
