"""
YG1 CVD Manual - Image Catalog Builder
Extracts section headers from parsed markdown, classifies and deduplicates images,
then generates an HTML catalog with embedded base64 thumbnails.
"""

import re
import os
import hashlib
import base64
from io import BytesIO
from pathlib import Path

# PIL for image processing
from PIL import Image

# --- Configuration ---
PARSED_MD = r"C:\MES\wta-agents\data\wta_parsed\WT1724_YG1_CVD_Manual.md"
IMAGE_DIR = r"C:\MES\wta-agents\data\manual_images\[WT1724]YG1  CVD 매뉴얼"
OUTPUT_HTML = r"C:\MES\wta-agents\reports\yg1_cvd_이미지_카탈로그.html"

# Image classification thresholds
FIGURE_MIN_W = 400
FIGURE_MIN_H = 300

# Thumbnail settings
THUMB_MAX_PX = 220
THUMB_QUALITY = 50

# Dedup hash size
HASH_SIZE = 32


def extract_sections(md_path: str) -> list[str]:
    """Extract section headers and step descriptions from parsed markdown.

    Skips the TOC (Index) block and extracts from body content only.
    """
    captions: list[str] = []
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Known standalone section titles
    section_titles = {
        "머리말", "설비 외형", "안전 참고사항", "시운전", "기본 조작", "메인 화면",
        "모델 관리", "팔레트 관리", "코팅 트레이 관리", "적재 관리", "환경 설정",
        "작업 위치", "자동 운전", "문제 해결", "응용프로그램 매뉴얼", "유지 보수", "부록",
        "조작 패널 설명", "위치별 기능", "메인화면 구조", "원점 복귀", "일시정지", "작업 정지",
        "카메라 위치 보정", "위치 보정의 실행", "그리퍼 보정 진행", "에러 일람",
        "모션제어기 기본 조작 방법", "보수 점검 요령", "보수 부품",
        "카메라 이미지 설정", "그리퍼 이미지 설정", "비전세팅",
        "트레이 관리", "팔레트 원점세팅", "모델파일 생성", "적재설정", "티칭선택", "운전시작",
        "트레이 각도검출 세팅", "제품 촬상", "트래커 설정", "마스크 편집",
        "설비 전원 켜기", "설비 전원 끄기", "설비 재 가동", "비상정지 버튼",
        "안전 도어 및 작업 도어", "시그널 램프", "사용설명서",
        "사용설명서 관련 참고사항", "설비 표식", "설비 명판",
        "조작 인력 관련 기본 지침", "설비 적용 범위",
        "규정 준수 사용 및 책임 배제", "설비 부착 경고 및 안전 참고사항",
        "전기 위험", "시각 광선", "분진, 증기, 연기", "공압", "구동 액츄에이터", "서보 축",
        "설비의 운반 및 취급", "조립 및 설치", "공압 설치", "전기 설치",
        "설비 전원 켜기 / 끄기", "설비 재 가동", "티칭 예약", "위치 Offset 설정",
        "작업 세팅 순서 및 조작", "제어기 연결상태 확인", "모션 매니져의 실행",
        "상시/정기 점검표",
    }

    # Skip the TOC block: find the line "머리말" in body (after TOC ends)
    in_toc = True
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # TOC lines contain tabs with page numbers like "1.\t머리말\t4"
        # Skip until we reach the body (first "머리말" without trailing page number)
        if in_toc:
            # Body starts at line containing just "머리말" (the actual section header)
            if stripped == "머리말":
                in_toc = False
                captions.append("머리말")
            continue

        # Match markdown headers
        m = re.match(r'^#{1,6}\s+(.+)', stripped)
        if m:
            captions.append(m.group(1).strip())
            continue

        # Match numbered section patterns: "1.1 사용설명서" or "14.8 트레이 각도검출 세팅"
        # Must not contain tabs (to avoid TOC remnants)
        m = re.match(r'^(\d+\.[\d\.]*)\s+(\S.+)$', stripped)
        if m and '\t' not in stripped:
            text = m.group(2).strip()
            captions.append(f"{m.group(1)} {text}")
            continue

        # Match known standalone section titles
        if stripped in section_titles:
            captions.append(stripped)
            continue

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in captions:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def natural_sort_key(filename: str):
    """Sort key for natural ordering of filenames like img_001.png, img_002.png."""
    parts = re.split(r'(\d+)', filename)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def classify_and_dedup_images(image_dir: str) -> list[dict]:
    """
    Classify images by size, deduplicate by pixel hash.
    Returns list of dicts with path, width, height, category for FIGURE images.
    """
    supported_ext = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    files = sorted(
        [f for f in os.listdir(image_dir)
         if Path(f).suffix.lower() in supported_ext],
        key=natural_sort_key
    )

    seen_hashes: set[str] = set()
    results: list[dict] = []
    stats = {"total": 0, "figure": 0, "small": 0, "icon": 0, "duplicate": 0, "error": 0}

    for fname in files:
        fpath = os.path.join(image_dir, fname)
        stats["total"] += 1
        try:
            with Image.open(fpath) as img:
                img = img.convert("RGB")
                w, h = img.size

                # Classify
                if w >= FIGURE_MIN_W and h >= FIGURE_MIN_H:
                    category = "FIGURE"
                elif w >= 100 or h >= 100:
                    category = "SMALL"
                else:
                    category = "ICON"

                # Pixel-hash dedup (resize to 32x32, md5 of RGB bytes)
                thumb = img.resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS)
                pixel_hash = hashlib.md5(thumb.tobytes()).hexdigest()

                if pixel_hash in seen_hashes:
                    stats["duplicate"] += 1
                    continue
                seen_hashes.add(pixel_hash)

                if category == "FIGURE":
                    stats["figure"] += 1
                    results.append({
                        "path": fpath,
                        "filename": fname,
                        "width": w,
                        "height": h,
                        "category": category,
                    })
                elif category == "SMALL":
                    stats["small"] += 1
                elif category == "ICON":
                    stats["icon"] += 1

        except Exception as e:
            stats["error"] += 1
            print(f"  [SKIP] {fname}: {e}")

    return results, stats


def make_thumbnail_base64(img_path: str) -> str:
    """Create a base64-encoded JPEG thumbnail."""
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        img.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=THUMB_QUALITY)
        return base64.b64encode(buf.getvalue()).decode("ascii")


def generate_html(figures: list[dict], captions: list[str], output_path: str) -> int:
    """Generate HTML catalog. Returns matched count."""
    matched = min(len(figures), len(captions))

    cards_html = []
    for i, fig in enumerate(figures):
        caption = captions[i] if i < len(captions) else f"Image {i+1}"
        b64 = make_thumbnail_base64(fig["path"])
        cards_html.append(f"""
      <div class="card">
        <div class="img-wrap">
          <img src="data:image/jpeg;base64,{b64}" alt="{caption}" loading="lazy">
        </div>
        <div class="caption">
          <span class="idx">#{i+1}</span>
          <span class="title">{caption}</span>
        </div>
        <div class="meta">{fig['filename']} &mdash; {fig['width']}x{fig['height']}px</div>
      </div>""")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YG1 CVD — Manual Image Catalog</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif;
    background: #f5f5fa;
    color: #333;
    padding: 24px;
  }}
  .header {{
    text-align: center;
    padding: 32px 0 24px;
  }}
  .header h1 {{
    color: #1a237e;
    font-size: 28px;
    margin-bottom: 8px;
  }}
  .header .sub {{
    color: #555;
    font-size: 14px;
  }}
  .stats {{
    display: flex;
    justify-content: center;
    gap: 32px;
    margin: 16px 0 32px;
    flex-wrap: wrap;
  }}
  .stat-box {{
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 12px 24px;
    text-align: center;
    min-width: 120px;
  }}
  .stat-box .num {{
    font-size: 28px;
    font-weight: bold;
    color: #1a237e;
  }}
  .stat-box .label {{
    font-size: 12px;
    color: #777;
    margin-top: 4px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .card {{
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
    transition: box-shadow 0.2s;
  }}
  .card:hover {{
    box-shadow: 0 4px 16px rgba(26, 35, 126, 0.15);
  }}
  .img-wrap {{
    background: #fafafa;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 160px;
    padding: 8px;
  }}
  .img-wrap img {{
    max-width: 100%;
    max-height: 200px;
    object-fit: contain;
  }}
  .caption {{
    padding: 8px 12px 4px;
    font-size: 13px;
    line-height: 1.4;
  }}
  .caption .idx {{
    display: inline-block;
    background: #1a237e;
    color: #fff;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    margin-right: 4px;
    font-weight: bold;
  }}
  .caption .title {{
    color: #1a237e;
    font-weight: 600;
  }}
  .meta {{
    padding: 2px 12px 10px;
    font-size: 11px;
    color: #999;
  }}
  .footer {{
    text-align: center;
    padding: 32px 0 16px;
    color: #999;
    font-size: 12px;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>YG1 CVD &mdash; Manual Image Catalog</h1>
    <div class="sub">(주)윈텍오토메이션 &middot; [WT1724] YG1 CVD 매뉴얼 &middot; 자동 생성</div>
  </div>
  <div class="stats">
    <div class="stat-box"><div class="num">{len(captions)}</div><div class="label">섹션/캡션</div></div>
    <div class="stat-box"><div class="num">{len(figures)}</div><div class="label">고유 FIGURE 이미지</div></div>
    <div class="stat-box"><div class="num">{matched}</div><div class="label">매칭됨</div></div>
  </div>
  <div class="grid">
    {"".join(cards_html)}
  </div>
  <div class="footer">docs-agent &middot; Auto-generated image catalog</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return matched


def main():
    print("=" * 60)
    print("YG1 CVD Manual - Image Catalog Builder")
    print("=" * 60)

    # 1. Extract sections/captions
    print("\n[1] Extracting sections from parsed markdown...")
    captions = extract_sections(PARSED_MD)
    print(f"    Found {len(captions)} unique section captions")
    for i, c in enumerate(captions[:10]):
        print(f"      {i+1}. {c}")
    if len(captions) > 10:
        print(f"      ... and {len(captions) - 10} more")

    # 2. Classify and deduplicate images
    print(f"\n[2] Classifying images from: {IMAGE_DIR}")
    figures, stats = classify_and_dedup_images(IMAGE_DIR)
    print(f"    Total files scanned: {stats['total']}")
    print(f"    FIGURE (>={FIGURE_MIN_W}x{FIGURE_MIN_H}): {stats['figure']}")
    print(f"    SMALL: {stats['small']}")
    print(f"    ICON: {stats['icon']}")
    print(f"    Duplicates removed: {stats['duplicate']}")
    print(f"    Errors: {stats['error']}")

    # 3. Generate HTML catalog
    print(f"\n[3] Generating HTML catalog...")
    matched = generate_html(figures, captions, OUTPUT_HTML)

    file_size = os.path.getsize(OUTPUT_HTML)
    size_str = f"{file_size / 1024:.1f} KB" if file_size < 1048576 else f"{file_size / 1048576:.1f} MB"

    print(f"\n{'=' * 60}")
    print(f"RESULTS:")
    print(f"  Sections/Captions: {len(captions)}")
    print(f"  Unique FIGURE images: {len(figures)}")
    print(f"  Matched (caption<->image): {matched}")
    print(f"  Output: {OUTPUT_HTML}")
    print(f"  File size: {size_str}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
