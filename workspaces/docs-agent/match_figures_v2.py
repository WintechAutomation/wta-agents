"""
매뉴얼 이미지 figure 매칭 v2
- 큰 이미지(figure 후보)만 필터링
- 순서대로 그림 번호 부여
- 작은 이미지(아이콘/심볼)는 별도 표시
- 통합 카탈로그 생성
"""
import os
import re
import base64
from pathlib import Path
from PIL import Image
import io

IMG_BASE = Path(r'C:\MES\wta-agents\data\manual_images')
REPORTS = Path(r'C:\MES\wta-agents\reports')

# Figure 후보 최소 크기 (아이콘/로고 제외)
MIN_FIGURE_W = 250
MIN_FIGURE_H = 200


def get_sorted_images(img_dir: Path) -> list[Path]:
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    files = [f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in exts]
    def natural_key(p):
        parts = re.split(r'(\d+)', p.stem)
        return [int(x) if x.isdigit() else x.lower() for x in parts]
    files.sort(key=natural_key)
    return files


def classify_image(path: Path) -> tuple[str, int, int]:
    """이미지를 figure/icon으로 분류. (type, w, h) 반환"""
    try:
        img = Image.open(path)
        w, h = img.size
        if w >= MIN_FIGURE_W and h >= MIN_FIGURE_H:
            return ('figure', w, h)
        else:
            return ('icon', w, h)
    except:
        return ('error', 0, 0)


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


def process_manual(img_dir_name: str, title: str) -> dict:
    img_dir = IMG_BASE / img_dir_name
    if not img_dir.is_dir():
        print(f"  건너뜀: {img_dir_name}")
        return None

    images = get_sorted_images(img_dir)
    if not images:
        return None

    figures = []  # (path, fig_num, w, h)
    icons = []    # (path, w, h)
    fig_seq = 0

    for path in images:
        cls, w, h = classify_image(path)
        if cls == 'figure':
            fig_seq += 1
            figures.append((path, fig_seq, w, h))
        elif cls == 'icon':
            icons.append((path, w, h))

    print(f"  {title}: {len(images)}개 중 figure {len(figures)}개, 아이콘 {len(icons)}개")

    # figure 카드 생성
    cards = []
    for path, seq, w, h in figures:
        thumb = make_thumb(path)
        fname = f"{seq:03d}_그림_{path.stem}{path.suffix}"
        cards.append(f"""    <div class="card">
      <div class="seq">{seq:03d}</div>
      <img src="{thumb}" alt="그림 {seq}"/>
      <div class="cap">그림 {seq:03d}</div>
      <div class="fname">{fname}</div>
      <div class="orig">원본: {path.name} ({w}x{h})</div>
    </div>""")

    # 아이콘 카드 (접힌 상태)
    icon_cards = []
    for path, w, h in icons:
        thumb = make_thumb(path, 100)
        icon_cards.append(f"""      <div class="icon-card">
        <img src="{thumb}" alt="{path.stem}"/>
        <div class="icon-name">{path.name} ({w}x{h})</div>
      </div>""")

    return {
        'title': title,
        'total': len(images),
        'figures': len(figures),
        'icons': len(icons),
        'cards_html': '\n'.join(cards),
        'icon_html': '\n'.join(icon_cards),
    }


MANUALS = [
    ('PVD 언로딩 매뉴얼(수정 완료)_20220328', 'PVD Unloading (KR)'),
    ('HAM-PVD_Unloading_User_Manual_en_v1.3', 'PVD Unloading (EN)'),
    ('(완성본)유지보수 메뉴얼 - 한국야금 PVD Loading Handler', 'PVD Loading Handler'),
    ('HAM-CVD L&UL Machine User Manual en_v1.0', 'CVD L&UL Machine (EN)'),
    ('[WT1724]YG1  CVD 매뉴얼', 'YG1 CVD'),
    ('HAM-Labeling_User_Manual_v1.1_KR', 'Labeling Machine'),
    ('PressHandler', 'Press Handler'),
    ('Double_Side_Handler_Manual_Revised', 'Double Side Handler'),
    ('[OKE]201102_PVD 1호핸들러 매뉴얼(한국어)', 'PVD 1호 Handler (KR)'),
]


def main():
    results = []
    for img_dir, title in MANUALS:
        print(f"처리 중: {title}")
        result = process_manual(img_dir, title)
        if result:
            results.append(result)

    # 통합 HTML (탭 UI)
    tab_buttons = []
    tab_contents = []
    for i, r in enumerate(results):
        active = ' active' if i == 0 else ''
        display = 'block' if i == 0 else 'none'
        tab_buttons.append(
            f'<button class="tab-btn{active}" onclick="showTab({i})">'
            f'{r["title"]} <span class="badge">{r["figures"]}</span></button>'
        )
        tab_contents.append(f"""<div class="tab-content" id="tab-{i}" style="display:{display};">
  <div class="summary">총 {r['total']}개 이미지 | Figure 후보: {r['figures']}개 | 아이콘/심볼: {r['icons']}개</div>
  <h3 style="color:#1a237e; margin: 12px 0 8px;">Figure 이미지 ({r['figures']}개)</h3>
  <div class="grid">
{r['cards_html']}
  </div>
  <details style="margin-top:16px;">
    <summary style="cursor:pointer; color:#888; font-size:9pt;">아이콘/심볼 ({r['icons']}개) — 클릭하여 펼치기</summary>
    <div class="icon-grid" style="margin-top:8px;">
{r['icon_html']}
    </div>
  </details>
</div>""")

    total_figs = sum(r['figures'] for r in results)
    total_imgs = sum(r['total'] for r in results)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>WTA 장비 매뉴얼 이미지 카탈로그</title>
<style>
  body {{ font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .total {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .tab-bar {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }}
  .tab-btn {{
    padding: 8px 14px; border: 1px solid #ccc; border-radius: 6px 6px 0 0;
    background: #fff; cursor: pointer; font-size: 9pt; font-family: '맑은 고딕', sans-serif;
    color: #555; transition: all 0.2s;
  }}
  .tab-btn:hover {{ background: #e8eaf6; }}
  .tab-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; font-weight: 700; }}
  .badge {{ padding: 1px 6px; border-radius: 10px; font-size: 8pt; margin-left: 4px; }}
  .tab-btn.active .badge {{ background: rgba(255,255,255,0.3); }}
  .tab-btn:not(.active) .badge {{ background: #e0e0e0; color: #666; }}
  .summary {{ color: #555; font-size: 10pt; margin-bottom: 12px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 140px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 8pt; color: #aaa; margin-bottom: 2px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #1a237e; margin-top: 4px; }}
  .fname {{ font-size: 7pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .orig {{ font-size: 7pt; color: #bbb; }}
  .icon-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 6px; }}
  .icon-card {{ background: #fff; border-radius: 4px; padding: 4px; text-align: center; }}
  .icon-card img {{ width: 80px; height: 60px; object-fit: contain; }}
  .icon-name {{ font-size: 7pt; color: #aaa; word-break: break-all; }}
</style>
</head>
<body>
<h1>WTA 장비 매뉴얼 — 이미지 카탈로그</h1>
<div class="total">{len(results)}개 장비 | 총 {total_imgs}개 이미지 (Figure 후보 {total_figs}개)</div>
<div class="tab-bar">
{''.join(tab_buttons)}
</div>
{''.join(tab_contents)}
<script>
function showTab(idx) {{
  document.querySelectorAll('.tab-content').forEach(function(el, i) {{
    el.style.display = i === idx ? 'block' : 'none';
  }});
  document.querySelectorAll('.tab-btn').forEach(function(el, i) {{
    if (i === idx) {{ el.classList.add('active'); }}
    else {{ el.classList.remove('active'); }}
  }});
}}
</script>
</body>
</html>"""

    output = REPORTS / '장비_이미지_카탈로그.html'
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\n통합 카탈로그: {output}")
    print(f"크기: {size_mb:.1f} MB | {len(results)}개 장비 | Figure {total_figs}개 / 전체 {total_imgs}개")


if __name__ == '__main__':
    main()
