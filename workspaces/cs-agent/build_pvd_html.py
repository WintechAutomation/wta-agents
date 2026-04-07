import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('C:/MES/wta-agents/workspaces/cs-agent/pvd_slides_data.json', encoding='utf-8') as f:
    slides = json.load(f)

COLORS = [
    '#4472C4', '#ED7D31', '#A9D18E', '#FF5C5C', '#FFC000',
    '#5B9BD5', '#70AD47', '#264478', '#9E480E', '#636363'
]
ICONS = ['📋','⚠️','🔩','🔄','⚙️','🔍','⚡','❄️','💨','🎨']

def clean(text):
    if not text:
        return ''
    return text.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

def media_html(imgs, vids):
    parts = []
    for url in imgs[:2]:
        parts.append(
            '<div class="media-item">'
            '<img src="' + url + '" alt="첨부 이미지" loading="lazy" '
            'onerror="this.parentElement.style.display=\'none\'">'
            '</div>'
        )
    for url in vids[:1]:
        parts.append(
            '<div class="media-item">'
            '<video controls preload="metadata">'
            '<source src="' + url + '">동영상 미지원</video>'
            '</div>'
        )
    if not parts:
        return '<div class="no-media">📎 첨부 미디어 없음</div>'
    return ''.join(parts)

slides_html_parts = []
for i, s in enumerate(slides):
    color = COLORS[i]
    icon = ICONS[i]
    date_str = s['received_at'][:10] if s.get('received_at') else '-'
    proj = s.get('project_name') or '-'
    customer = s.get('customer') or '-'
    serial = s.get('serial_no') or '-'
    symptom = clean(s.get('symptom') or '')
    action = clean(s.get('action') or '')
    media = media_html(s.get('img_urls', []), s.get('vid_urls', []))
    pct = round(s['total'] / 641 * 100, 1)

    has_media = bool(s.get('img_urls') or s.get('vid_urls'))
    badge_cls = 'has-media' if has_media else 'no-media-badge'
    badge_txt = '✓ 미디어 있음' if has_media else '미디어 없음'

    bar_w = min(pct * 3, 100)

    slide = (
        '<div class="slide" id="slide-' + str(i+1) + '" style="--accent:' + color + '">'
        '<div class="slide-header">'
        '<div class="rank-badge">#' + str(i+1) + '</div>'
        '<div class="header-content">'
        '<div class="category-name">' + icon + ' ' + s['category'] + '</div>'
        '<div class="stat-row">'
        '<span class="stat-total">' + str(s['total']) + '건</span>'
        '<span class="stat-pct">전체의 ' + str(pct) + '%</span>'
        '<span class="media-badge ' + badge_cls + '">' + badge_txt + '</span>'
        '</div>'
        '</div>'
        '<div class="bar-container"><div class="bar-fill" style="width:' + str(bar_w) + '%"></div></div>'
        '</div>'  # slide-header
        '<div class="slide-body">'
        '<div class="case-info">'
        '<div class="case-title">📌 ' + clean(s.get('title') or '') + '</div>'
        '<div class="case-meta">'
        '<span>🏭 ' + proj + '</span>'
        '<span>🏢 ' + customer + '</span>'
        '<span>🔢 S/N: ' + serial + '</span>'
        '<span>📅 ' + date_str + '</span>'
        '</div>'
        '</div>'
        '<div class="content-grid">'
        '<div class="text-section">'
        '<div class="section-label">🔍 증상 / 원인</div>'
        '<div class="section-body">' + (symptom or '기록 없음') + '</div>'
        '<div class="section-label mt">✅ 처리 결과</div>'
        '<div class="section-body">' + (action or '기록 없음') + '</div>'
        '</div>'
        '<div class="media-section">'
        '<div class="section-label">📷 첨부 자료</div>'
        '<div class="media-grid">' + media + '</div>'
        '</div>'
        '</div>'  # content-grid
        '</div>'  # slide-body
        '</div>'  # slide
    )
    slides_html_parts.append(slide)

nav_btns = ''.join(
    '<button class="nav-btn" onclick="goto(' + str(i+1) + ')">&#35;' + str(i+1) + ' ' + s['category'] + '</button>'
    for i, s in enumerate(slides)
)

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Malgun Gothic', '\ub9d1\uc740 \uace0\ub515', -apple-system, sans-serif;
  background: #0d1117;
  color: #e6edf3;
  min-height: 100vh;
}
.page-header {
  background: linear-gradient(135deg, #161b22 0%, #1c2433 100%);
  border-bottom: 2px solid #30363d;
  padding: 32px 48px;
  display: flex;
  align-items: center;
  gap: 24px;
}
.header-logo {
  width: 56px; height: 56px;
  background: #4472C4;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px;
}
.header-text h1 { font-size: 24px; font-weight: 700; color: #f0f6fc; }
.header-text p { font-size: 13px; color: #8b949e; margin-top: 4px; }
.header-stats { margin-left: auto; display: flex; gap: 16px; }
.stat-box {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 12px 20px;
  text-align: center;
}
.stat-box .num { font-size: 26px; font-weight: 700; color: #4472C4; }
.stat-box .lbl { font-size: 11px; color: #8b949e; margin-top: 2px; }
.nav-bar {
  position: sticky; top: 0; z-index: 100;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  padding: 0 48px;
  display: flex; gap: 4px; overflow-x: auto;
  scrollbar-width: none;
}
.nav-bar::-webkit-scrollbar { display: none; }
.nav-btn {
  padding: 12px 14px;
  border: none; background: transparent;
  color: #8b949e; cursor: pointer;
  font-size: 13px; font-family: inherit;
  white-space: nowrap;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
}
.nav-btn:hover, .nav-btn.active { color: #f0f6fc; border-bottom-color: #4472C4; }
.slides-container { padding: 32px 48px; max-width: 1400px; margin: 0 auto; }
.slide {
  background: #161b22;
  border: 1px solid #30363d;
  border-top: 4px solid var(--accent);
  border-radius: 12px;
  margin-bottom: 32px;
  overflow: hidden;
  scroll-margin-top: 56px;
}
.slide-header {
  padding: 20px 28px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #30363d;
  background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 10%, transparent) 0%, transparent 100%);
}
.rank-badge {
  width: 48px; height: 48px;
  background: var(--accent);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700;
  color: #fff; flex-shrink: 0;
}
.header-content { flex: 1; }
.category-name { font-size: 20px; font-weight: 700; color: #f0f6fc; }
.stat-row { display: flex; align-items: center; gap: 12px; margin-top: 6px; }
.stat-total { font-size: 16px; font-weight: 600; color: var(--accent); }
.stat-pct { font-size: 13px; color: #8b949e; }
.media-badge { font-size: 12px; padding: 2px 8px; border-radius: 12px; }
.has-media { background: #1f6feb; color: #fff; }
.no-media-badge { background: #30363d; color: #8b949e; }
.bar-container { width: 120px; height: 8px; background: #30363d; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 4px; }
.slide-body { padding: 24px 28px; }
.case-info { margin-bottom: 16px; }
.case-title { font-size: 16px; font-weight: 600; color: #f0f6fc; margin-bottom: 8px; }
.case-meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: 13px; color: #8b949e; }
.case-meta span { background: #21262d; padding: 4px 10px; border-radius: 6px; }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.text-section, .media-section {
  background: #0d1117;
  border: 1px solid #21262d;
  border-radius: 8px;
  padding: 16px;
}
.section-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  color: #8b949e; letter-spacing: 0.05em; margin-bottom: 8px;
}
.section-label.mt { margin-top: 14px; }
.section-body { font-size: 14px; line-height: 1.7; color: #c9d1d9; max-height: 150px; overflow-y: auto; }
.media-grid { display: flex; flex-direction: column; gap: 10px; }
.media-item { border-radius: 8px; overflow: hidden; background: #21262d; }
.media-item img { width: 100%; max-height: 200px; object-fit: contain; display: block; }
.media-item video { width: 100%; max-height: 200px; display: block; }
.no-media { text-align: center; padding: 32px; color: #484f58; font-size: 14px; }
.page-footer { text-align: center; padding: 24px; color: #484f58; font-size: 12px; border-top: 1px solid #21262d; }
@media (max-width: 900px) {
  .content-grid { grid-template-columns: 1fr; }
  .slides-container, .page-header, .nav-bar { padding-left: 16px; padding-right: 16px; }
  .header-stats { flex-wrap: wrap; }
}
"""

JS = """
function goto(n) {
  const el = document.getElementById('slide-' + n);
  if (el) el.scrollIntoView({behavior:'smooth'});
  document.querySelectorAll('.nav-btn').forEach(function(b,i){ b.classList.toggle('active', i+1===n); });
}
const observer = new IntersectionObserver(function(entries) {
  entries.forEach(function(e) {
    if (e.isIntersecting) {
      const id = parseInt(e.target.id.split('-')[1]);
      document.querySelectorAll('.nav-btn').forEach(function(b,i){ b.classList.toggle('active', i+1===id); });
    }
  });
}, {threshold: 0.4});
document.querySelectorAll('.slide').forEach(function(s){ observer.observe(s); });
"""

HTML = (
    '<!DOCTYPE html>\n'
    '<html lang="ko">\n'
    '<head>\n'
    '<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '<title>PVD CS 이력 TOP 10 에러 유형 분석</title>\n'
    '<style>\n' + CSS + '\n</style>\n'
    '</head>\n'
    '<body>\n'
    '<div class="page-header">'
    '<div class="header-logo">🏭</div>'
    '<div class="header-text">'
    '<h1>PVD 장비 CS 이력 — TOP 10 에러 유형</h1>'
    '<p>WTA 윈텍오토메이션 | 에러 카테고리별 대표 CS 사례 및 첨부 자료</p>'
    '</div>'
    '<div class="header-stats">'
    '<div class="stat-box"><div class="num">641</div><div class="lbl">총 CS 건수</div></div>'
    '<div class="stat-box"><div class="num">37</div><div class="lbl">PVD 장비 수</div></div>'
    '<div class="stat-box"><div class="num">94</div><div class="lbl">미디어 포함 건</div></div>'
    '</div>'
    '</div>\n'
    '<nav class="nav-bar">' + nav_btns + '</nav>\n'
    '<div class="slides-container">\n'
    + '\n'.join(slides_html_parts) +
    '\n</div>\n'
    '<div class="page-footer">WTA cs-agent 자동 생성 | 데이터 기준: 2026-03-31 | 총 641건 PVD CS 이력 분석</div>\n'
    '<script>\n' + JS + '\n</script>\n'
    '</body>\n</html>'
)

out = 'C:/MES/wta-agents/workspaces/cs-agent/PVD_TOP10_Slides.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('HTML saved:', out)
print('Size:', len(HTML), 'bytes')
