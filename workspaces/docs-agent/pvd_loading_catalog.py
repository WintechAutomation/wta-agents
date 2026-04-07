"""
PVD Loading Handler - 이미지 카탈로그 생성
75개 이미지를 매뉴얼 섹션별로 분류하여 verified 캡션 매칭
"""
import base64
import io
from pathlib import Path
from PIL import Image

IMG_DIR = Path(r'C:\MES\wta-agents\data\manual_images\(완성본)유지보수 메뉴얼 - 한국야금 PVD Loading Handler')
REPORTS = Path(r'C:\MES\wta-agents\reports')

# Verified image-to-caption mapping (visually confirmed)
# Format: (img_file, section, caption)
MAPPING = [
    # === 장비 외관 (Equipment Overview) ===
    ('img_021.png', '장비 외관', '장비 외관 - 3D 등각뷰 (우측 상단)'),
    ('img_022.png', '장비 외관', '장비 외관 - 3D 등각뷰 (좌측 상단)'),
    ('img_028.png', '장비 외관', '장비 외관 - 3D 등각뷰 (정면)'),
    ('img_032.png', '장비 외관', '장비 전면부 (Signal Lamp, 2D)'),
    ('img_003.png', '장비 외관', '장비 전면부 - 도어/조작판/시그널램프'),
    ('img_034.png', '장비 외관', '장비 전면부 (도어 닫힘)'),
    ('img_049.png', '장비 외관', '장비 전면부 (도어 닫힘, Signal Lamp)'),
    ('img_067.png', '장비 외관', '장비 전면부 (도어 개방, Signal Lamp)'),
    ('img_066.png', '장비 외관', '장비 전면부 (우측 도어 개방)'),
    ('img_052.png', '장비 외관', '장비 좌측면 (HMI 패널 표시)'),
    ('img_060.png', '장비 외관', '장비 측면도 (2D)'),
    ('img_030.png', '장비 외관', '장비 내부 평면도 (전체 유닛 배치)'),
    ('img_035.png', '장비 외관', '좌측면 Door Open (HMI, 서보 유닛)'),
    ('img_063.png', '장비 외관', 'Door Open - Pallet 트레이 영역'),
    ('img_011.png', '장비 외관', '장비 내부 (서보 유닛, 케이블 체인)'),
    ('img_051.png', '장비 외관', '장비 내부 측면 (서보, 케이블 체인)'),

    # === Pneumatic Unit / Regulator 필터 청소 ===
    ('img_009.png', 'Regulator 필터 청소', 'Pneumatic Unit 위치 - Door Open'),
    ('img_031.png', 'Regulator 필터 청소', 'Pneumatic Unit 패널 (Door Open)'),
    ('img_054.png', 'Regulator 필터 청소', 'Pneumatic Unit 패널 (상세)'),
    ('img_061.png', 'Regulator 필터 청소', 'Pneumatic Unit 패널'),
    ('img_017.png', 'Regulator 필터 청소', 'Air Combination 유닛 (SMC)'),
    ('img_008.png', 'Regulator 필터 청소', 'Drain Cock Push (배출 방법)'),
    ('img_047.png', 'Regulator 필터 청소', 'Air Filter 구조도 (Drain Cock)'),
    ('img_062.jpg', 'Regulator 필터 청소', 'Regulator 구조도 (Drain Cock)'),

    # === Pallet Feeder Unit 점검 ===
    ('img_001.png', 'Pallet Feeder Unit', 'Pallet Feeder 내부 구조 (2D 측면도)'),
    ('img_016.png', 'Pallet Feeder Unit', 'Pallet Feeder Unit 전체 (2D 측면도)'),
    ('img_070.png', 'Pallet Feeder Unit', 'Pallet Feeder Unit (3D 등각뷰)'),
    ('img_071.png', 'Pallet Feeder Unit', 'Pallet Feeder 상세 (실린더/가이드)'),
    ('img_020.png', 'Pallet Feeder Unit', 'Pallet Lift 구조 (Z축 승강)'),
    ('img_055.png', 'Pallet Feeder Unit', 'Skewer Elevator Unit (3D)'),
    ('img_010.png', 'Pallet Feeder Unit', 'Skewer Elevator Unit (3D 상세)'),

    # === Insert Transfer Unit 점검 ===
    ('img_004.png', 'Insert Transfer Unit', 'Insert Transfer - Belt/Rail 가이드 블록'),
    ('img_005.png', 'Insert Transfer Unit', 'Insert Transfer Unit 전체 (그리퍼 포함)'),
    ('img_019.png', 'Insert Transfer Unit', 'Insert Transfer 구동부 (서보 모터)'),
    ('img_033.png', 'Insert Transfer Unit', 'Insert Transfer 구동부 (2D)'),
    ('img_056.png', 'Insert Transfer Unit', 'Insert Transfer 컨베이어 (분해도)'),
    ('img_039.png', 'Insert Transfer Robot', 'Insert Transfer Robot (리니어 액추에이터)'),
    ('img_045.png', 'Insert Transfer Robot', 'Insert Transfer Robot (전체뷰)'),
    ('img_013.png', 'Insert Transfer Unit', 'Insert Clamp 가이드 (상세)'),
    ('img_058.jpg', 'Insert Transfer Unit', 'Insert Clamp Pad (레일 위)'),

    # === Gripper 점검 ===
    ('img_012.png', 'Gripper 점검', '3-Jaw Gripper 분해도 (실린더 + Jaw)'),
    ('img_024.PNG', 'Gripper 점검', '3-Jaw Gripper 조립 상태'),
    ('img_029.png', 'Gripper 점검', '3-Jaw Gripper Jaw 분리 (3방향)'),
    ('img_057.png', 'Gripper 점검', 'Gripper Pin 분리 (Pin + Jaw)'),
    ('img_042.png', 'Gripper 점검', 'Gripper Pin Holder (상세)'),
    ('img_068.png', 'Gripper 점검', 'Pin 돌출 길이 확인 (9.6mm)'),

    # === Skewer Grip Cam Unit 점검 ===
    ('img_025.png', 'Skewer Grip Cam Unit', 'Skewer Align Gripper (단품)'),
    ('img_036.png', 'Skewer Grip Cam Unit', 'Skewer Grip Cam Bracket (단품)'),
    ('img_065.png', 'Skewer Grip Cam Unit', 'Skewer Grip Cam Unit (수직 액추에이터)'),

    # === Skewer Index Turning Unit ===
    ('img_015.png', 'Skewer Index Turning Unit', 'Rotary Index 구동부 (기어 휠, 체인)'),
    ('img_006.png', 'Skewer Index Turning Unit', 'Rotary Index - Insert 핸들링 영역'),
    ('img_053.png', 'Skewer Index Turning Unit', 'Rotary Index Unit (3D 상세)'),
    ('img_044.png', 'Skewer Index Turning Unit', 'Rotary Index 상부 (체인, 녹색 프레임)'),
    ('img_069.png', 'Skewer Index Turning Unit', 'Rotary Index Plate (상면도)'),
    ('img_026.png', 'Skewer Index Turning Unit', 'Skewer Index Turning Unit (슈트 포함)'),
    ('img_038.png', 'Skewer Index Turning Unit', 'Skewer Index Turning Unit (상세)'),
    ('img_074.png', 'Skewer Index Turning Unit', 'Skewer Index 영역 (녹색 프레임, 체인)'),
    ('img_037.png', 'Skewer Index Turning Unit', 'Insert & Spacer P.P Robot 영역'),
    ('img_043.png', 'Skewer Index Turning Unit', 'Ball Screw Flange (근접 상세)'),

    # === Down Looking Vision Robot ===
    ('img_007.png', 'Vision Robot', 'Down Looking Vision Robot 영역'),
    ('img_002.jpeg', 'Vision Robot', 'Vision 카메라 유닛 (근접 상세)'),
    ('img_040.jpeg', 'Vision Robot', 'Vision 카메라 유닛 (근접)'),
    ('img_048.png', 'Vision Robot', 'Vision 카메라 유닛'),
    ('img_018.png', 'Vision Robot', 'Vision 카메라 상세 (옐로우 실린더)'),
    ('img_059.png', 'Vision Robot', 'Vision Robot 영역 (블루 슈트)'),
    ('img_023.png', 'Vision Robot', '내부 상세 - Vision 영역 (그린/옐로우)'),

    # === Robot Grease 주입 ===
    ('img_041.png', 'Robot Grease 주입', '주입기 (Grease Gun)'),
    ('img_072.png', 'Robot Grease 주입', '주입기 (Grease Gun)'),
    ('img_050.png', 'Robot Grease 주입', 'Grease Nipple Block (8포트)'),
    ('img_064.png', 'Robot Grease 주입', 'Grease Nipple Block (8포트)'),
    ('img_073.png', 'Robot Grease 주입', 'Cover 제거 영역 (견시창)'),

    # === 기타/실물 사진 ===
    ('img_014.jpeg', '실물 사진', 'Door 내부 - LM Guide 위치 (실물)'),
    ('img_027.jpeg', '실물 사진', '액추에이터/센서 영역 (실물)'),
    ('img_046.jpeg', '실물 사진', '서보 로봇 (옐로우, 실물)'),
    ('img_075.jpeg', '실물 사진', '리니어 레일/케이블 체인 (실물)'),
]


def make_thumb(path: Path, max_size: int = 220) -> str:
    try:
        img = Image.open(path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = 'JPEG' if path.suffix.lower() in ['.jpg', '.jpeg'] else 'PNG'
        if fmt == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buf, format=fmt, quality=50)
        b64 = base64.b64encode(buf.getvalue()).decode()
        mime = 'jpeg' if fmt == 'JPEG' else 'png'
        return f"data:image/{mime};base64,{b64}"
    except:
        return ""


def main():
    # Group by section
    sections = {}
    for fname, section, caption in MAPPING:
        if section not in sections:
            sections[section] = []
        sections[section].append((fname, caption))

    # Build cards grouped by section
    all_cards = []
    seq = 0
    for section, items in sections.items():
        all_cards.append(f'<h3 class="section-title">{section} ({len(items)})</h3>')
        for fname, caption in items:
            seq += 1
            fpath = IMG_DIR / fname
            if not fpath.exists():
                print(f"  SKIP (not found): {fname}")
                continue
            img = Image.open(fpath)
            w, h = img.size
            thumb = make_thumb(fpath)
            all_cards.append(f"""<div class="card">
  <div class="seq">{seq:03d}</div>
  <img src="{thumb}" alt="{caption}"/>
  <div class="cap">{caption}</div>
  <div class="fname">{fname} ({w}x{h})</div>
</div>""")

    total = len(MAPPING)
    section_count = len(sections)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>PVD Loading Handler - Image Catalog</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .info {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .section-title {{ color: #1a237e; font-size: 12pt; margin: 20px 0 8px; padding: 6px 12px; background: #e8eaf6; border-left: 4px solid #1a237e; border-radius: 0 4px 4px 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 140px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 8pt; color: #aaa; margin-bottom: 2px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #1a237e; margin-top: 4px; }}
  .fname {{ font-size: 7pt; color: #888; font-family: monospace; margin-top: 2px; }}
</style>
</head>
<body>
<h1>PVD Loading Handler - Maintenance Manual Image Catalog</h1>
<div class="info">{section_count}개 섹션 | 총 {total}개 이미지 | 이미지 개별 확인 완료</div>
<div class="grid">
{''.join(all_cards)}
</div>
</body>
</html>"""

    output = REPORTS / 'pvd_loading_이미지_카탈로그.html'
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"Saved: {output} ({size_mb:.1f} MB)")
    print(f"{section_count} sections | {total} images")


if __name__ == '__main__':
    main()
