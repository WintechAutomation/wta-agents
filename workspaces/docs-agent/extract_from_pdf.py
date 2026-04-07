# -*- coding: utf-8 -*-
"""
HAM-PVD_ULO_User_Manual.pdf에서 Figure 이미지를 순서대로 추출
각 Figure가 있는 페이지에서 이미지 위치 + 캡션 텍스트로 파일명 저장
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import fitz  # PyMuPDF
import os, re

PDF_PATH  = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\HAM-PVD_ULO_User_Manual.pdf'
HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
OUT_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'

from bs4 import BeautifulSoup

# HTML 한국어 caption 목록
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
kr_captions = [c.get_text(strip=True) for c in soup.find_all('div', class_='figure-caption')]
print(f"HTML 한국어 caption: {len(kr_captions)}개")

def safe_name(text):
    name = re.sub(r'[\\/:*?"<>|]', '', text).strip()
    return re.sub(r'\s+', '_', name)[:80]

pdf = fitz.open(PDF_PATH)
print(f"PDF 페이지: {len(pdf)}개")

# Figure X-X 패턴으로 페이지별 이미지 + 캡션 수집
fig_pattern = re.compile(r'Figure\s+(\d+)-(\d+)', re.I)

collected = []  # [(fig_label, img_bytes, ext)]

for page_num, page in enumerate(pdf):
    text = page.get_text()
    figs = list(fig_pattern.finditer(text))
    if not figs:
        continue

    # 이 페이지의 이미지 목록
    img_list = page.get_images(full=True)
    if not img_list:
        continue

    # 각 Figure 캡션 위치에서 가장 가까운 이미지 추출
    # 페이지에서 Figure 텍스트 블록 좌표 찾기
    blocks = page.get_text('dict')['blocks']

    for match in figs:
        fig_label = f"Figure {match.group(1)}-{match.group(2)}"
        # 해당 Figure 블록 좌표
        fig_rect = None
        for block in blocks:
            if block.get('type') == 0:  # text block
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        if re.search(r'Figure\s+' + re.escape(match.group(1) + '-' + match.group(2)), span['text'], re.I):
                            fig_rect = fitz.Rect(block['bbox'])
                            break

        if not img_list:
            continue

        # Figure 레이블 위치 기준으로 가장 가까운 이미지 선택
        best_xref = None
        best_dist = float('inf')

        for img_info in img_list:
            xref = img_info[0]
            # 이미지 위치 (페이지 내 rects)
            for item in page.get_image_rects(xref):
                img_rect = fitz.Rect(item)
                if fig_rect:
                    # Figure 텍스트 바로 위에 있는 이미지 선호 (캡션이 이미지 아래에 있는 경우)
                    dist = abs(img_rect.y1 - fig_rect.y0)
                    if dist < best_dist:
                        best_dist = dist
                        best_xref = xref

        if best_xref is None and img_list:
            best_xref = img_list[0][0]

        if best_xref:
            img_dict = pdf.extract_image(best_xref)
            img_bytes = img_dict['image']
            ext = img_dict['ext']
            if ext == 'jpeg':
                ext = 'jpg'
            collected.append((fig_label, img_bytes, ext, page_num + 1))
            print(f"  p{page_num+1}: {fig_label} ({round(len(img_bytes)/1024)}KB)")

print(f"\n추출된 Figure 이미지: {len(collected)}개")

# 중복 제거 (같은 Figure 레이블이 여러 번 나올 수 있음)
seen = {}
unique = []
for fig_label, img_bytes, ext, pnum in collected:
    if fig_label not in seen:
        seen[fig_label] = True
        unique.append((fig_label, img_bytes, ext, pnum))

print(f"중복 제거 후: {len(unique)}개")
print(f"HTML caption 수: {len(kr_captions)}개")

# 순서 기반으로 한국어 caption과 매핑 (Figure 순번 기준 정렬)
def fig_sort_key(item):
    m = re.search(r'Figure\s+(\d+)-(\d+)', item[0])
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    return 0

unique.sort(key=fig_sort_key)

# 저장
import shutil
backup_dir = OUT_DIR + '_backup2'
if not os.path.exists(backup_dir):
    shutil.copytree(OUT_DIR, backup_dir)
    print(f"백업: {backup_dir}")

# 기존 파일 삭제
for fname in os.listdir(OUT_DIR):
    os.remove(os.path.join(OUT_DIR, fname))

saved = 0
for i, (fig_label, img_bytes, ext, pnum) in enumerate(unique):
    if i >= len(kr_captions):
        print(f"  [경고] HTML caption 초과: {fig_label}")
        break
    kr_cap = kr_captions[i]
    fname = f"{i+1:03d}_{safe_name(kr_cap)}.{ext}"
    fpath = os.path.join(OUT_DIR, fname)
    with open(fpath, 'wb') as f:
        f.write(img_bytes)
    kb = round(len(img_bytes) / 1024)
    print(f"  [{i+1:02d}] {fig_label} → {kr_cap} ({kb}KB) | p{pnum}")
    saved += 1

print(f"\n총 {saved}개 저장 완료 → {OUT_DIR}")

if saved < len(kr_captions):
    print(f"\n미처리 caption ({len(kr_captions) - saved}개):")
    for cap in kr_captions[saved:]:
        print(f"  - {cap}")
