"""
통합 카탈로그 재구축
- PVD Unloading (KR): 기존 pvd_이미지_매칭_확인.html 데이터 그대로 사용
- 나머지: 개별 카탈로그 데이터 그대로 사용
"""
import re
from pathlib import Path

REPORTS = Path(r'C:\MES\wta-agents\reports')


def extract_grid(html_path: Path) -> tuple[str, str, int]:
    """HTML에서 summary + grid 콘텐츠 추출"""
    if not html_path.exists():
        return ('', '', 0)
    content = html_path.read_text(encoding='utf-8')
    summary_m = re.search(r'<div class="summary">(.*?)</div>', content)
    summary = summary_m.group(1) if summary_m else ''
    grid_m = re.search(r'<div class="grid">(.*?)</div>\s*</body>', content, re.DOTALL)
    grid = grid_m.group(1).strip() if grid_m else ''
    count = grid.count('class="card"')
    return (summary, grid, count)


# 탭 목록: (제목, 소스 파일)
TABS = [
    ('PVD Unloading (KR)', 'pvd_이미지_매칭_확인.html'),
]

tabs_data = []
for title, fname in TABS:
    summary, grid, count = extract_grid(REPORTS / fname)
    if count > 0:
        tabs_data.append({'title': title, 'summary': summary, 'grid': grid, 'count': count})
        print(f'{title}: {count}개 (기존 데이터 복원)')

# 통합 HTML
tab_buttons = []
tab_contents = []
for i, t in enumerate(tabs_data):
    active = ' active' if i == 0 else ''
    display = 'block' if i == 0 else 'none'
    tab_buttons.append(
        f'<button class="tab-btn{active}" onclick="showTab({i})">'
        f'{t["title"]} <span class="badge">{t["count"]}</span></button>'
    )
    tab_contents.append(f"""<div class="tab-content" id="tab-{i}" style="display:{display};">
<div class="summary">{t['summary']}</div>
<div class="grid">
{t['grid']}
</div>
</div>""")

total = sum(t['count'] for t in tabs_data)

html = f"""<!DOCTYPE html>
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
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .card img {{ width: 100%; height: 160px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }}
  .seq {{ font-size: 9pt; color: #aaa; margin-bottom: 4px; }}
  .cap {{ font-size: 10pt; font-weight: 700; color: #1a237e; margin-top: 8px; }}
  .fname {{ font-size: 8pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }}
  .size {{ font-size: 8pt; color: #bbb; margin-top: 2px; }}
</style>
</head>
<body>
<h1>WTA 장비 매뉴얼 - 이미지 카탈로그</h1>
<div class="total">{len(tabs_data)}개 장비 | 총 {total}개 이미지</div>
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
out.write_text(html, encoding='utf-8')
sz = out.stat().st_size / 1024 / 1024
print(f'\n저장: {out} ({sz:.1f} MB)')
print(f'{len(tabs_data)}개 장비 | {total}개 이미지')
