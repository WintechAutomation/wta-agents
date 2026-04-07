"""Double Side Handler 매뉴얼 이미지 카탈로그 생성 스크립트.

파싱 텍스트 미확보 → 이미지 크기 기반 분류 + 픽셀 해시 중복 제거.
"""

import base64
import hashlib
import io
import re
from pathlib import Path

from PIL import Image

# ── 경로 ──
IMG_DIR = Path(r"C:\MES\wta-agents\data\manual_images\Double_Side_Handler_Manual_Revised")
OUT_HTML = Path(r"C:\MES\wta-agents\reports\double_side_handler_이미지_카탈로그.html")


def natural_sort_key(p: Path):
    """자연 정렬 키 (img_001, img_002, ... img_100)."""
    return [
        int(t) if t.isdigit() else t.lower()
        for t in re.split(r"(\d+)", p.name)
    ]


def classify(w: int, h: int) -> str:
    if w < 150 or h < 100:
        return "ICON"
    if w >= 400 and h >= 300:
        return "FIGURE"
    return "SMALL"


def pixel_hash(img: Image.Image) -> str:
    """32x32 리사이즈 후 RGB 바이트 MD5."""
    thumb = img.resize((32, 32), Image.LANCZOS).convert("RGB")
    return hashlib.md5(thumb.tobytes()).hexdigest()


def make_thumbnail_b64(img: Image.Image, max_px: int = 220, quality: int = 50) -> str:
    """JPEG 썸네일을 base64로 반환."""
    img_copy = img.copy()
    img_copy.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img_copy.convert("RGB").save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    images = sorted(IMG_DIR.iterdir(), key=natural_sort_key)
    images = [p for p in images if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")]

    counts = {"FIGURE": 0, "SMALL": 0, "ICON": 0}
    seen_hashes: set[str] = set()
    figures: list[tuple[Path, Image.Image]] = []

    for p in images:
        try:
            img = Image.open(p)
            w, h = img.size
        except Exception as e:
            print(f"SKIP (open error): {p.name} — {e}")
            continue

        cat = classify(w, h)
        counts[cat] += 1

        if cat != "FIGURE":
            continue

        ph = pixel_hash(img)
        if ph in seen_hashes:
            continue
        seen_hashes.add(ph)
        figures.append((p, img))

    # ── 리포트 ──
    total = sum(counts.values())
    dup_count = counts["FIGURE"] - len(figures)
    print(f"총 이미지: {total}")
    print(f"  FIGURE: {counts['FIGURE']}  (중복 제거 후: {len(figures)})")
    print(f"  SMALL:  {counts['SMALL']}")
    print(f"  ICON:   {counts['ICON']}")
    print(f"  중복 제거: {dup_count}")

    # ── HTML 생성 ──
    cards_html = []
    for idx, (p, img) in enumerate(figures, 1):
        w, h = img.size
        b64 = make_thumbnail_b64(img)
        cards_html.append(f"""
      <div class="card">
        <img src="data:image/jpeg;base64,{b64}" alt="Fig {idx:02d}">
        <div class="caption">Fig {idx:02d}</div>
        <div class="meta">{p.name}<br>{w}x{h}px</div>
      </div>""")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Double Side Handler — Manual Image Catalog</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Malgun Gothic', 'Pretendard Variable', sans-serif;
    background: #f5f5f5; color: #222; padding: 32px;
  }}
  h1 {{
    text-align: center; color: #1a237e; font-size: 28px;
    margin-bottom: 8px;
  }}
  .info {{
    text-align: center; color: #555; font-size: 14px;
    margin-bottom: 24px; line-height: 1.8;
  }}
  .info .warn {{
    color: #c62828; font-weight: bold;
  }}
  .stats {{
    display: flex; justify-content: center; gap: 24px;
    margin-bottom: 28px; flex-wrap: wrap;
  }}
  .stat {{
    background: #fff; border-radius: 8px; padding: 12px 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,.1); text-align: center; min-width: 120px;
  }}
  .stat .num {{ font-size: 28px; font-weight: bold; color: #1a237e; }}
  .stat .label {{ font-size: 12px; color: #777; margin-top: 4px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: #fff; border-radius: 8px; overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    display: flex; flex-direction: column; align-items: center;
    padding: 12px;
  }}
  .card img {{
    max-width: 220px; max-height: 220px; object-fit: contain;
    border: 1px solid #e0e0e0; border-radius: 4px;
  }}
  .caption {{
    margin-top: 8px; font-weight: bold; color: #1a237e; font-size: 14px;
  }}
  .meta {{
    font-size: 11px; color: #999; text-align: center; margin-top: 4px;
  }}
  footer {{
    text-align: center; margin-top: 32px; color: #aaa; font-size: 12px;
  }}
</style>
</head>
<body>
  <h1>Double Side Handler — Manual Image Catalog</h1>
  <div class="info">
    총 {total}장 중 FIGURE {len(figures)}장 (중복 제거 후) | 크기 기반 자동 분류<br>
    <span class="warn">파싱 텍스트 미확보 — 이미지 순서 기반 정렬 (캡션 확인 필요)</span>
  </div>
  <div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="label">전체 이미지</div></div>
    <div class="stat"><div class="num">{len(figures)}</div><div class="label">FIGURE (유니크)</div></div>
    <div class="stat"><div class="num">{counts['SMALL']}</div><div class="label">SMALL</div></div>
    <div class="stat"><div class="num">{counts['ICON']}</div><div class="label">ICON</div></div>
    <div class="stat"><div class="num">{dup_count}</div><div class="label">중복 제거</div></div>
  </div>
  <div class="grid">
    {"".join(cards_html)}
  </div>
  <footer>(주)윈텍오토메이션 생산관리팀 (AI운영팀) — docs-agent 자동 생성</footer>
</body>
</html>"""

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\n카탈로그 저장: {OUT_HTML}")
    print(f"Cloudflare URL: https://agent.mes-wta.com/double_side_handler_이미지_카탈로그")


if __name__ == "__main__":
    main()
