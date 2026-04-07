"""통합 이미지 카탈로그 생성 - 장비별 탭 UI"""
import os
import re
from pathlib import Path

base = Path(r'C:\MES\wta-agents\reports')

catalog_files = {
    'PVD Unloading (figure)': 'pvd_unloading_이미지_매칭_확인.html',
    'PVD Unloading (KR원본)': 'pvd_unloading_kr원본_이미지_매칭_확인.html',
    'PVD Unloading (EN)': 'pvd_unloading_en_이미지_매칭_확인.html',
    'PVD Loading Handler': 'pvd_loading_handler_kr_이미지_매칭_확인.html',
    'PVD 1호 Handler (KR)': 'pvd_1호_handler_kr_이미지_매칭_확인.html',
    'CVD L&UL Machine (EN)': 'cvd_l&ul_machine_en_이미지_매칭_확인.html',
    'YG1 CVD': 'yg1_cvd_이미지_매칭_확인.html',
    'Labeling Machine': 'labeling_machine_kr_이미지_매칭_확인.html',
    'Press Handler': 'press_handler_이미지_매칭_확인.html',
    'Double Side Handler': 'double_side_handler_이미지_매칭_확인.html',
}

sections = []
for title, fname in catalog_files.items():
    fpath = base / fname
    if not fpath.exists():
        print(f"  건너뜀: {fname}")
        continue
    content = fpath.read_text(encoding='utf-8')

    summary_m = re.search(r'<div class="summary">(.*?)</div>', content)
    summary = summary_m.group(1) if summary_m else ''

    grid_m = re.search(r'<div class="grid">(.*?)</div>\s*</body>', content, re.DOTALL)
    grid = grid_m.group(1).strip() if grid_m else ''

    img_count = grid.count('class="card"')

    sections.append({
        'title': title,
        'summary': summary,
        'grid': grid,
        'count': img_count,
    })
    print(f"  추출: {title} ({img_count}개)")

tab_buttons = []
tab_contents = []
for i, sec in enumerate(sections):
    active_btn = ' active' if i == 0 else ''
    active_tab = ' style="display:block;"' if i == 0 else ' style="display:none;"'

    tab_buttons.append(
        f'<button class="tab-btn{active_btn}" onclick="showTab({i})" id="tab-btn-{i}">'
        f'{sec["title"]} <span class="badge">{sec["count"]}</span></button>'
    )
    tab_contents.append(
        f'<div class="tab-content" id="tab-{i}"{active_tab}>\n'
        f'<div class="summary">{sec["summary"]}</div>\n'
        f'<div class="grid">\n{sec["grid"]}\n</div>\n'
        f'</div>'
    )

total_images = sum(s['count'] for s in sections)

html_output = f"""<!DOCTYPE html>
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
    padding: 8px 16px; border: 1px solid #ccc; border-radius: 6px 6px 0 0;
    background: #fff; cursor: pointer; font-size: 9.5pt; font-family: '맑은 고딕', sans-serif;
    color: #555; transition: all 0.2s;
  }}
  .tab-btn:hover {{ background: #e8eaf6; }}
  .tab-btn.active {{ background: #1a237e; color: #fff; border-color: #1a237e; font-weight: 700; }}
  .badge {{ background: rgba(255,255,255,0.3); padding: 1px 6px; border-radius: 10px; font-size: 8pt; margin-left: 4px; }}
  .tab-btn.active .badge {{ background: rgba(255,255,255,0.3); }}
  .tab-btn:not(.active) .badge {{ background: #e0e0e0; color: #666; }}
  .summary {{ color: #555; font-size: 10pt; margin-bottom: 12px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 150px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; content-visibility: auto; }}
  .seq {{ font-size: 8pt; color: #aaa; margin-bottom: 3px; }}
  .cap {{ font-size: 9pt; font-weight: 700; color: #1a237e; margin-top: 6px; }}
  .fname {{ font-size: 7.5pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
</style>
</head>
<body>
<h1>WTA 장비 매뉴얼 — 이미지 카탈로그</h1>
<div class="total">{len(sections)}개 장비 | 총 {total_images}개 이미지</div>
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
  // lazy load: 탭 전환 시 해당 탭의 이미지만 로드
  var tab = document.getElementById('tab-' + idx);
  if (tab) {{
    tab.querySelectorAll('img[data-src]').forEach(function(img) {{
      img.src = img.getAttribute('data-src');
      img.removeAttribute('data-src');
    }});
  }}
}}
// 첫 탭 이미지 즉시 로드
window.addEventListener('load', function() {{ showTab(0); }});
</script>
</body>
</html>"""

output_path = base / '장비_이미지_카탈로그.html'
output_path.write_text(html_output, encoding='utf-8')
size_mb = output_path.stat().st_size / 1024 / 1024
print(f"\n통합 파일 저장: {output_path}")
print(f"크기: {size_mb:.1f} MB | {len(sections)}개 장비 | {total_images}개 이미지")
