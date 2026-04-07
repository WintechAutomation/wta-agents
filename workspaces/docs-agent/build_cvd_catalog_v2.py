"""
CVD L&UL Machine EN — 이미지 카탈로그 (수동 검증 매칭)
83개 Figure 캡션을 이미지와 시각적으로 확인하여 매칭
Sequential 매칭이 아닌 이미지 내용 기반 verified 매칭
"""
import re
import base64
import hashlib
import io
from pathlib import Path
from PIL import Image

IMG_DIR = Path(r'C:\MES\wta-agents\data\manual_images\HAM-CVD L&UL Machine User Manual en_v1.0')
REPORTS = Path(r'C:\MES\wta-agents\reports')

# === Verified image-to-figure mapping (visually confirmed) ===
# Format: (img_file, figure_caption, section)
MAPPING = [
    # ──────────────────────────────────────────
    # Part 1: User Manual
    # ──────────────────────────────────────────

    # Ch 1. Machine Appearance
    ('img_196.png', 'Figure - Front', '1. Machine Appearance'),
    ('img_175.png', 'Figure - Rear', '1. Machine Appearance'),
    ('img_137.png', 'Figure - Latera', '1. Machine Appearance'),

    # Ch 2. Safety
    ('img_186.jpeg', 'Figure - Emergency Stop Button', '2. Safety'),
    ('img_154.png', 'Figure - Signal lamps', '2. Safety'),

    # Ch 3. Startup
    ('img_102.png', 'Figure - Power on the installation', '3. Startup'),
    ('img_197.png', 'Figure - Control panel descriptions', '3. Control Panel'),

    # Ch 4. Main Screen
    ('img_107.png', 'Figure - Main Screen', '4. Main Screen'),

    # Ch 5. Managing models
    ('img_052.png', 'Figure - Create and set up the model (1)', '5. Managing Models'),
    ('img_055.png', 'Figure - Create and set up the model (2)', '5. Managing Models'),  # model detail view
    ('img_169.png', 'Figure - Pattern Settings', '5. Pattern Settings'),

    # Ch 6. Manage pallets / bars / spacers
    ('img_134.png', 'Figure - Pallet management settings (1)', '6. Pallet Management'),
    ('img_155.png', 'Figure - Pallet management settings (2)', '6. Pallet Management'),
    ('img_044.png', 'Figure - Bar management settings (1)', '6. Bar Management'),
    ('img_176.png', 'Figure - Bar management settings (2)', '6. Bar Management'),
    ('img_063.png', 'Figure - Spacer management settings (1)', '6. Spacer Management'),
    ('img_187.png', 'Figure - Spacer management settings (2)', '6. Spacer Management'),

    # Ch 7. Manage loads
    ('img_124.bmp', 'Figure - Manage loads', '7. Manage Loads'),
    ('img_022.png', 'Figure - Selecting a model and entering lots', '7. Load Settings'),

    # Ch 7-8. Pallet/Index/Task settings
    ('img_155.png', 'Figure - Pallet settings', '7. Pallet Settings'),  # duplicate - skip
    ('img_173.PNG', 'Figure - Setting up indexes', '7. Index Setup'),
    ('img_146.png', 'Figure - Set up the default task', '8. Preferences'),
    ('img_166.png', 'Figure - Setting up pallet actions', '8. Pallet Actions'),
    ('img_177.png', 'Figure - Rotary stacker', '8. Rotary Stacker'),

    # Ch 9. Working Location
    ('img_133.png', 'Figure - Schedule a teaching', '9. Work Location'),
    ('img_108.png', 'Figure - Setting the Position Offset', '9. Position Offset'),

    # Ch 10. Autopilot
    ('img_013.png', 'Figure - Reset', '10. Autopilot'),
    ('img_012.png', 'Figure - Pause', '10. Autopilot'),
    ('img_144.png', 'Figure - Stop a task', '10. Stop'),
    ('img_072.png', 'Figure - Running Location Compensation', '10. Calibration'),
    ('img_090.png', 'Figure - Image settings', '10. Image Settings'),
    ('img_156.png', 'Figure - Check supplies', '10. Check Supplies'),

    # Ch 11. Operator operation sequence
    ('img_176.png', 'Figure - Managing pallet', '11. Operator Sequence'),  # pallet grid Point 1
    ('img_187.png', 'Figure - Manage bars', '11. Operator Sequence'),      # pallet grid Point 2
    ('img_063.png', 'Figure - Manage spacers', '11. Operator Sequence'),    # reuse
    ('img_052.png', 'Figure - Create a Model File', '11. Operator Sequence'),
    ('img_022.png', 'Figure - Setting up loading', '11. Operator Sequence'),
    ('img_146.png', 'Figure - Preferences', '11. Operator Sequence'),
    ('img_159.png', 'Figure - Select Teaching', '11. Operator Sequence'),
    ('img_183.png', 'Figure - Start driving', '11. Start Driving'),
    ('img_203.png', 'Figure - Vision Settings', '11. Vision Settings'),

    # ──────────────────────────────────────────
    # Part 2: Maintenance Manual
    # ──────────────────────────────────────────

    # 12.1 Regulator filter
    ('img_036.png', 'Figure - Position of Air Utility', '12. Regulator Filter'),
    ('img_009.png', 'Figure - Position of Cock Push', '12. Regulator Filter'),

    # 12.2 Pallet Feeder (1) - Belt replacement
    ('img_147.png', 'Figure - Position of Tension Adjustment', '12. Pallet Feeder (1)'),
    ('img_037.png', 'Figure - Cover Position', '12. Pallet Feeder (1)'),

    # 12.3 Pallet Feeder (2) - Y-axis
    ('img_033.png', 'Figure - Position of Tension Block', '12. Pallet Feeder (2)'),
    ('img_114.png', 'Figure - Belt Clamp Block Position', '12. Pallet Feeder (2)'),
    ('img_025.png', 'Figure - Position of Belt', '12. Pallet Feeder (2)'),

    # 12.4 Pallet Feeder (3) - Z-axis
    ('img_126.png', 'Figure - Position of Pallet Feeder', '12. Pallet Feeder (3)'),
    ('img_075.png', 'Figure - Position of Cover', '12. Pallet Feeder (3)'),
    ('img_056.png', 'Figure - Positions of Tension Bolts', '12. Pallet Feeder (3)'),
    ('img_001.png', 'Figure - Position of Belt', '12. Pallet Feeder (3)'),

    # 12.5 Insert Transfer (1) - Grease
    ('img_029.png', 'Figure - Grease Injecting Block', '12. Insert Transfer (1)'),
    ('img_028.jpeg', 'Figure - Injector and Grease Injecting Block', '12. Insert Transfer (1)'),

    # 12.6 Insert Transfer (2) - Belt
    ('img_142.png', 'Figure - Position of Tension adjusting', '12. Insert Transfer (2)'),
    ('img_077.png', 'Figure - Position of Belt Clamp Block', '12. Insert Transfer (2)'),
    ('img_027.png', 'Figure - Belt Clamp Block', '12. Insert Transfer (2)'),

    # 12.7 Gripper Inspection (1) - Check
    ('img_032.png', 'Figure - Position of Pallet Gripper', '12. Gripper (1)'),
    ('img_065.png', 'Figure - Position of Rot Gripper', '12. Gripper (1)'),
    ('img_010.png', 'Figure - 2jaw Gripper', '12. Gripper (1)'),
    ('img_151.png', 'Figure - 3jaw Gripper', '12. Gripper (1)'),

    # 12.8 Gripper Inspection (2) - 2jaw Pin replacement
    ('img_058.jpeg', 'Figure - Precision Driver', '12. Gripper (2)'),
    ('img_164.jpeg', 'Figure - Remove Cover', '12. Gripper (2)'),
    ('img_141.jpeg', 'Figure - Remove the Fixing Pin', '12. Gripper (2)'),
    ('img_068.jpeg', 'Figure - Remove Grip Pin and Spring', '12. Gripper (2)'),

    # 12.9 Gripper Inspection (3) - 3jaw Pin replacement
    ('img_048.jpeg', 'Figure - Remove the Pin Holder', '12. Gripper (3)'),
    ('img_116.jpeg', 'Figure - Remove the Pin', '12. Gripper (3)'),
    ('img_101.jpeg', 'Figure - Pin Direction', '12. Gripper (3)'),
    ('img_201.jpeg', 'Figure - Reassemble Pin Holder', '12. Gripper (3)'),
    ('img_008.jpeg', 'Figure - Pin Height Check', '12. Gripper (3)'),

    # 12.10 Reversal Unit
    ('img_158.png', 'Figure - Reversal Position', '12. Reversal Unit'),
    ('img_131.png', 'Figure - Center Pin Plate Position', '12. Reversal Unit'),
    ('img_105.jpeg', 'Figure - Remove the Bolt', '12. Reversal Unit'),

    # 12.11 Skewer Index Turning Unit (1) - Grease
    ('img_076.png', 'Figure - Index Position', '12. Skewer Index (1)'),
    ('img_106.png', 'Figure - Nipple Position', '12. Skewer Index (1)'),

    # 12.12 Skewer Elevator Unit
    ('img_100.png', 'Figure - Position of the Skewer Elevator Gripper', '12. Skewer Elevator'),

    # 12.13 Robot Grease
    ('img_011.jpeg', 'Figure - Position of the Axis', '12. Robot Grease'),
    ('img_020.jpeg', 'Figure - Position of the Axis', '12. Robot Grease'),
    ('img_035.png', 'Figure - Down Looking Vision Robot', '12. Down Looking Vision'),
    ('img_202.png', 'Figure - Skewer Elevator Robot', '12. Skewer Elevator Robot'),

    # 13.2 Frequent Issues
    ('img_149.png', 'Figure - Pick Up Failure', '13. Troubleshooting'),
    ('img_059.PNG', 'Figure - 3jaw Gripper', '13. Troubleshooting'),
    ('img_159.png', 'Figure - Select Teaching', '13. Troubleshooting'),
]


def make_thumb(path: Path, max_size: int = 220) -> str:
    try:
        img = Image.open(path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buf, format='JPEG', quality=50)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"  [WARN] {path}: {e}")
        return ""


def main():
    print("=== CVD L&UL Machine (EN) — Verified Image Catalog ===\n")

    # Deduplicate mapping (remove duplicate img references, keep first)
    seen_imgs = set()
    unique_mapping = []
    for entry in MAPPING:
        fname, caption, section = entry
        key = f"{fname}_{caption}"  # Allow same image for different captions in troubleshooting
        if fname not in seen_imgs or section.startswith('13.'):
            seen_imgs.add(fname)
            unique_mapping.append(entry)
        else:
            print(f"  [SKIP duplicate] {fname} → {caption}")

    # Build cards grouped by section
    all_cards = []
    fig_idx = 0
    current_section = ''
    matched = 0
    missing = 0
    current_part = ''

    for fname, caption, section in unique_mapping:
        # Part header
        if section.startswith('12.') and current_part != 'Part 2':
            current_part = 'Part 2'
            all_cards.append('<h2 class="part-title">Part 2: Maintenance Manual</h2>')

        # Section header
        if section != current_section:
            current_section = section
            if not section.startswith('12.') or current_part == 'Part 2':
                if current_part != 'Part 2' and fig_idx == 0:
                    all_cards.append('<h2 class="part-title">Part 1: User Manual</h2>')
            all_cards.append(f'<h3 class="section-title">{section}</h3>')

        fig_idx += 1
        fpath = IMG_DIR / fname

        if not fpath.exists():
            print(f"  [MISS] {fname}")
            all_cards.append(f"""<div class="card missing">
  <div class="seq">Fig {fig_idx:02d}</div>
  <div class="placeholder">이미지 없음</div>
  <div class="cap">{caption}</div>
  <div class="fname">{fname}</div>
</div>""")
            missing += 1
            continue

        try:
            img = Image.open(fpath)
            w, h = img.size
        except:
            w, h = 0, 0

        thumb = make_thumb(fpath)
        if thumb:
            matched += 1
            all_cards.append(f"""<div class="card">
  <div class="seq">Fig {fig_idx:02d}</div>
  <img src="{thumb}" alt="{caption}"/>
  <div class="cap">{caption}</div>
  <div class="fname">{fname} ({w}x{h})</div>
</div>""")
        else:
            missing += 1
            all_cards.append(f"""<div class="card missing">
  <div class="seq">Fig {fig_idx:02d}</div>
  <div class="placeholder">썸네일 생성 실패</div>
  <div class="cap">{caption}</div>
  <div class="fname">{fname}</div>
</div>""")

    total = fig_idx

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>CVD L&UL Machine (EN) — Verified Image Catalog</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .info {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .part-title {{ color: #fff; font-size: 13pt; margin: 24px 0 12px; padding: 10px 16px;
    background: #1a237e; border-radius: 6px; grid-column: 1 / -1; }}
  .section-title {{ color: #1a237e; font-size: 11pt; margin: 16px 0 8px; padding: 6px 12px;
    background: #e8eaf6; border-left: 4px solid #1a237e; border-radius: 0 4px 4px 0; grid-column: 1 / -1; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
    transition: transform 0.15s; }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,.15); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9;
    border: 1px solid #eee; border-radius: 4px; }}
  .card.missing {{ border: 2px dashed #ff9800; }}
  .placeholder {{ height: 150px; display: flex; align-items: center; justify-content: center;
    background: #fafafa; color: #ccc; border: 1px dashed #ddd; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #1a237e; font-weight: 700; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #333; margin-top: 6px; line-height: 1.3; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .badge {{ display: inline-block; background: #4caf50; color: #fff; font-size: 8pt; padding: 2px 6px;
    border-radius: 3px; margin-left: 6px; }}
  .badge.warn {{ background: #ff9800; }}
</style>
</head>
<body>
<h1>CVD L&UL Machine (EN) — Manual Image Catalog
  <span class="badge">Verified Match</span>
</h1>
<div class="info">
  HAM-CVD_L_UL_Machine_User_Manual_en_v1.0 |
  {matched}/{total} figures matched |
  {missing} missing |
  수동 검증 매칭 (sequential 아님)
</div>
<div class="grid">
{''.join(all_cards)}
</div>
<div style="text-align:center; margin-top:24px; color:#888; font-size:11px;">
  Auto-generated image catalog — verified image-to-figure matching
</div>
</body>
</html>"""

    output = REPORTS / 'cvd_lul_en_이미지_카탈로그.html'
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\nSaved: {output} ({size_mb:.1f} MB)")
    print(f"Matched: {matched}/{total} | Missing: {missing}")


if __name__ == '__main__':
    main()
