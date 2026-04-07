"""PDF에서 모든 페이지를 고해상도 렌더링하고, 삽입된 이미지 객체를 추출하여 base64-data.json 업데이트."""
import fitz  # PyMuPDF
import json
import os
import base64
from io import BytesIO

PDF_PATH = r"C:\MES\wta-agents\data\wta-manuals-final\PVD\HAM-PVD_Unloading_User_Manual_en_v1.3.pdf"
IMG_DIR = r"C:\MES\wta-agents\reports\templates\images"
os.makedirs(IMG_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)
print(f"PDF: {doc.page_count} pages")

# ── 1) 각 페이지를 고해상도(200 DPI)로 렌더링 ──
page_images = {}
for i in range(doc.page_count):
    page = doc[i]
    # 200 DPI = 약 2.78x 스케일
    mat = fitz.Matrix(2.78, 2.78)
    pix = page.get_pixmap(matrix=mat)
    fname = f"page-{i+1:02d}.png"
    fpath = os.path.join(IMG_DIR, fname)
    pix.save(fpath)
    page_images[i+1] = fpath
    print(f"  page {i+1}/{doc.page_count} rendered ({pix.width}x{pix.height})")

# ── 2) 내장 이미지 객체 추출 ──
img_count = 0
extracted = {}
for i in range(doc.page_count):
    page = doc[i]
    img_list = page.get_images(full=True)
    for j, img_info in enumerate(img_list):
        xref = img_info[0]
        if xref in extracted:
            continue
        try:
            base_image = doc.extract_image(xref)
            ext = base_image["ext"]
            data = base_image["image"]
            w = base_image["width"]
            h = base_image["height"]
            # 너무 작은 이미지(아이콘급) 스킵
            if w < 30 or h < 30:
                continue
            fname = f"embedded-p{i+1:02d}-{j+1:02d}.{ext}"
            fpath = os.path.join(IMG_DIR, fname)
            with open(fpath, "wb") as f:
                f.write(data)
            extracted[xref] = fname
            img_count += 1
            print(f"  embedded image: {fname} ({w}x{h})")
        except Exception as e:
            print(f"  skip xref {xref}: {e}")

print(f"\nTotal: {doc.page_count} pages rendered, {img_count} embedded images extracted")

# ── 3) 위험 아이콘 SVG 생성 (모든 언어 통일용) ──
# 위험(빨간 삼각형), 경고(노란 삼각형), 금지(빨간 원+사선), 참고(파란 원+i)
icons_svg = {
    "icon_danger_svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,8 95,88 5,88" fill="#DC3545" stroke="#A71D2A" stroke-width="3" stroke-linejoin="round"/>
  <text x="50" y="76" text-anchor="middle" font-size="52" font-weight="bold" fill="white" font-family="Arial">!</text>
</svg>''',
    "icon_warning_svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <polygon points="50,8 95,88 5,88" fill="#FFC107" stroke="#D4A017" stroke-width="3" stroke-linejoin="round"/>
  <text x="50" y="76" text-anchor="middle" font-size="52" font-weight="bold" fill="#333" font-family="Arial">!</text>
</svg>''',
    "icon_caution_svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="50" r="44" fill="#DC3545" stroke="#A71D2A" stroke-width="4"/>
  <line x1="22" y1="22" x2="78" y2="78" stroke="white" stroke-width="8" stroke-linecap="round"/>
</svg>''',
    "icon_info_svg": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="50" r="44" fill="#2E86C1" stroke="#1B4F72" stroke-width="4"/>
  <text x="50" y="72" text-anchor="middle" font-size="56" font-weight="bold" fill="white" font-family="Arial">i</text>
</svg>''',
}

# SVG를 PNG로 저장 (base64 data URI 형태)
for key, svg_content in icons_svg.items():
    fname = f"{key.replace('_svg', '')}.svg"
    fpath = os.path.join(IMG_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"  icon: {fname}")

# ── 4) base64-data.json 업데이트 ──
b64_path = os.path.join(IMG_DIR, "base64-data.json")
if os.path.exists(b64_path):
    with open(b64_path, "r") as f:
        b64_data = json.load(f)
else:
    b64_data = {}

# 헤더, 로고 등 기존 항목 유지
# 위험 아이콘을 SVG data URI로 교체
for key, svg_content in icons_svg.items():
    b64_key = key.replace("_svg", "").replace("icon_", "icon_")
    svg_b64 = base64.b64encode(svg_content.encode("utf-8")).decode("ascii")
    b64_data[b64_key] = f"data:image/svg+xml;base64,{svg_b64}"

# 페이지 렌더링 이미지를 base64로 추가 (본문 그림용)
# 주요 그림이 있는 페이지만 추가
figure_pages = {
    # 챕터 1: 장비 외관
    "fig_1_1": 7,   # Figure 1-1 Front (page 7)
    "fig_1_2": 8,   # Figure 1-2 Rear (page 8)
    "fig_1_3": 9,   # Figure 1-3 Lateral (page 9)
    # 챕터 2: 안전
    "fig_2_1": 12,  # Emergency Stop
    "fig_2_2": 13,  # Signal lamps
    # 챕터 3: 시운전
    "fig_3_1": 17,  # Power on
    "fig_3_2": 19,  # Control panel
    # 챕터 4: 메인 화면
    "fig_4_1": 20,  # Main Screen
    # 챕터 5: 모델 관리
    "fig_5_1": 23,  # Model setup 1
    "fig_5_2": 24,  # Model setup 2
    "fig_5_3": 24,  # Pattern settings (same page or next)
    # 챕터 6: 팔레트 관리
    "fig_6_1": 25,  # Pallet mgmt 1
    "fig_6_2": 26,  # Pallet mgmt 2
    "fig_6_3": 28,  # Bar mgmt 1
    "fig_6_4": 28,  # Bar mgmt 2
    "fig_6_5": 29,  # Spacer mgmt 1
    "fig_6_6": 29,  # Spacer mgmt 2
    # 챕터 7: 적재 관리
    "fig_7_1": 30,  # Manage loads
    "fig_7_2": 30,  # Select model
    "fig_7_3": 31,  # Pallet settings
    "fig_7_4": 32,  # Index setup
    # 챕터 8: 환경설정
    "fig_8_1": 33,  # Default task
    "fig_8_2": 34,  # Pallet actions
    "fig_8_3": 35,  # Rotary stacker
    # 챕터 9: 작업 위치
    "fig_9_1": 36,  # Teaching schedule
    "fig_9_2": 37,  # Position offset
    # 챕터 10: 자동 운전
    "fig_10_1": 38, # Reset
    "fig_10_2": 39, # Pause
    "fig_10_3": 39, # Stop
    "fig_10_4": 40, # Location compensation
    "fig_10_5": 41, # Image settings
    "fig_10_6": 42, # Check supplies
    # 챕터 11: 작업자 조작 순서
    "fig_11_1": 43, # Operator
    "fig_11_2": 44, # Managing pallet
    "fig_11_3": 45, # Manage bars
    "fig_11_4": 46, # Manage spacers
    "fig_11_5": 47, # Model file
    "fig_11_6": 48, # Loading setup
    "fig_11_7": 49, # Preferences
    "fig_11_8": 49, # Select teaching
    "fig_11_9": 50, # Start driving
    "fig_11_10": 51, # Vision 1
    "fig_11_11": 51, # Vision 2
    "fig_11_12": 52, # Shape setting
    "fig_11_13": 53, # Register
    "fig_11_14": 53, # Score
    "fig_11_15": 54, # Brush size
    "fig_11_16": 54, # Masking
}

for fig_key, page_num in figure_pages.items():
    png_path = os.path.join(IMG_DIR, f"page-{page_num:02d}.png")
    if os.path.exists(png_path):
        with open(png_path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        b64_data[fig_key] = f"data:image/png;base64,{b64}"

with open(b64_path, "w") as f:
    json.dump(b64_data, f, ensure_ascii=False)

print(f"\nbase64-data.json updated: {len(b64_data)} entries, {os.path.getsize(b64_path):,} bytes")
doc.close()
