"""
Press Handler Manual Image Catalog Builder
- Extracts section headers from parsed markdown
- Classifies and deduplicates images
- Generates HTML catalog with base64 thumbnails
"""

import os
import re
import hashlib
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image
from datetime import datetime

# --- Config ---
PARSED_MD = r"C:\MES\wta-agents\data\wta_parsed\1._User_Manual_Press_Handler_MC.md"
IMAGE_DIR = r"C:\MES\wta-agents\data\manual_images\PressHandler"
OUTPUT_HTML = r"C:\MES\wta-agents\reports\press_handler_이미지_카탈로그.html"

MIN_FIG_W = 400
MIN_FIG_H = 300
THUMB_MAX = 220
THUMB_QUALITY = 50
HASH_SIZE = 32

PRIMARY_COLOR = "#1a237e"
FONT_FAMILY = "'Malgun Gothic', 'Pretendard Variable', sans-serif"


def extract_sections(md_path: str) -> list[dict]:
    """Extract major sections and subsections from the parsed markdown."""
    sections = []
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Filter to numbered section headers like "## 1. xxx", "## 1.1 xxx", "## 4.2.1 xxx"
    # Also include circled-number items like "## ① xxx"
    # Skip generic ones like "## 注意 !", "## 参考事项", "## 危险 !"
    skip_patterns = {
        "注意", "参考事项", "危险", "禁止", "触电 警告",
        "根据设备规格不同部分内容可略过",
    }

    for i, line in enumerate(lines):
        line = line.rstrip()
        if not line.startswith("## "):
            continue
        title = line[3:].strip()

        # Skip generic warning/note headers
        skip = False
        for pat in skip_patterns:
            if title.startswith(pat):
                skip = True
                break
        if skip:
            continue

        # Determine if this is a major section (numbered like "1.", "2.", etc.)
        is_major = bool(re.match(r"^\d+\.\s", title))
        # Subsection: "1.1", "4.2.1", etc.
        is_sub = bool(re.match(r"^\d+\.\d", title))
        # Circled number: ①②③...
        is_circled = bool(re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩]", title))
        # Named sub-item (no number prefix but meaningful)
        is_named = not is_major and not is_sub and not is_circled

        section_type = "major" if is_major else ("sub" if is_sub else ("item" if is_circled else "named"))

        sections.append({
            "line": i + 1,
            "title": title,
            "type": section_type,
        })

    return sections


def natural_sort_key(filename: str):
    """Sort key for natural ordering of filenames like img_001, img_002, ..."""
    parts = re.split(r"(\d+)", filename)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def classify_and_dedup_images(image_dir: str) -> dict:
    """
    Classify images into FIGURE/SMALL/ICON and deduplicate by pixel hash.
    Returns dict with 'figures', 'small', 'icon' lists and 'stats'.
    """
    files = [f for f in os.listdir(image_dir)
             if f.lower().startswith("img_") and f.lower().endswith((".png", ".jpg", ".jpeg"))]
    files.sort(key=natural_sort_key)

    figures = []
    small = []
    icons = []
    seen_hashes = set()
    dup_count = 0

    for fname in files:
        fpath = os.path.join(image_dir, fname)
        try:
            img = Image.open(fpath)
            w, h = img.size
        except Exception:
            continue

        # Pixel-hash dedup: resize to 32x32, md5 of RGB bytes
        try:
            thumb = img.convert("RGB").resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS)
            pixel_hash = hashlib.md5(thumb.tobytes()).hexdigest()
        except Exception:
            pixel_hash = hashlib.md5(fname.encode()).hexdigest()

        if pixel_hash in seen_hashes:
            dup_count += 1
            continue
        seen_hashes.add(pixel_hash)

        entry = {"filename": fname, "path": fpath, "width": w, "height": h}

        if w >= MIN_FIG_W and h >= MIN_FIG_H:
            figures.append(entry)
        elif w >= 100 or h >= 100:
            small.append(entry)
        else:
            icons.append(entry)

    # Also include page_*_full.png as full-page images (separate category)
    page_files = [f for f in os.listdir(image_dir)
                  if f.lower().startswith("page_") and f.lower().endswith(".png")]
    page_files.sort(key=natural_sort_key)

    stats = {
        "total_img_files": len(files),
        "duplicates_removed": dup_count,
        "unique_figures": len(figures),
        "unique_small": len(small),
        "unique_icons": len(icons),
        "page_images": len(page_files),
    }

    return {"figures": figures, "small": small, "icons": icons, "stats": stats}


def make_thumbnail_base64(image_path: str, max_size: int = THUMB_MAX, quality: int = THUMB_QUALITY) -> str:
    """Create a base64-encoded JPEG thumbnail."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def match_figures_to_sections(figures: list[dict], sections: list[dict]) -> list[dict]:
    """
    Sequential-match unique FIGURE images to section headers.
    Returns list of dicts with 'section' and 'image' keys.
    """
    # Use major and sub sections as group headers, items as captions
    catalog_entries = []

    # Build a flat list of meaningful sections (skip pure "named" generic ones)
    meaningful = [s for s in sections if s["type"] in ("major", "sub", "item")]

    fig_idx = 0
    for sec in meaningful:
        entry = {"section": sec, "images": []}
        catalog_entries.append(entry)

    # Distribute figures across sections proportionally
    # Simple approach: assign figures sequentially to sections
    if not meaningful or not figures:
        return catalog_entries

    # Calculate approximate figures per section
    figs_per_section = len(figures) / max(len(meaningful), 1)

    for i, entry in enumerate(catalog_entries):
        start = int(i * figs_per_section)
        end = int((i + 1) * figs_per_section)
        if i == len(catalog_entries) - 1:
            end = len(figures)
        entry["images"] = figures[start:end]

    return catalog_entries


def generate_html(catalog: list[dict], stats: dict) -> str:
    """Generate the HTML catalog."""
    now = datetime.now().strftime("%Y-%m-%d")

    cards_html = []
    img_counter = 0

    for entry in catalog:
        sec = entry["section"]
        images = entry["images"]

        if not images and sec["type"] != "major":
            continue

        # Section header
        if sec["type"] == "major":
            cards_html.append(f'''
            <div class="section-header major">
                <h2>{sec["title"]}</h2>
            </div>''')
        elif sec["type"] == "sub":
            cards_html.append(f'''
            <div class="section-header sub">
                <h3>{sec["title"]}</h3>
            </div>''')
        elif sec["type"] == "item":
            cards_html.append(f'''
            <div class="section-header item">
                <h4>{sec["title"]}</h4>
            </div>''')

        for img_info in images:
            img_counter += 1
            b64 = make_thumbnail_base64(img_info["path"])
            cards_html.append(f'''
            <div class="card">
                <div class="thumb-wrap">
                    <img src="data:image/jpeg;base64,{b64}" alt="{img_info['filename']}" loading="lazy"/>
                </div>
                <div class="card-label">
                    <span class="img-num">#{img_counter:03d}</span>
                    <span class="img-name">{img_info['filename']}</span>
                    <span class="img-size">{img_info['width']}x{img_info['height']}</span>
                </div>
            </div>''')

    cards_block = "\n".join(cards_html)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Press Handler — Manual Image Catalog</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: {FONT_FAMILY};
    background: #f5f5f5;
    color: #333;
}}
.header {{
    background: {PRIMARY_COLOR};
    color: #fff;
    padding: 32px 40px;
}}
.header h1 {{
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 8px;
}}
.header .sub {{
    font-size: 14px;
    opacity: 0.85;
}}
.stats {{
    display: flex;
    gap: 24px;
    padding: 16px 40px;
    background: #fff;
    border-bottom: 2px solid {PRIMARY_COLOR};
    flex-wrap: wrap;
}}
.stat-item {{
    text-align: center;
}}
.stat-item .val {{
    font-size: 24px;
    font-weight: 700;
    color: {PRIMARY_COLOR};
}}
.stat-item .lbl {{
    font-size: 12px;
    color: #666;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    padding: 24px 40px;
    max-width: 1600px;
    margin: 0 auto;
}}
.section-header {{
    grid-column: 1 / -1;
    padding: 12px 0 4px;
    border-bottom: 2px solid {PRIMARY_COLOR};
    margin-top: 8px;
}}
.section-header.major {{
    border-bottom-width: 3px;
    margin-top: 24px;
}}
.section-header.major h2 {{
    font-size: 22px;
    color: {PRIMARY_COLOR};
}}
.section-header.sub h3 {{
    font-size: 17px;
    color: #283593;
}}
.section-header.item h4 {{
    font-size: 15px;
    color: #3949ab;
    font-weight: 600;
}}
.card {{
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    transition: transform 0.15s, box-shadow 0.15s;
}}
.card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}
.thumb-wrap {{
    display: flex;
    align-items: center;
    justify-content: center;
    height: 180px;
    background: #fafafa;
    padding: 8px;
}}
.thumb-wrap img {{
    max-width: 100%;
    max-height: 164px;
    object-fit: contain;
}}
.card-label {{
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    border-top: 1px solid #eee;
}}
.img-num {{
    font-size: 13px;
    font-weight: 700;
    color: {PRIMARY_COLOR};
}}
.img-name {{
    font-size: 11px;
    color: #666;
    word-break: break-all;
}}
.img-size {{
    font-size: 11px;
    color: #999;
}}
.footer {{
    text-align: center;
    padding: 24px;
    color: #999;
    font-size: 12px;
    border-top: 1px solid #eee;
    margin-top: 24px;
}}
</style>
</head>
<body>
<div class="header">
    <h1>Press Handler — Manual Image Catalog</h1>
    <div class="sub">HP3-L12 去毛刺装盘机器人 | (주)윈텍오토메이션 생산관리팀 (AI운영팀) | {now}</div>
</div>
<div class="stats">
    <div class="stat-item"><div class="val">{stats['total_img_files']}</div><div class="lbl">Total Images</div></div>
    <div class="stat-item"><div class="val">{stats['duplicates_removed']}</div><div class="lbl">Duplicates Removed</div></div>
    <div class="stat-item"><div class="val">{stats['unique_figures']}</div><div class="lbl">FIGURE (≥400x300)</div></div>
    <div class="stat-item"><div class="val">{stats['unique_small']}</div><div class="lbl">SMALL</div></div>
    <div class="stat-item"><div class="val">{stats['unique_icons']}</div><div class="lbl">ICON</div></div>
    <div class="stat-item"><div class="val">{stats['page_images']}</div><div class="lbl">Full Pages</div></div>
</div>
<div class="grid">
{cards_block}
</div>
<div class="footer">
    Auto-generated by docs-agent | Press Handler User Manual (Chinese) | {now}
</div>
</body>
</html>"""
    return html


def main():
    print("=== Press Handler Image Catalog Builder ===")

    # 1. Extract sections
    print("\n[1] Extracting sections from parsed markdown...")
    sections = extract_sections(PARSED_MD)
    major = [s for s in sections if s["type"] == "major"]
    sub = [s for s in sections if s["type"] == "sub"]
    item = [s for s in sections if s["type"] == "item"]
    named = [s for s in sections if s["type"] == "named"]
    print(f"    Major sections: {len(major)}")
    print(f"    Subsections:    {len(sub)}")
    print(f"    Items (circled): {len(item)}")
    print(f"    Named sections: {len(named)}")
    print(f"    Total:          {len(sections)}")

    # 2. Classify and deduplicate images
    print("\n[2] Classifying and deduplicating images...")
    result = classify_and_dedup_images(IMAGE_DIR)
    stats = result["stats"]
    for k, v in stats.items():
        print(f"    {k}: {v}")

    # 3. Match figures to sections
    print("\n[3] Matching figures to sections...")
    catalog = match_figures_to_sections(result["figures"], sections)
    entries_with_images = sum(1 for e in catalog if e["images"])
    print(f"    Sections with images: {entries_with_images}")
    print(f"    Total figures mapped: {sum(len(e['images']) for e in catalog)}")

    # 4. Generate HTML
    print("\n[4] Generating HTML catalog...")
    html = generate_html(catalog, stats)
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    file_size_kb = os.path.getsize(OUTPUT_HTML) / 1024
    print(f"    Output: {OUTPUT_HTML}")
    print(f"    Size:   {file_size_kb:.0f} KB")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
