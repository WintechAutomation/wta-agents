# -*- coding: utf-8 -*-
"""
docx 이미지를 figure-caption 텍스트 기반으로 파일명 변경
방법:
 1. HTML에서 figure-caption 목록 추출 (순서대로)
 2. docx에서 이미지 등장 순서 추출
 3. 순서 매핑 후 파일 복사 (새 이름)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from bs4 import BeautifulSoup
from docx import Document
import os, shutil, re

HTML_PATH  = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
DOCX_PATH  = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\PVD_Unloading_Manual_Revised_20220328.docx'
IMG_DIR    = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images'
OUT_DIR    = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'
os.makedirs(OUT_DIR, exist_ok=True)

# ── 1. HTML에서 figure-caption 목록 추출 ──────────────────────
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
captions = []
for cap in soup.find_all('div', class_='figure-caption'):
    text = cap.get_text(strip=True)
    if text:
        captions.append(text)

print(f"HTML figure-caption 수: {len(captions)}")
for i, c in enumerate(captions[:10]):
    print(f"  [{i+1}] {c}")

# ── 2. docx에서 이미지 등장 순서 추출 ─────────────────────────
doc = Document(DOCX_PATH)
body = doc.element.body

img_order = []  # [(rId, filename), ...]
for blip in body.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
    if rId:
        rel = doc.part.rels.get(rId)
        if rel:
            fname = os.path.basename(rel.target_ref)
            img_order.append((rId, fname))

# 중복 제거 (같은 rId 반복 사용 시)
seen = set()
unique_imgs = []
for rId, fname in img_order:
    if rId not in seen:
        seen.add(rId)
        unique_imgs.append(fname)

print(f"\ndocx 고유 이미지 수: {len(unique_imgs)}")

# ── 3. 파일명 정리 함수 ────────────────────────────────────────
def safe_name(text):
    # 특수문자 제거, 공백→언더스코어
    name = re.sub(r'[\\/:*?"<>|]', '', text)
    name = name.replace(' ', '_')
    return name[:60]  # 최대 60자

# ── 4. 매핑 및 파일 복사 ──────────────────────────────────────
# HTML caption 수 vs docx 이미지 수 중 작은 쪽 기준으로 매핑
# docx 첫 번째 이미지는 로고일 수 있으므로 offset 조정 필요

# 로고 이미지들 (문서 첫 부분, 캡션 없음) 스킵
# docx의 몇 번째 이미지부터가 figure 이미지인지 파악
# HTML caption 수와 docx 이미지 수를 비교해서 offset 결정
# image1.png가 로고이고 실제 그림은 image2.jpeg부터 시작 (map_images.py 결과 기반)
# 전면부=img#2(image2.jpeg), 후면부=img#3(image3.jpeg), 측면부=img#4(image4.jpeg)

# 단순 접근: captions와 unique_imgs를 앞에서부터 매핑
# 실제로 로고/기호 이미지들이 앞에 있으므로 offset을 찾아야 함
# offset = len(docx_imgs) - len(captions) 또는 수동 지정

offset = len(unique_imgs) - len(captions)
if offset < 0:
    offset = 0
print(f"\n추정 offset: {offset} (docx 이미지 {len(unique_imgs)}개 - caption {len(captions)}개)")

renamed = []
for i, cap in enumerate(captions):
    docx_idx = offset + i
    if docx_idx >= len(unique_imgs):
        break
    orig_fname = unique_imgs[docx_idx]
    ext = orig_fname.rsplit('.', 1)[-1].lower()
    new_name = f"{i+1:03d}_{safe_name(cap)}.{ext}"
    src = os.path.join(IMG_DIR, orig_fname)
    dst = os.path.join(OUT_DIR, new_name)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        renamed.append((orig_fname, new_name, cap))
        print(f"  {orig_fname:20s} → {new_name}")
    else:
        print(f"  ⚠️ 파일 없음: {src}")

print(f"\n총 {len(renamed)}개 파일 이름 변경 완료")
print(f"저장 위치: {OUT_DIR}")
