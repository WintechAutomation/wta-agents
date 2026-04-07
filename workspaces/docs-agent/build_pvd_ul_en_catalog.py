"""
PVD Unloading (EN) - 매뉴얼 텍스트 기반 이미지 카탈로그
Figure captions from parsed text, matched to images in DOCX extraction order
Deduplicates images by pixel hash, separates User Manual / Maintenance Manual
"""
import re
import base64
import hashlib
import io
from pathlib import Path
from PIL import Image

IMG_DIR = Path(r'C:\MES\wta-agents\data\manual_images\HAM-PVD_Unloading_User_Manual_en_v1.3')
PARSED = Path(r'C:\MES\wta-agents\data\wta_parsed\HAM-PVD_Unloading_User_Manual_en_v1.3.md')
REPORTS = Path(r'C:\MES\wta-agents\reports')

# Figure size threshold
MIN_W, MIN_H = 400, 300

# Section split: line gap between user manual (ch1-11) and maintenance (ch13+)
# User manual figures end at line ~945, maintenance starts at ~1393
SECTION_SPLIT_LINE = 1100


def extract_figures(md_path: Path) -> list[tuple[int, str, str]]:
    """Extract (line_num, caption, section) from parsed markdown"""
    text = md_path.read_text(encoding='utf-8', errors='replace')
    lines = text.split('\n')

    figures = []
    current_section = ''
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#'):
            current_section = stripped.lstrip('#').strip()
        m = re.match(r'^Figure\s+(\d+-\d+)\s+(.*)', stripped)
        if m:
            fig_num = m.group(1)
            caption = m.group(2).strip()
            full_caption = f"Figure {fig_num} {caption}" if caption else f"Figure {fig_num}"
            figures.append((i + 1, full_caption, current_section))
    return figures


def natural_sort_key(p: Path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', p.stem)]


def img_pixel_hash(path: Path) -> str:
    """Fast pixel-based hash for duplicate detection"""
    try:
        img = Image.open(path)
        img = img.resize((32, 32), Image.LANCZOS).convert('RGB')
        return hashlib.md5(img.tobytes()).hexdigest()
    except Exception:
        return ''


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
    except Exception:
        return ""


def main():
    # 1. Extract figure captions
    figures = extract_figures(PARSED)
    print(f"Figure captions: {len(figures)}")

    # Split into User Manual and Maintenance Manual by line number gap
    user_figs = [(ln, cap, sec) for ln, cap, sec in figures if ln < SECTION_SPLIT_LINE]
    maint_figs = [(ln, cap, sec) for ln, cap, sec in figures if ln >= SECTION_SPLIT_LINE]
    print(f"  User Manual: {len(user_figs)} figures")
    print(f"  Maintenance Manual: {len(maint_figs)} figures")

    # 2. Get all images sorted by extraction order
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    all_imgs = sorted(
        [f for f in IMG_DIR.iterdir() if f.is_file() and f.suffix.lower() in exts],
        key=natural_sort_key
    )
    print(f"\nTotal images: {len(all_imgs)}")

    # 3. Classify and deduplicate
    seen_hashes = {}
    figure_imgs = []  # (path, w, h, is_duplicate, orig_name)
    small_imgs = []
    icon_imgs = []

    for f in all_imgs:
        try:
            img = Image.open(f)
            w, h = img.size
        except Exception:
            continue

        if w >= MIN_W and h >= MIN_H:
            phash = img_pixel_hash(f)
            if phash in seen_hashes:
                figure_imgs.append((f, w, h, True, seen_hashes[phash]))
            else:
                seen_hashes[phash] = f.name
                figure_imgs.append((f, w, h, False, ''))
        elif w < 150 or h < 100:
            icon_imgs.append((f, w, h))
        else:
            small_imgs.append((f, w, h))

    unique_figs = [x for x in figure_imgs if not x[3]]
    dup_figs = [x for x in figure_imgs if x[3]]
    print(f"FIGURE images: {len(figure_imgs)} (unique: {len(unique_figs)}, duplicates: {len(dup_figs)})")
    print(f"SMALL: {len(small_imgs)}, ICON: {len(icon_imgs)}")

    # 4. Build cards - sequential match unique figures to captions
    all_cards = []
    fig_idx = 0
    total_matched = 0

    # --- User Manual Section ---
    all_cards.append('<h2 class="part-title">Part 1: User Manual</h2>')
    um_figures_available = unique_figs[:len(user_figs)]

    for i, (ln, cap, sec) in enumerate(user_figs):
        fig_idx += 1
        if i < len(um_figures_available):
            path, w, h, _, _ = um_figures_available[i]
            thumb = make_thumb(path)
            total_matched += 1
            card = f"""<div class="card">
  <div class="seq">Fig {fig_idx:02d}</div>
  <img src="{thumb}" alt="{cap}"/>
  <div class="cap">{cap}</div>
  <div class="fname">{path.name} ({w}x{h})</div>
  <div class="section">{sec}</div>
</div>"""
        else:
            card = f"""<div class="card missing">
  <div class="seq">Fig {fig_idx:02d}</div>
  <div class="placeholder">이미지 없음</div>
  <div class="cap">{cap}</div>
  <div class="section">{sec}</div>
</div>"""
        all_cards.append(card)

    # --- Maintenance Manual Section ---
    all_cards.append('<h2 class="part-title">Part 2: Maintenance Manual</h2>')
    mm_figures_available = unique_figs[len(user_figs):]

    for i, (ln, cap, sec) in enumerate(maint_figs):
        fig_idx += 1
        if i < len(mm_figures_available):
            path, w, h, _, _ = mm_figures_available[i]
            thumb = make_thumb(path)
            total_matched += 1
            card = f"""<div class="card">
  <div class="seq">Fig {fig_idx:02d}</div>
  <img src="{thumb}" alt="{cap}"/>
  <div class="cap">{cap}</div>
  <div class="fname">{path.name} ({w}x{h})</div>
  <div class="section">{sec}</div>
</div>"""
        else:
            card = f"""<div class="card missing">
  <div class="seq">Fig {fig_idx:02d}</div>
  <div class="placeholder">이미지 없음</div>
  <div class="cap">{cap}</div>
  <div class="section">{sec}</div>
</div>"""
        all_cards.append(card)

    # Remaining unmatched images
    matched_count = min(len(user_figs), len(um_figures_available)) + min(len(maint_figs), len(mm_figures_available))
    remaining = unique_figs[matched_count:]

    if remaining:
        all_cards.append(f'<h2 class="part-title">미매칭 이미지 ({len(remaining)}개)</h2>')
        for path, w, h, _, _ in remaining:
            thumb = make_thumb(path)
            all_cards.append(f"""<div class="card unmatched">
  <img src="{thumb}" alt="{path.name}"/>
  <div class="fname">{path.name} ({w}x{h})</div>
</div>""")

    # Duplicate images info
    if dup_figs:
        all_cards.append(f'<h2 class="part-title">중복 이미지 ({len(dup_figs)}개)</h2>')
        for path, w, h, _, orig in dup_figs:
            thumb = make_thumb(path, 120)
            all_cards.append(f"""<div class="card dup">
  <img src="{thumb}" alt="{path.name}"/>
  <div class="fname">{path.name} → {orig}</div>
</div>""")

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>PVD Unloading (EN) — Manual Image Catalog</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .info {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .part-title {{ color: #1a237e; font-size: 13pt; margin: 24px 0 12px; padding: 8px 16px; background: #e8eaf6; border-left: 4px solid #1a237e; border-radius: 0 4px 4px 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .card.missing {{ border: 2px dashed #ff9800; }}
  .card.unmatched {{ border: 1px solid #ccc; opacity: 0.7; }}
  .card.dup {{ border: 1px dashed #9e9e9e; opacity: 0.6; }}
  .placeholder {{ height: 150px; display: flex; align-items: center; justify-content: center; background: #fafafa; color: #ccc; border: 1px dashed #ddd; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #1a237e; font-weight: 700; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #333; margin-top: 6px; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .section {{ font-size: 7pt; color: #aaa; margin-top: 1px; }}
</style>
</head>
<body>
<h1>PVD Unloading (EN) — Manual Image Catalog</h1>
<div class="info">
  {len(figures)} Figure references | {len(unique_figs)} unique images | {len(dup_figs)} duplicates |
  User Manual {len(user_figs)} figs | Maintenance Manual {len(maint_figs)} figs
</div>
<div class="grid">
{''.join(all_cards)}
</div>
</body>
</html>"""

    output = REPORTS / 'pvd_unloading_en_이미지_카탈로그.html'
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\nSaved: {output} ({size_mb:.1f} MB)")
    print(f"Matched: {total_matched}/{len(figures)}")


if __name__ == '__main__':
    main()
