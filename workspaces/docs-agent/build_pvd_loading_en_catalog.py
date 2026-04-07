"""
PVD Loading (EN) Manual Image Catalog Builder
- Extracts figure captions from parsed markdown
- Classifies and deduplicates images
- Generates HTML catalog with embedded base64 thumbnails
"""

import re
import os
import hashlib
import base64
import io
from pathlib import Path
from PIL import Image

# --- Config ---
PARSED_MD = r"C:\MES\wta-agents\data\wta_parsed\HAM-PVD_Loading_User_Manual_en_v1.2.md"
IMAGE_DIR = r"C:\MES\wta-agents\data\manual_images\HAM-PVD Loading User Manual en_v1.2"
OUTPUT_HTML = r"C:\MES\wta-agents\reports\pvd_loading_en_이미지_카탈로그.html"

THUMB_MAX = 220
THUMB_QUALITY = 50
MIN_FIG_W = 400
MIN_FIG_H = 300
HASH_SIZE = 32

# --- 1. Extract figure captions with section context ---
def extract_figures_and_sections(md_path: str) -> list[dict]:
    """Parse markdown for Figure lines and # headers, return ordered list of items."""
    items = []
    current_section = ""
    fig_pattern = re.compile(r"^Figure\s+(.+)", re.IGNORECASE)
    header_pattern = re.compile(r"^(#{1,4})\s+(.+)")

    with open(md_path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip()
            hm = header_pattern.match(line)
            if hm:
                level = len(hm.group(1))
                title = hm.group(2).strip()
                # Track major section changes (level 1-2 with numbered prefix)
                if level <= 2 and re.match(r"\d+\.", title):
                    current_section = title

            fm = fig_pattern.match(line)
            if fm:
                caption = fm.group(1).strip()
                items.append({
                    "type": "figure",
                    "caption": f"Figure {caption}",
                    "section": current_section,
                    "lineno": lineno,
                })

    return items


def detect_parts(items: list[dict]) -> list[dict]:
    """Detect User Manual / Maintenance Manual divide by line number gap."""
    if not items:
        return items

    # Find the biggest gap between consecutive figures
    max_gap = 0
    max_gap_idx = -1
    for i in range(1, len(items)):
        gap = items[i]["lineno"] - items[i - 1]["lineno"]
        if gap > max_gap:
            max_gap = gap
            max_gap_idx = i

    # If there's a big gap (>200 lines), split into two parts
    if max_gap > 200 and max_gap_idx > 0:
        part1_section = items[max_gap_idx - 1].get("section", "")
        part2_section = items[max_gap_idx].get("section", "")

        # Insert part dividers
        result = []
        result.append({"type": "part_header", "title": "Part 1: User Manual (Ch.1-12)"})
        for item in items[:max_gap_idx]:
            result.append(item)
        result.append({"type": "part_header", "title": "Part 2: Maintenance Manual (Ch.13-14)"})
        for item in items[max_gap_idx:]:
            result.append(item)
        return result

    return items


# --- 2. Image classification and deduplication ---
def pixel_hash(img: Image.Image) -> str:
    """Compute MD5 of resized RGB bytes for dedup."""
    small = img.resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS).convert("RGB")
    return hashlib.md5(small.tobytes()).hexdigest()


def classify_image(w: int, h: int) -> str:
    if w >= MIN_FIG_W and h >= MIN_FIG_H:
        return "FIGURE"
    elif w < 100 and h < 100:
        return "ICON"
    else:
        return "SMALL"


def get_unique_figure_images(image_dir: str) -> list[dict]:
    """Get FIGURE-sized images, deduplicated, in natural sort order."""
    exts = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
    files = [f for f in os.listdir(image_dir) if any(f.lower().endswith(e) for e in exts)]
    files.sort(key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', x)])

    seen_hashes: set[str] = set()
    results = []

    for fname in files:
        fpath = os.path.join(image_dir, fname)
        try:
            img = Image.open(fpath)
            w, h = img.size
            cls = classify_image(w, h)

            if cls != "FIGURE":
                continue

            ph = pixel_hash(img)
            if ph in seen_hashes:
                continue
            seen_hashes.add(ph)

            results.append({
                "filename": fname,
                "path": fpath,
                "width": w,
                "height": h,
                "hash": ph,
            })
        except Exception as e:
            print(f"  [WARN] {fname}: {e}")

    return results


def make_thumbnail_base64(img_path: str) -> str:
    """Create JPEG thumbnail and return base64 string."""
    img = Image.open(img_path).convert("RGB")
    img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=THUMB_QUALITY)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --- 3. Generate HTML catalog ---
def generate_html(matched: list[dict], output_path: str) -> None:
    cards_html = []

    for item in matched:
        if item["type"] == "part_header":
            cards_html.append(f"""
        <div class="part-header">
            <h2>{item['title']}</h2>
        </div>""")
            continue

        if item["type"] == "section_header":
            cards_html.append(f"""
        <div class="section-header">
            <h3>{item['title']}</h3>
        </div>""")
            continue

        # Image card
        b64 = item.get("thumb_b64", "")
        caption = item.get("caption", "")
        fname = item.get("filename", "")
        dims = item.get("dims", "")

        cards_html.append(f"""
        <div class="card">
            <div class="img-wrap">
                <img src="data:image/jpeg;base64,{b64}" alt="{caption}" loading="lazy" />
            </div>
            <div class="caption">{caption}</div>
            <div class="meta">{fname}<br/>{dims}</div>
        </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>PVD Loading (EN) — Manual Image Catalog</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    background: #f5f5f5;
    color: #333;
    padding: 24px;
}}
h1 {{
    color: #1a237e;
    text-align: center;
    font-size: 28px;
    margin-bottom: 8px;
}}
.subtitle {{
    text-align: center;
    color: #666;
    font-size: 14px;
    margin-bottom: 32px;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    max-width: 1400px;
    margin: 0 auto;
}}
.part-header {{
    grid-column: 1 / -1;
    background: #1a237e;
    color: #fff;
    padding: 14px 20px;
    border-radius: 8px;
    margin-top: 16px;
}}
.part-header h2 {{
    font-size: 20px;
    font-weight: 700;
}}
.section-header {{
    grid-column: 1 / -1;
    border-bottom: 2px solid #1a237e;
    padding: 8px 4px 4px;
    margin-top: 8px;
}}
.section-header h3 {{
    font-size: 15px;
    color: #1a237e;
    font-weight: 600;
}}
.card {{
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: transform 0.15s;
}}
.card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}
.img-wrap {{
    background: #fafafa;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    min-height: 160px;
}}
.img-wrap img {{
    max-width: 100%;
    max-height: 200px;
    object-fit: contain;
}}
.caption {{
    padding: 8px 10px 2px;
    font-size: 12.5px;
    font-weight: 600;
    color: #1a237e;
    line-height: 1.4;
}}
.meta {{
    padding: 2px 10px 8px;
    font-size: 11px;
    color: #999;
}}
.stats {{
    text-align: center;
    margin-top: 24px;
    padding: 12px;
    color: #888;
    font-size: 13px;
}}
</style>
</head>
<body>
<h1>PVD Loading (EN) — Manual Image Catalog</h1>
<div class="subtitle">HAM-PVD_Loading_User_Manual_en_v1.2 | Auto-generated Image Catalog</div>
<div class="grid">
{"".join(cards_html)}
</div>
<div class="stats">
    Total images: {sum(1 for i in matched if i['type'] == 'image')} |
    Total captions: {sum(1 for i in matched if i['type'] == 'image' and i.get('caption'))}
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# --- Main ---
def main():
    print("=== PVD Loading (EN) Image Catalog Builder ===\n")

    # Step 1: Extract figure captions
    print("[1/4] Extracting figure captions from parsed markdown...")
    items = extract_figures_and_sections(PARSED_MD)
    print(f"  Found {len(items)} figure captions")

    # Step 2: Detect part divide
    print("[2/4] Detecting manual parts...")
    items_with_parts = detect_parts(items)
    part_count = sum(1 for i in items_with_parts if i.get("type") == "part_header")
    print(f"  Detected {part_count} parts")

    # Step 3: Get unique FIGURE images
    print("[3/4] Scanning and classifying images...")
    images = get_unique_figure_images(IMAGE_DIR)
    print(f"  Total image files: {len(os.listdir(IMAGE_DIR))}")
    print(f"  Unique FIGURE images: {len(images)}")

    # Step 4: Sequential match images to captions and build output
    print("[4/4] Matching images to captions and generating HTML...")

    # Build output list with section tracking
    output: list[dict] = []
    img_idx = 0
    last_section = ""

    for item in items_with_parts:
        if item["type"] == "part_header":
            output.append({"type": "part_header", "title": item["title"]})
            last_section = ""
            continue

        if item["type"] == "figure":
            # Insert section header if section changed
            section = item.get("section", "")
            if section and section != last_section:
                output.append({"type": "section_header", "title": section})
                last_section = section

            # Match to next available image
            if img_idx < len(images):
                img = images[img_idx]
                thumb_b64 = make_thumbnail_base64(img["path"])
                output.append({
                    "type": "image",
                    "caption": item["caption"],
                    "filename": img["filename"],
                    "dims": f"{img['width']}x{img['height']}",
                    "thumb_b64": thumb_b64,
                })
                img_idx += 1
            else:
                # No more images, add caption-only
                output.append({
                    "type": "image",
                    "caption": item["caption"],
                    "filename": "(no image)",
                    "dims": "",
                    "thumb_b64": "",
                })

    generate_html(output, OUTPUT_HTML)

    matched_count = sum(1 for o in output if o["type"] == "image" and o.get("thumb_b64"))
    unmatched_captions = sum(1 for o in output if o["type"] == "image" and not o.get("thumb_b64"))
    unused_images = len(images) - img_idx

    print(f"\n=== Results ===")
    print(f"  Figure captions: {len(items)}")
    print(f"  Unique FIGURE images: {len(images)}")
    print(f"  Matched pairs: {matched_count}")
    print(f"  Unmatched captions: {unmatched_captions}")
    print(f"  Unused images: {unused_images}")
    print(f"  Output: {OUTPUT_HTML}")
    print("  Done!")


if __name__ == "__main__":
    main()
