"""
PVD Loading Handler - Maintenance Manual Image Catalog
매뉴얼 섹션별 이미지 매칭 (유지보수 절차 순서)
"""
import re
import base64
import hashlib
import io
from pathlib import Path
from PIL import Image

IMG_DIR = Path(r'C:\MES\wta-agents\data\manual_images\(완성본)유지보수 메뉴얼 - 한국야금 PVD Loading Handler')
REPORTS = Path(r'C:\MES\wta-agents\reports')

MIN_W, MIN_H = 250, 200


# Manual section structure with step descriptions (from parsed text)
# Each section: (section_name, [step descriptions])
MANUAL_SECTIONS = [
    ('Regulator 필터 청소', [
        'Door Open — Pneumatic Unit 위치',
        'Pneumatic Unit 패널',
        'Air Combination 유닛 (SMC)',
        'Drain Cock Push — 배출 방법',
        'Air Filter 구조도',
        'Regulator 구조도',
    ]),
    ('Pallet Feeder Unit 점검 (1) — Belt 교체', [
        'Belt Cover 제거 — Door Open',
        'Pallet Feeder Unit 전체 구조',
        'Tension 조정 위치',
        'Tension 제거 후 Block 제거',
        'Belt Clamp 제거',
        'Belt 교체 및 마모, 편심 확인',
        'Belt 조립 방향 — 종동부/구동부',
    ]),
    ('Pallet Feeder Unit 점검 (2) — Y축 Belt', [
        'Pallet Feeder 내부 구조 (측면도)',
        'Pallet Feeder Unit 전체 (측면도)',
        'Pallet Lift 구조 (Z축 승강)',
        'Skewer Elevator Unit',
    ]),
    ('Pallet Feeder Unit 점검 (3) — Z축 Belt', [
        'Cover 제거 — Door Open',
        'Bolt를 풀어서 Tension 제거',
        'Belt 교체 확인',
    ]),
    ('Insert Transfer Unit 점검 (1) — Grease 주입', [
        'Insert Transfer — Belt/Rail 가이드',
        'Insert Transfer Unit 전체 (그리퍼 포함)',
        'Insert Transfer 구동부 (서보 모터)',
        '주입기 (Grease Gun)',
        'Grease Nipple Block',
    ]),
    ('Insert Transfer Unit 점검 (2) — Belt 교체', [
        'Insert Transfer 컨베이어 (분해도)',
        'Insert Transfer 구동부 (2D)',
        'Insert Clamp 가이드',
        'Insert Clamp Pad (레일 위)',
    ]),
    ('Gripper 점검 (1) — 3-Jaw Gripper', [
        '3-Jaw Gripper 분해도 (실린더 + Jaw)',
        '3-Jaw Gripper 조립 상태',
        '3-Jaw Gripper Jaw 분리 (3방향)',
    ]),
    ('Gripper 점검 (2) — Pin 교체', [
        'Gripper Pin 분리 (Pin + Jaw)',
        'Gripper Pin Holder (상세)',
        'Pin 돌출 길이 확인 (9.6mm)',
        'Pin Holder 결합 후 Bolt 체결',
        'Pin 교체 완료',
    ]),
    ('Skewer Grip Cam Unit 점검', [
        'Skewer Align Gripper (단품)',
        'Skewer Grip Cam Bracket (단품)',
        'Skewer Grip Cam Unit (수직 액추에이터)',
        'Guide 상승/후진',
        'Knob Bolt 제거 후 교체',
    ]),
    ('Skewer Index Turning Unit 점검 (1)', [
        'Rotary Index 구동부 (기어 휠, 체인)',
        'Rotary Index Unit (3D 상세)',
        'Rotary Index Plate (상면도)',
        'Skewer Index Turning Unit (슈트 포함)',
        'Insert & Spacer P.P Robot 영역',
        'Ball Screw Flange (근접 상세)',
    ]),
    ('Skewer Index Turning Unit 점검 (2)', [
        'Rotary Index 상부 (체인, 녹색 프레임)',
        'Skewer Index 영역 (녹색 프레임, 체인)',
        'Skewer Index Turning Unit (상세)',
    ]),
    ('Robot Grease 주입', [
        'Down Looking Vision Robot 영역',
        'Skewer Index Turning Robot 영역',
        'Insert & Spacer P.P Robot 영역',
        'Skewer Elevator Robot 영역',
        '견시창 제거',
        'Cover 제거 후 그리스 주입',
        'Grease 도포 방법 (축 하강)',
        'Grease 도포 방법 (축 이동)',
    ]),
    ('장비 외관 참고도', [
        '장비 외관 — 3D 등각뷰',
        '장비 전면부 (도어/조작판/시그널램프)',
        '장비 좌측면 (HMI 패널)',
        '장비 내부 평면도 (전체 유닛 배치)',
        '장비 측면도',
    ]),
]


def natural_sort_key(p):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', p.stem)]


def img_pixel_hash(path):
    try:
        img = Image.open(path)
        img = img.resize((32, 32), Image.LANCZOS).convert('RGB')
        return hashlib.md5(img.tobytes()).hexdigest()
    except:
        return ''


def make_thumb(path, max_size=220):
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
    # Get all images
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    all_imgs = sorted(
        [f for f in IMG_DIR.iterdir() if f.is_file() and f.suffix.lower() in exts],
        key=natural_sort_key
    )
    print(f"Total images: {len(all_imgs)}")

    # Classify and deduplicate
    seen_hashes = {}
    unique_figs = []

    for f in all_imgs:
        try:
            img = Image.open(f)
            w, h = img.size
        except:
            continue

        if w >= MIN_W and h >= MIN_H:
            phash = img_pixel_hash(f)
            if phash not in seen_hashes:
                seen_hashes[phash] = f.name
                unique_figs.append((f, w, h))

    print(f"Unique FIGURE images: {len(unique_figs)}")

    # Count total steps
    total_steps = sum(len(steps) for _, steps in MANUAL_SECTIONS)
    print(f"Manual steps: {total_steps}")

    # Sequential match
    all_cards = []
    fig_idx = 0
    img_cursor = 0

    for section_name, steps in MANUAL_SECTIONS:
        all_cards.append(f'<h3 class="section-title">{section_name}</h3>')
        for step_desc in steps:
            fig_idx += 1
            if img_cursor < len(unique_figs):
                path, w, h = unique_figs[img_cursor]
                thumb = make_thumb(path)
                img_cursor += 1
                all_cards.append(f"""<div class="card">
  <div class="seq">{fig_idx:02d}</div>
  <img src="{thumb}" alt="{step_desc}"/>
  <div class="cap">{step_desc}</div>
  <div class="fname">{path.name} ({w}x{h})</div>
</div>""")
            else:
                all_cards.append(f"""<div class="card missing">
  <div class="seq">{fig_idx:02d}</div>
  <div class="placeholder">이미지 없음</div>
  <div class="cap">{step_desc}</div>
</div>""")

    # Remaining unmatched images
    remaining = unique_figs[img_cursor:]
    if remaining:
        all_cards.append(f'<h3 class="section-title">미매칭 이미지 ({len(remaining)}개)</h3>')
        for path, w, h in remaining:
            thumb = make_thumb(path, 160)
            all_cards.append(f"""<div class="card unmatched">
  <img src="{thumb}" alt="{path.name}"/>
  <div class="fname">{path.name} ({w}x{h})</div>
</div>""")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>PVD Loading Handler — Maintenance Manual Image Catalog</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .info {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .section-title {{ color: #1a237e; font-size: 12pt; margin: 20px 0 8px; padding: 6px 12px; background: #e8eaf6; border-left: 4px solid #1a237e; border-radius: 0 4px 4px 0; grid-column: 1 / -1; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .card.missing {{ border: 2px dashed #ff9800; }}
  .card.unmatched {{ border: 1px solid #ccc; opacity: 0.7; }}
  .placeholder {{ height: 150px; display: flex; align-items: center; justify-content: center; background: #fafafa; color: #ccc; border: 1px dashed #ddd; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #1a237e; font-weight: 700; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #333; margin-top: 6px; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
</style>
</head>
<body>
<h1>PVD Loading Handler — 유지보수 매뉴얼 이미지 카탈로그</h1>
<div class="info">
  {len(MANUAL_SECTIONS)}개 점검 섹션 | {total_steps}개 절차 이미지 | {len(unique_figs)}개 고유 이미지
</div>
<div class="grid">
{''.join(all_cards)}
</div>
</body>
</html>"""

    output = REPORTS / 'pvd_loading_이미지_카탈로그.html'
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\nSaved: {output} ({size_mb:.1f} MB)")
    print(f"Matched: {min(img_cursor, total_steps)}/{total_steps}")


if __name__ == '__main__':
    main()
