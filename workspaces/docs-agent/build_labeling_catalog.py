"""
Labeling Machine KR 매뉴얼 이미지 카탈로그 빌더.
파싱된 마크다운에서 Figure 캡션/섹션을 추출하고,
이미지를 분류·중복제거한 뒤 HTML 카탈로그를 생성한다.
"""

import os
import re
import hashlib
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image

# --- 경로 설정 ---
PARSED_MD = r"C:\MES\wta-agents\data\manual_parsed\HAM-Labeling_User_Manual_v1.1_KR.md"
IMAGE_DIR = r"C:\MES\wta-agents\data\manual_images\HAM-Labeling_User_Manual_v1.1_KR"
OUTPUT_HTML = r"C:\MES\wta-agents\reports\labeling_kr_이미지_카탈로그.html"

# --- 이미지 분류 기준 ---
FIGURE_MIN_W = 400
FIGURE_MIN_H = 300
THUMB_MAX = 220
THUMB_QUALITY = 50
DEDUP_SIZE = (32, 32)


def natural_sort_key(s: str):
    """자연 정렬 키 (img_001, img_002, ... img_065)."""
    return [
        int(c) if c.isdigit() else c.lower()
        for c in re.split(r"(\d+)", s)
    ]


def pixel_hash(img: Image.Image) -> str:
    """32x32 리사이즈 후 RGB 바이트의 MD5 해시."""
    small = img.convert("RGB").resize(DEDUP_SIZE, Image.LANCZOS)
    return hashlib.md5(small.tobytes()).hexdigest()


def classify_image(path: str) -> tuple[str, int, int]:
    """이미지를 FIGURE / SMALL / ICON 으로 분류. (label, w, h) 반환."""
    with Image.open(path) as img:
        w, h = img.size
    if w >= FIGURE_MIN_W and h >= FIGURE_MIN_H:
        return "FIGURE", w, h
    elif w >= 100 or h >= 100:
        return "SMALL", w, h
    else:
        return "ICON", w, h


def make_thumbnail_base64(path: str) -> str:
    """JPEG base64 썸네일 생성 (max 220px, quality 50)."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=THUMB_QUALITY)
        return base64.b64encode(buf.getvalue()).decode("ascii")


def extract_captions(md_path: str) -> list[str]:
    """마크다운에서 Figure 캡션과 주요 섹션 헤더를 순서대로 추출."""
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    captions: list[str] = []
    # Figure 패턴들
    fig_patterns = [
        re.compile(r"^Figure\s*[-–]\s*(.+)", re.IGNORECASE),
        re.compile(r"^Figure\s+(\d[\d\-\.]*)\s+(.+)", re.IGNORECASE),
        re.compile(r"^그림\s*[\d\-\.]+\s*(.+)"),
    ]
    # 섹션 헤더 (## 또는 ###)
    section_pattern = re.compile(r"^(#{2,3})\s+(.+)")

    for line in lines:
        stripped = line.strip()
        # Figure 캡션 우선
        for pat in fig_patterns:
            m = pat.match(stripped)
            if m:
                # Figure X-Y Caption 형태이면 그룹 2개
                groups = m.groups()
                caption = groups[-1].strip()
                # 번호 포함 버전
                if len(groups) == 2:
                    caption = f"Figure {groups[0]} {groups[1]}".strip()
                else:
                    caption = f"Figure - {caption}"
                captions.append(caption)
                break
        else:
            # 섹션 헤더 (Table, Page 제외)
            m = section_pattern.match(stripped)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                if title.lower() not in ("table",) and not title.startswith("Page "):
                    # 이미 같은 타이틀 연속 방지
                    if not captions or captions[-1] != title:
                        captions.append(title)

    return captions


def main():
    # 1) 캡션 추출
    captions = extract_captions(PARSED_MD)
    print(f"[1/4] 캡션/섹션 추출 완료: {len(captions)}개")

    # 2) 이미지 수집 및 분류
    all_files = sorted(
        [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith((".png", ".jpg", ".jpeg"))],
        key=natural_sort_key,
    )
    print(f"[2/4] 전체 이미지: {len(all_files)}개")

    figures = []  # (filename, w, h)
    smalls = []
    icons = []
    stats = {"FIGURE": 0, "SMALL": 0, "ICON": 0}

    for fname in all_files:
        fpath = os.path.join(IMAGE_DIR, fname)
        label, w, h = classify_image(fpath)
        stats[label] += 1
        if label == "FIGURE":
            figures.append((fname, w, h))
        elif label == "SMALL":
            smalls.append((fname, w, h))
        else:
            icons.append((fname, w, h))

    print(f"    FIGURE: {stats['FIGURE']}, SMALL: {stats['SMALL']}, ICON: {stats['ICON']}")

    # 3) 중복 제거 (pixel-hash)
    seen_hashes: set[str] = set()
    unique_figures: list[tuple[str, int, int]] = []
    dup_count = 0

    for fname, w, h in figures:
        fpath = os.path.join(IMAGE_DIR, fname)
        with Image.open(fpath) as img:
            ph = pixel_hash(img)
        if ph not in seen_hashes:
            seen_hashes.add(ph)
            unique_figures.append((fname, w, h))
        else:
            dup_count += 1

    print(f"[3/4] 중복 제거: {dup_count}개 제거 → 유니크 FIGURE: {len(unique_figures)}개")

    # 4) 캡션 매칭 (순차 매칭)
    matched: list[dict] = []
    for idx, (fname, w, h) in enumerate(unique_figures):
        caption = captions[idx] if idx < len(captions) else f"Image #{idx + 1}"
        fpath = os.path.join(IMAGE_DIR, fname)
        thumb_b64 = make_thumbnail_base64(fpath)
        matched.append({
            "index": idx + 1,
            "filename": fname,
            "width": w,
            "height": h,
            "caption": caption,
            "thumb_b64": thumb_b64,
        })

    # 5) HTML 생성
    html = generate_html(matched, stats, dup_count, len(all_files), len(unique_figures))

    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[4/4] HTML 카탈로그 생성 완료: {OUTPUT_HTML}")
    print(f"    총 {len(matched)}개 이미지 카탈로그 항목")


def generate_html(items: list[dict], stats: dict, dup_count: int, total: int, unique: int) -> str:
    """HTML 카탈로그 생성."""
    cards_html = ""
    for item in items:
        cards_html += f"""
        <div class="card">
            <div class="card-img">
                <img src="data:image/jpeg;base64,{item['thumb_b64']}" alt="{item['caption']}" loading="lazy">
            </div>
            <div class="card-body">
                <div class="card-index">#{item['index']}</div>
                <div class="card-caption">{item['caption']}</div>
                <div class="card-meta">{item['filename']} &mdash; {item['width']}x{item['height']}px</div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Labeling Machine (KR) — Manual Image Catalog</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Malgun Gothic', '맑은 고딕', 'Pretendard Variable', sans-serif;
    background: #f4f6fb;
    color: #222;
    line-height: 1.5;
  }}
  .header {{
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    color: #fff;
    padding: 40px 32px 32px;
    text-align: center;
  }}
  .header h1 {{
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .header .subtitle {{
    font-size: 15px;
    opacity: 0.85;
  }}
  .summary {{
    display: flex;
    justify-content: center;
    gap: 24px;
    flex-wrap: wrap;
    padding: 20px 32px;
    background: #fff;
    border-bottom: 1px solid #e0e3eb;
  }}
  .summary .stat {{
    text-align: center;
    min-width: 100px;
  }}
  .summary .stat-value {{
    font-size: 26px;
    font-weight: 700;
    color: #1a237e;
  }}
  .summary .stat-label {{
    font-size: 13px;
    color: #666;
    margin-top: 2px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 20px;
    padding: 28px 32px 48px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .card {{
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(26,35,126,0.07);
    overflow: hidden;
    transition: box-shadow 0.2s, transform 0.2s;
  }}
  .card:hover {{
    box-shadow: 0 6px 24px rgba(26,35,126,0.15);
    transform: translateY(-3px);
  }}
  .card-img {{
    background: #eef0f7;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    min-height: 160px;
  }}
  .card-img img {{
    max-width: 100%;
    max-height: 200px;
    border-radius: 4px;
  }}
  .card-body {{
    padding: 12px 14px 14px;
  }}
  .card-index {{
    display: inline-block;
    background: #1a237e;
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    margin-bottom: 6px;
  }}
  .card-caption {{
    font-size: 13px;
    font-weight: 600;
    color: #1a237e;
    margin-bottom: 4px;
    word-break: keep-all;
  }}
  .card-meta {{
    font-size: 11px;
    color: #999;
  }}
  .footer {{
    text-align: center;
    padding: 24px;
    font-size: 12px;
    color: #aaa;
    border-top: 1px solid #e8eaf0;
    background: #fff;
  }}
</style>
</head>
<body>
<div class="header">
  <h1>Labeling Machine (KR) &mdash; Manual Image Catalog</h1>
  <div class="subtitle">HAM-Labeling_User_Manual_v1.1_KR &nbsp;|&nbsp; (주)윈텍오토메이션 생산관리팀</div>
</div>
<div class="summary">
  <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">전체 이미지</div></div>
  <div class="stat"><div class="stat-value">{stats['FIGURE']}</div><div class="stat-label">FIGURE</div></div>
  <div class="stat"><div class="stat-value">{stats['SMALL']}</div><div class="stat-label">SMALL</div></div>
  <div class="stat"><div class="stat-value">{stats['ICON']}</div><div class="stat-label">ICON</div></div>
  <div class="stat"><div class="stat-value">{dup_count}</div><div class="stat-label">중복 제거</div></div>
  <div class="stat"><div class="stat-value">{unique}</div><div class="stat-label">카탈로그 항목</div></div>
</div>
<div class="grid">
{cards_html}
</div>
<div class="footer">
  Generated by docs-agent &nbsp;|&nbsp; HAM-Labeling_User_Manual_v1.1_KR Image Catalog
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
