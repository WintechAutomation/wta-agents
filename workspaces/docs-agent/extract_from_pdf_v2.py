# -*- coding: utf-8 -*-
"""
HAM-PVD_ULO_User_Manual.pdf에서 Figure 이미지를 번호 기반으로 추출
그림 X-Y 번호 ↔ Figure X-Y 번호 매핑 (순서 기반 아님)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import fitz
import os, re, shutil

PDF_PATH  = r'C:\MES\wta-agents\data\wta-manuals-final\PVD\HAM-PVD_ULO_User_Manual.pdf'
HTML_PATH = r'C:\MES\wta-agents\reports\PVD_Unloading_Manual_KR.html'
OUT_DIR   = r'C:\MES\wta-agents\workspaces\docs-agent\pvd_images_named'

from bs4 import BeautifulSoup

# HTML 한국어 caption 목록 + 번호 추출
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
kr_captions = [c.get_text(strip=True) for c in soup.find_all('div', class_='figure-caption')]

# caption에서 번호 추출: "그림 1-1 전면부" → "1-1"
kr_fig_map = {}   # "1-1" → (seq, caption)
kr_extra = []     # 번호 없는 것들 (별도 첨부 등)
for i, cap in enumerate(kr_captions):
    m = re.match(r'그림\s+(\d+[-–]\d+)', cap)
    if m:
        num = m.group(1).replace('–', '-')
        kr_fig_map[num] = (i + 1, cap)
    else:
        kr_extra.append((i + 1, cap))

print(f"HTML 번호 있는 caption: {len(kr_fig_map)}개")
print(f"HTML 번호 없는 caption: {len(kr_extra)}개 → {[c for _, c in kr_extra]}")

def safe_name(text):
    name = re.sub(r'[\\/:*?"<>|]', '', text).strip()
    return re.sub(r'\s+', '_', name)[:80]

# PDF에서 Figure 이미지 추출
pdf = fitz.open(PDF_PATH)
fig_pattern = re.compile(r'Figure\s+(\d+)[-–](\d+)', re.I)

# 페이지별 Figure 캡션 위치와 이미지를 수집
pdf_figures = {}  # "1-1" → (img_bytes, ext, page_num)

for page_num, page in enumerate(pdf):
    text = page.get_text()
    img_list = page.get_images(full=True)
    if not img_list:
        continue

    figs = list(fig_pattern.finditer(text))
    if not figs:
        continue

    # 페이지의 텍스트 블록과 이미지 rect 파악
    blocks = page.get_text('dict')['blocks']

    for match in figs:
        fig_num = f"{match.group(1)}-{match.group(2)}"
        if fig_num in pdf_figures:
            continue  # 이미 수집됨

        # Figure 텍스트 블록 위치 찾기
        fig_rect = None
        for block in blocks:
            if block.get('type') == 0:
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        if re.search(r'Figure\s+' + re.escape(match.group(1) + '-' + match.group(2)), span['text'], re.I):
                            fig_rect = fitz.Rect(block['bbox'])

        # 해당 Figure와 가장 가까운 이미지 선택 (위쪽 이미지 우선)
        best_xref = None
        best_score = float('inf')

        for img_info in img_list:
            xref = img_info[0]
            for item in page.get_image_rects(xref):
                img_rect = fitz.Rect(item)
                # 이미지가 Figure 텍스트 위에 있는 경우 (캡션이 아래)
                if fig_rect:
                    if img_rect.y1 <= fig_rect.y0 + 5:  # 이미지가 텍스트 위에 있거나 약간 겹침
                        dist = fig_rect.y0 - img_rect.y1
                        if dist < best_score:
                            best_score = dist
                            best_xref = xref
                else:
                    best_xref = img_info[0]

        # 위쪽 이미지 못 찾으면 가장 가까운 이미지
        if best_xref is None:
            best_score = float('inf')
            for img_info in img_list:
                xref = img_info[0]
                for item in page.get_image_rects(xref):
                    img_rect = fitz.Rect(item)
                    if fig_rect:
                        dist = abs(img_rect.y1 - fig_rect.y0)
                        if dist < best_score:
                            best_score = dist
                            best_xref = xref

        if best_xref:
            img_dict = pdf.extract_image(best_xref)
            ext = img_dict['ext']
            if ext == 'jpeg':
                ext = 'jpg'
            pdf_figures[fig_num] = (img_dict['image'], ext, page_num + 1)

print(f"\nPDF Figure 추출: {len(pdf_figures)}개")
for k in sorted(pdf_figures.keys(), key=lambda x: [int(n) for n in x.split('-')]):
    kb = round(len(pdf_figures[k][0]) / 1024)
    pg = pdf_figures[k][2]
    matched = k in kr_fig_map
    mark = '✓' if matched else '✗ (HTML 없음)'
    print(f"  Figure {k}: {kb}KB p{pg} {mark}")

# 저장
backup_dir = OUT_DIR + '_backup3'
if not os.path.exists(backup_dir):
    shutil.copytree(OUT_DIR, backup_dir)
    print(f"\n백업: {backup_dir}")

for fname in os.listdir(OUT_DIR):
    os.remove(os.path.join(OUT_DIR, fname))

saved = 0
missing = []

# 번호 있는 caption들 먼저 저장
for num, (seq, kr_cap) in sorted(kr_fig_map.items(), key=lambda x: [int(n) for n in x[0].split('-')]):
    if num in pdf_figures:
        img_bytes, ext, pnum = pdf_figures[num]
        fname = f"{seq:03d}_{safe_name(kr_cap)}.{ext}"
        fpath = os.path.join(OUT_DIR, fname)
        with open(fpath, 'wb') as f:
            f.write(img_bytes)
        kb = round(len(img_bytes) / 1024)
        print(f"  [{seq:02d}] Figure {num} → {kr_cap} ({kb}KB) p{pnum}")
        saved += 1
    else:
        missing.append((seq, kr_cap, num))
        print(f"  [{seq:02d}] Figure {num} → {kr_cap} *** PDF에 없음 ***")

# 번호 없는 caption들 (별도 첨부 등) — 빈 placeholder로 저장
for seq, kr_cap in kr_extra:
    fname = f"{seq:03d}_{safe_name(kr_cap)}.png"
    fpath = os.path.join(OUT_DIR, fname)
    # 빈 PNG (1x1 투명)
    import base64
    empty_png = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    with open(fpath, 'wb') as f:
        f.write(empty_png)
    print(f"  [{seq:02d}] {kr_cap} (placeholder)")

print(f"\n총 {saved}개 매핑 완료 (+ {len(kr_extra)}개 placeholder)")
if missing:
    print(f"누락: {[(n, c) for _, c, n in missing]}")
