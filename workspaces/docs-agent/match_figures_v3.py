"""
매뉴얼 이미지 figure 매칭 v3
- PVD Unloading: 기존 HTML 매뉴얼에서 추출한 정확한 캡션 복원
- CVD L&UL, PVD Unloading EN: 파싱 텍스트에서 Figure 캡션 추출 + 이미지 매칭
- 기타: 큰 이미지 필터링 후 순번 부여, section heading 참조
"""
import os
import re
import base64
import html as html_mod
from pathlib import Path
from PIL import Image
import io

IMG_BASE = Path(r'C:\MES\wta-agents\data\manual_images')
PARSED_DIR = Path(r'C:\MES\wta-agents\data\wta_parsed')
REPORTS = Path(r'C:\MES\wta-agents\reports')

MIN_FIG_W, MIN_FIG_H = 250, 200


def get_sorted_images(img_dir: Path) -> list[Path]:
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    files = [f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in exts]
    def nk(p):
        return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', p.stem)]
    files.sort(key=nk)
    return files


def classify(path: Path) -> tuple[str, int, int]:
    try:
        img = Image.open(path)
        w, h = img.size
        return ('figure' if w >= MIN_FIG_W and h >= MIN_FIG_H else 'icon', w, h)
    except:
        return ('error', 0, 0)


def thumb(path: Path, sz: int = 220) -> str:
    try:
        img = Image.open(path)
        img.thumbnail((sz, sz), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = 'JPEG' if path.suffix.lower() in ['.jpg', '.jpeg'] else 'PNG'
        if fmt == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(buf, format=fmt, quality=50)
        mime = 'jpeg' if fmt == 'JPEG' else 'png'
        return f"data:image/{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"
    except:
        return ""


def extract_pvd_unloading_captions() -> list[str]:
    """기존 pvd_이미지_매칭_확인.html에서 정확한 캡션 추출"""
    path = REPORTS / 'pvd_이미지_매칭_확인.html'
    content = path.read_text(encoding='utf-8')
    return re.findall(r'class="cap">(.*?)</div>', content)


def extract_figure_captions_en(parsed_file: str, pattern: str) -> list[str]:
    """파싱된 마크다운에서 Figure 캡션 추출"""
    path = PARSED_DIR / parsed_file
    if not path.exists():
        return []
    content = path.read_text(encoding='utf-8', errors='replace')
    matches = re.findall(pattern, content)
    return [m.strip()[:80] for m in matches if m.strip()]


def extract_section_headings(parsed_file: str) -> list[str]:
    """파싱 텍스트에서 섹션 헤딩 추출 (figure 캡션이 없는 매뉴얼용)"""
    path = PARSED_DIR / parsed_file
    if not path.exists():
        return []
    content = path.read_text(encoding='utf-8', errors='replace')
    headings = re.findall(r'^#{1,4}\s+(.+?)$', content, re.MULTILINE)
    return [h.strip() for h in headings if len(h.strip()) > 2]


def build_tab(title, images, captions, img_dir_name):
    """장비 탭 콘텐츠 생성"""
    figures = []
    icons = []
    fig_idx = 0

    for path in images:
        cls, w, h = classify(path)
        if cls == 'figure':
            # 캡션 매칭
            if fig_idx < len(captions):
                cap = captions[fig_idx]
            else:
                cap = f"(확인 필요) {path.stem}"

            # 파일명 생성
            fig_match = re.match(r'그림\s*(\d+[-\.]\d+)\s*(.*)', cap)
            if fig_match:
                fig_num = fig_match.group(1)
                desc = fig_match.group(2).strip()
                desc_safe = re.sub(r'\s+', '_', desc)
                desc_safe = re.sub(r'[\\/:*?"<>|]', '', desc_safe)
                fname = f"{fig_idx+1:03d}_그림_{fig_num}_{desc_safe}{path.suffix}"
            else:
                cap_safe = re.sub(r'\s+', '_', cap)
                cap_safe = re.sub(r'[\\/:*?"<>|()]', '', cap_safe)
                fname = f"{fig_idx+1:03d}_{cap_safe}{path.suffix}"

            figures.append((path, fig_idx + 1, cap, fname, w, h))
            fig_idx += 1
        else:
            icons.append((path, w, h))

    # Figure 카드
    cards = []
    for path, seq, cap, fname, w, h in figures:
        t = thumb(path)
        is_unmatched = '확인 필요' in cap
        border = ' style="border:2px solid #ff9800;"' if is_unmatched else ''
        cards.append(f"""    <div class="card"{border}>
      <div class="seq">{seq:03d}</div>
      <img src="{t}" alt="{html_mod.escape(cap)}"/>
      <div class="cap">{html_mod.escape(cap)}</div>
      <div class="fname">{html_mod.escape(fname)}</div>
      <div class="orig">원본: {path.name} ({w}x{h})</div>
    </div>""")

    # 아이콘
    icon_cards = []
    for path, w, h in icons:
        t = thumb(path, 80)
        icon_cards.append(f"""      <div class="icon-card">
        <img src="{t}" alt="{path.stem}"/>
        <div class="icon-name">{path.name} ({w}x{h})</div>
      </div>""")

    matched = len([1 for _, _, c, _, _, _ in figures if '확인 필요' not in c])
    return {
        'title': title,
        'total': len(images),
        'figures': len(figures),
        'matched': matched,
        'icons': len(icons),
        'cards': '\n'.join(cards),
        'icon_cards': '\n'.join(icon_cards),
    }


# 매뉴얼별 설정
MANUALS = [
    {
        'img_dir': 'PVD 언로딩 매뉴얼(수정 완료)_20220328',
        'title': 'PVD Unloading (KR)',
        'caption_source': 'pvd_html',  # 기존 HTML에서 추출
    },
    {
        'img_dir': 'HAM-PVD_Unloading_User_Manual_en_v1.3',
        'title': 'PVD Unloading (EN)',
        'caption_source': 'parsed',
        'parsed_file': 'HAM-PVD_Unloading_User_Manual_en_v1.3.md',
        'pattern': r'[Ff]ig(?:ure|\.)\s*(\d+[-\.]\d+)[\.:\s—\-]*(.*?)(?:\n|$)',
        'format': 'fig_num',
    },
    {
        'img_dir': '(완성본)유지보수 메뉴얼 - 한국야금 PVD Loading Handler',
        'title': 'PVD Loading Handler',
        'caption_source': 'parsed',
        'parsed_file': 'Final_Maintenance_Manual_-_Korea_Tungsten_PVD_Loading_Handler.md',
        'pattern': r'그림\s*(\d+[-\.]\d+)[\.:\s—\-]*(.*?)(?:\n|$)',
        'format': 'fig_num',
    },
    {
        'img_dir': 'HAM-CVD L&UL Machine User Manual en_v1.0',
        'title': 'CVD L&UL Machine (EN)',
        'caption_source': 'parsed_figure_dash',
        'parsed_file': 'HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.md',
    },
    {
        'img_dir': '[WT1724]YG1  CVD 매뉴얼',
        'title': 'YG1 CVD',
        'caption_source': 'none',
    },
    {
        'img_dir': 'HAM-Labeling_User_Manual_v1.1_KR',
        'title': 'Labeling Machine',
        'caption_source': 'none',
    },
    {
        'img_dir': 'PressHandler',
        'title': 'Press Handler',
        'caption_source': 'none',
    },
    {
        'img_dir': 'Double_Side_Handler_Manual_Revised',
        'title': 'Double Side Handler',
        'caption_source': 'none',
    },
    {
        'img_dir': '[OKE]201102_PVD 1호핸들러 매뉴얼(한국어)',
        'title': 'PVD 1호 Handler (KR)',
        'caption_source': 'parsed',
        'parsed_file': 'OKE_201102_PVD_1_Handler_Manual.md',
        'pattern': r'그림\s*(\d+[-\.]\d+)[\.:\s—\-]*(.*?)(?:\n|$)',
        'format': 'fig_num',
    },
]


def get_captions(manual: dict) -> list[str]:
    src = manual['caption_source']

    if src == 'pvd_html':
        return extract_pvd_unloading_captions()

    elif src == 'parsed':
        parsed = manual.get('parsed_file', '')
        pattern = manual.get('pattern', '')
        raw = []
        path = PARSED_DIR / parsed
        if path.exists():
            content = path.read_text(encoding='utf-8', errors='replace')
            for m in re.finditer(pattern, content):
                fig_num = m.group(1).replace('.', '-')
                desc = m.group(2).strip()[:60]
                raw.append(f"그림 {fig_num} {desc}".strip())
        return raw

    elif src == 'parsed_figure_dash':
        parsed = manual.get('parsed_file', '')
        path = PARSED_DIR / parsed
        if path.exists():
            content = path.read_text(encoding='utf-8', errors='replace')
            matches = re.findall(r'Figure\s*[-—]\s*(.+?)(?:\n|$)', content)
            return [m.strip()[:80] for m in matches]
        return []

    return []


def main():
    results = []

    for manual in MANUALS:
        img_dir = IMG_BASE / manual['img_dir']
        if not img_dir.is_dir():
            print(f"건너뜀: {manual['img_dir']}")
            continue

        images = get_sorted_images(img_dir)
        captions = get_captions(manual)
        title = manual['title']

        print(f"처리: {title} - {len(images)}개 이미지, {len(captions)}개 캡션")

        result = build_tab(title, images, captions, manual['img_dir'])
        results.append(result)
        print(f"  -> figure {result['figures']}개 (매칭 {result['matched']}개), 아이콘 {result['icons']}개")

    # 통합 HTML
    tab_buttons = []
    tab_contents = []
    for i, r in enumerate(results):
        active = ' active' if i == 0 else ''
        display = 'block' if i == 0 else 'none'
        match_info = f"{r['matched']}/{r['figures']}" if r['matched'] > 0 else str(r['figures'])
        tab_buttons.append(
            f'<button class="tab-btn{active}" onclick="showTab({i})">'
            f'{r["title"]} <span class="badge">{match_info}</span></button>'
        )
        match_pct = (r['matched'] / r['figures'] * 100) if r['figures'] > 0 else 0
        tab_contents.append(f"""<div class="tab-content" id="tab-{i}" style="display:{display};">
  <div class="summary">총 {r['total']}개 이미지 | Figure: {r['figures']}개 (캡션 매칭 {r['matched']}개, {match_pct:.0f}%) | 아이콘: {r['icons']}개</div>
  <div class="grid">
{r['cards']}
  </div>
  <details style="margin-top:16px;">
    <summary style="cursor:pointer; color:#888; font-size:9pt;">아이콘/심볼 ({r['icons']}개)</summary>
    <div class="icon-grid" style="margin-top:8px;">
{r['icon_cards']}
    </div>
  </details>
</div>""")

    total_figs = sum(r['figures'] for r in results)
    total_matched = sum(r['matched'] for r in results)
    total_imgs = sum(r['total'] for r in results)

    html_out = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>WTA 장비 매뉴얼 이미지 카탈로그</title>
<style>
  body {{ font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .total {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .tab-bar {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }}
  .tab-btn {{ padding: 8px 14px; border: 1px solid #ccc; border-radius: 6px 6px 0 0; background: #fff; cursor: pointer; font-size: 9pt; font-family: '맑은 고딕', sans-serif; color: #555; }}
  .tab-btn:hover {{ background: #e8eaf6; }}
  .tab-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; font-weight: 700; }}
  .badge {{ padding: 1px 6px; border-radius: 10px; font-size: 8pt; margin-left: 4px; }}
  .tab-btn.active .badge {{ background: rgba(255,255,255,0.3); }}
  .tab-btn:not(.active) .badge {{ background: #e0e0e0; color: #666; }}
  .summary {{ color: #555; font-size: 10pt; margin-bottom: 12px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 140px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 8pt; color: #aaa; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #1a237e; margin-top: 4px; }}
  .fname {{ font-size: 7pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .orig {{ font-size: 7pt; color: #bbb; }}
  .icon-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 4px; }}
  .icon-card {{ background: #fff; border-radius: 4px; padding: 4px; text-align: center; }}
  .icon-card img {{ width: 60px; height: 50px; object-fit: contain; }}
  .icon-name {{ font-size: 6pt; color: #aaa; word-break: break-all; }}
</style>
</head>
<body>
<h1>WTA 장비 매뉴얼 — 이미지 카탈로그</h1>
<div class="total">{len(results)}개 장비 | Figure {total_figs}개 (캡션 매칭 {total_matched}개) | 전체 {total_imgs}개</div>
<div class="tab-bar">
{''.join(tab_buttons)}
</div>
{''.join(tab_contents)}
<script>
function showTab(idx) {{
  document.querySelectorAll('.tab-content').forEach(function(el, i) {{ el.style.display = i === idx ? 'block' : 'none'; }});
  document.querySelectorAll('.tab-btn').forEach(function(el, i) {{ el.classList.toggle('active', i === idx); }});
}}
</script>
</body>
</html>"""

    out = REPORTS / '장비_이미지_카탈로그.html'
    out.write_text(html_out, encoding='utf-8')
    sz = out.stat().st_size / 1024 / 1024
    print(f"\n저장: {out} ({sz:.1f} MB)")
    print(f"{len(results)}개 장비 | Figure {total_figs}개 (매칭 {total_matched}개) | 전체 {total_imgs}개")


if __name__ == '__main__':
    main()
