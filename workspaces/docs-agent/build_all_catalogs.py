"""
전체 장비 매뉴얼 이미지 카탈로그 생성
- 매뉴얼별 파싱 텍스트에서 Figure 캡션 추출
- img_NNN 파일과 순서 매칭
- 통합 HTML (탭 UI) 생성
"""
import os
import re
import base64
from pathlib import Path
from PIL import Image
import io

IMG_BASE = Path(r'C:\MES\wta-agents\data\manual_images')
PARSED_DIR = Path(r'C:\MES\wta-agents\data\wta_parsed')
REPORTS = Path(r'C:\MES\wta-agents\reports')

MIN_FIG_W = 250
MIN_FIG_H = 200


def get_sorted_images(img_dir: Path) -> list:
    """img_NNN 파일만 자연 정렬로 반환"""
    files = []
    for f in img_dir.iterdir():
        if f.is_file() and f.stem.startswith('img_') and f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}:
            files.append(f)
    def key(p):
        m = re.search(r'(\d+)', p.stem)
        return int(m.group(1)) if m else 0
    files.sort(key=key)
    return files


def classify_image(path: Path):
    """(type, w, h) - figure or icon"""
    try:
        img = Image.open(path)
        w, h = img.size
        if w >= MIN_FIG_W and h >= MIN_FIG_H:
            return ('figure', w, h)
        return ('icon', w, h)
    except Exception:
        return ('error', 0, 0)


def make_thumb(path: Path, max_size=220) -> str:
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


def extract_en_figures(md_path: Path) -> list:
    """EN 매뉴얼에서 'Figure - Description' 캡션 추출 (순서대로)"""
    if not md_path.exists():
        return []
    content = md_path.read_text(encoding='utf-8', errors='replace')
    captions = []
    for m in re.finditer(r'Figure\s*-\s*(.+)', content):
        desc = m.group(1).strip()
        # 테이블 내용 제거
        if len(desc) > 80:
            desc = desc[:80]
        if desc and desc not in [c[1] for c in captions]:
            captions.append((len(captions)+1, desc))
    return captions


def extract_kr_figures(md_path: Path) -> list:
    """KR 매뉴얼에서 '그림 X-Y' 캡션 추출"""
    if not md_path.exists():
        return []
    content = md_path.read_text(encoding='utf-8', errors='replace')
    captions = []
    for m in re.finditer(r'(?:그림|Figure|Fig\.?)\s*(\d+[-\.]\d+)\s*[\.:\s]*([^\n]*)', content):
        fig_num = m.group(1).replace('.', '-')
        desc = m.group(2).strip()
        desc = re.sub(r'[*_`#]', '', desc).strip()
        caption = f"{fig_num} {desc}" if desc else fig_num
        if caption not in [c[1] for c in captions]:
            captions.append((len(captions)+1, caption))
    return captions


def extract_sections(md_path: Path) -> list:
    """매뉴얼에서 섹션 헤더 추출 (순서대로)"""
    if not md_path.exists():
        return []
    content = md_path.read_text(encoding='utf-8', errors='replace')
    sections = []
    # 마크다운 헤더
    for m in re.finditer(r'^#{1,4}\s+(.+)', content, re.MULTILINE):
        title = m.group(1).strip()
        if len(title) > 60:
            title = title[:60]
        sections.append((m.start(), title))
    # 마크다운 헤더 없으면 탭 기반 TOC 추출
    if not sections:
        for m in re.finditer(r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\t|\s{2,})\d+\s*$', content, re.MULTILINE):
            num = m.group(1)
            title = m.group(2).strip()
            if len(title) > 60:
                title = title[:60]
            sections.append((m.start(), f"{num} {title}"))
    return sections


def extract_maintenance_captions(md_path: Path) -> list:
    """유지보수 매뉴얼에서 단계별 설명을 캡션으로 추출"""
    if not md_path.exists():
        return []
    content = md_path.read_text(encoding='utf-8', errors='replace')
    captions = []
    for line in content.split('\n'):
        line = line.strip()
        # 빈 줄, 테이블, 코드 참조 건너뛰기
        if not line or line.startswith('|') or line.startswith('---'):
            continue
        # 너무 긴 줄 (테이블 데이터) 건너뛰기
        if len(line) > 80:
            continue
        # 설명 라인으로 보이는 것만
        if re.match(r'^[\d\.\s]*[A-Za-z가-힣]', line):
            # 중복 제거
            cap = re.sub(r'\s+', ' ', line).strip()[:60]
            if cap and cap not in [c[1] for c in captions]:
                captions.append((len(captions)+1, cap))
    return captions


def assign_section_names(figures: list, sections: list, md_path: Path) -> list:
    """파싱 텍스트의 섹션 구조를 기반으로 figure에 이름 부여
    figures: [(path, w, h), ...]
    sections: [(pos, title), ...]
    Returns: [(seq, caption), ...]
    """
    if not sections:
        # 섹션 정보 없으면 순번만
        return [(i+1, f"Figure {i+1:03d}") for i in range(len(figures))]

    # 섹션별 figure 수 추정 (균등 분배 방식 대신, 이미지 순서를 유지)
    captions = []
    section_idx = 0
    per_section = max(1, len(figures) // max(1, len(sections)))

    for i, (path, w, h) in enumerate(figures):
        # 현재 섹션 찾기
        if section_idx < len(sections) - 1 and i >= (section_idx + 1) * per_section:
            section_idx = min(section_idx + 1, len(sections) - 1)
        sec_title = sections[min(section_idx, len(sections)-1)][1]
        # 섹션 내 순번
        in_sec = i - section_idx * per_section + 1
        caption = f"{sec_title}"
        captions.append((i+1, caption))

    return captions


def process_manual(img_dir_name: str, title: str, parsed_file: str = None, caption_mode: str = 'auto'):
    """매뉴얼 1개 처리
    caption_mode: 'en' | 'kr' | 'section' | 'auto'
    """
    img_dir = IMG_BASE / img_dir_name
    if not img_dir.is_dir():
        print(f"  SKIP (no dir): {img_dir_name}")
        return None

    images = get_sorted_images(img_dir)
    if not images:
        print(f"  SKIP (no imgs): {img_dir_name}")
        return None

    # 이미지 분류
    figures = []  # (path, w, h)
    icons = []
    for path in images:
        cls, w, h = classify_image(path)
        if cls == 'figure':
            figures.append((path, w, h))
        elif cls == 'icon':
            icons.append((path, w, h))

    # 캡션 추출
    md_path = PARSED_DIR / parsed_file if parsed_file else None
    captions = []

    if caption_mode == 'en':
        captions = extract_en_figures(md_path)
    elif caption_mode == 'kr':
        captions = extract_kr_figures(md_path)
    elif caption_mode == 'maintenance':
        captions = extract_maintenance_captions(md_path)
    elif caption_mode == 'section':
        # 먼저 figure/그림 패턴 시도
        if md_path and md_path.exists():
            captions = extract_kr_figures(md_path)
        # 없으면 유지보수 캡션 시도
        if not captions and md_path and md_path.exists():
            captions = extract_maintenance_captions(md_path)
        # 그래도 없으면 섹션 기반
        if not captions and md_path and md_path.exists():
            sections = extract_sections(md_path)
            if sections:
                captions = assign_section_names(figures, sections, md_path)

    # 캡션 부족 시 나머지 채우기
    if len(captions) < len(figures):
        for j in range(len(figures)):
            if j >= len(captions):
                captions.append((j+1, f"Figure {j+1:03d}"))

    print(f"  {title}: {len(images)} imgs, {len(figures)} figs, {len(captions)} caps, {len(icons)} icons")

    # 카드 생성
    cards = []
    for i, (path, w, h) in enumerate(figures):
        seq = i + 1
        if i < len(captions):
            _, cap_text = captions[i]
        else:
            cap_text = f"Figure {seq:03d}"

        thumb = make_thumb(path)
        # 구조화 파일명
        safe_cap = re.sub(r'\s+', '_', cap_text)
        safe_cap = re.sub(r'[\\/:*?"<>|]', '', safe_cap)[:50]
        fname = f"{seq:03d}_{safe_cap}{path.suffix}"

        cards.append(f"""    <div class="card">
      <div class="seq">{seq:03d}</div>
      <img src="{thumb}" alt="{cap_text}"/>
      <div class="cap">{cap_text}</div>
      <div class="fname">{fname}</div>
      <div class="size">orig: {path.name} ({w}x{h})</div>
    </div>""")

    return {
        'title': title,
        'total': len(images),
        'figures': len(figures),
        'icons': len(icons),
        'cards_html': '\n'.join(cards),
    }


# 매뉴얼 목록
MANUALS = [
    # (이미지 디렉토리, 제목, 파싱 파일, 캡션 모드)
    ('HAM-CVD L&UL Machine User Manual en_v1.0', 'CVD L&UL Machine (EN)',
     'HAM-CVD_L_UL_Machine_User_Manual_en_v1.0.md', 'en'),
    ('HAM-PVD_Unloading_User_Manual_en_v1.3', 'PVD Unloading (EN)',
     'HAM-PVD_Unloading_User_Manual_en_v1.3.md', 'en'),
    ('(완성본)유지보수 메뉴얼 - 한국야금 PVD Loading Handler', 'PVD Loading Handler',
     'Final_Maintenance_Manual_-_Korea_Tungsten_PVD_Loading_Handler.md', 'section'),
    ('[WT1724]YG1  CVD 매뉴얼', 'YG1 CVD',
     'WT1724_YG1_CVD_Manual.md', 'section'),
    ('HAM-Labeling_User_Manual_v1.1_KR', 'Labeling Machine', None, 'section'),
    ('PressHandler', 'Press Handler',
     '1._User_Manual_Press_Handler_MC.md', 'section'),
    ('Double_Side_Handler_Manual_Revised', 'Double Side Handler', None, 'section'),
    ('[OKE]201102_PVD 1호핸들러 매뉴얼(한국어)', 'PVD 1 Handler (KR)',
     'OKE_201102_PVD_1_Handler_Manual.md', 'section'),
]


def main():
    results = []

    # 1. PVD Unloading (KR) - 기존 데이터 복원
    pvd_kr_path = REPORTS / 'pvd_이미지_매칭_확인.html'
    if pvd_kr_path.exists():
        content = pvd_kr_path.read_text(encoding='utf-8')
        summary_m = re.search(r'<div class="summary">(.*?)</div>', content)
        summary = summary_m.group(1) if summary_m else ''
        grid_m = re.search(r'<div class="grid">(.*?)</div>\s*</body>', content, re.DOTALL)
        grid = grid_m.group(1).strip() if grid_m else ''
        count = grid.count('class="card"')
        if count > 0:
            results.append({
                'title': 'PVD Unloading (KR)',
                'total': count,
                'figures': count,
                'icons': 0,
                'cards_html': grid,
                'is_restored': True,
            })
            print(f"  PVD Unloading (KR): {count} cards (restored)")

    # 2. 나머지 매뉴얼 처리
    for img_dir, title, parsed, mode in MANUALS:
        print(f"Processing: {title}")
        result = process_manual(img_dir, title, parsed, mode)
        if result:
            results.append(result)

    # 통합 HTML 생성
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
  <div class="summary">Total {r['total']} imgs | Figures: {r['figures']} | Icons: {r.get('icons', 0)}</div>
  <div class="grid">
{r['cards_html']}
  </div>
</div>""")

    total_figs = sum(r['figures'] for r in results)
    total_imgs = sum(r['total'] for r in results)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>WTA Equipment Manual - Image Catalog</title>
<style>
  body {{ font-family: 'Malgun Gothic', sans-serif; background: #f5f5f5; padding: 20px; margin: 0; }}
  h1 {{ font-size: 16pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; margin-bottom: 4px; }}
  .total {{ color: #555; font-size: 10pt; margin-bottom: 16px; }}
  .tab-bar {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }}
  .tab-btn {{
    padding: 8px 14px; border: 1px solid #ccc; border-radius: 6px 6px 0 0;
    background: #fff; cursor: pointer; font-size: 9pt; font-family: 'Malgun Gothic', sans-serif;
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
  .size {{ font-size: 7pt; color: #bbb; }}
</style>
</head>
<body>
<h1>WTA Equipment Manual - Image Catalog</h1>
<div class="total">{len(results)} equipment | {total_imgs} images (Figures: {total_figs})</div>
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

    output = REPORTS / 'equipment_image_catalog.html'
    output.write_text(html, encoding='utf-8')
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\nSaved: {output}")
    print(f"Size: {size_mb:.1f} MB | {len(results)} equipment | Figures {total_figs} / Total {total_imgs}")


if __name__ == '__main__':
    main()
