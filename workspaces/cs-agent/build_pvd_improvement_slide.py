import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('C:/MES/wta-agents/workspaces/cs-agent/pvd_slides_data.json', encoding='utf-8') as f:
    slides = json.load(f)

with open('C:/MES/wta-agents/workspaces/cs-agent/pvd_analysis_result.json', encoding='utf-8') as f:
    analysis = json.load(f)

# Build lookup by category
ana_map = {a['category']: a for a in analysis}

# ── 카테고리별 대응/개선 방안 (CS 이력 패턴 기반) ──
IMPROVEMENTS = {
    "기타": {
        "root_causes": ["팔레트·공구 위치 틀어짐", "원점 복귀 오류", "마모로 인한 치수 변화"],
        "countermeasures": [
            "정기 원점 교정 주기 설정 (월 1회)",
            "팔레트 픽스처 체결 토크 관리 기준 수립",
            "위치 틀어짐 자동 감지 알람 로직 추가 검토",
        ],
        "prevention": [
            "현장 작업자 원점 확인 체크리스트 운영",
            "치수 변화 이력 추적 DB 축적",
        ],
        "priority": "중",
    },
    "에러/알람": {
        "root_causes": ["서보·앰프 설정값 오류", "파라미터 초기화", "전기적 노이즈 간섭"],
        "countermeasures": [
            "에러 코드별 원인·처리 매뉴얼 표준화 및 현장 비치",
            "파라미터 백업 정책 수립 (변경 시 즉시 백업)",
            "노이즈 차폐 보강 — 케이블 트레이·접지 재점검",
        ],
        "prevention": [
            "에러 발생 패턴 통계 기반 예방 정비 일정 수립",
            "알람 이력 MES 자동 기록 → 반복 알람 조기 감지",
        ],
        "priority": "상",
    },
    "스페이서": {
        "root_causes": ["스페이서 마모·치수 공차 초과", "공급 가이드 위치 편차", "재질 노후화"],
        "countermeasures": [
            "스페이서 치수 공차 관리 기준 강화 (수입 검사 항목 추가)",
            "공급 가이드 마모 주기 분석 → 예방교체 주기 설정",
            "마모 내성 재질 사양 검토 (고객사 협의)",
        ],
        "prevention": [
            "스페이서 투입량 대비 CS 발생률 모니터링",
            "신규 스페이서 사양 적용 전 파일럿 테스트 의무화",
        ],
        "priority": "상",
    },
    "로딩/언로딩": {
        "root_causes": ["인덱스 위치 편차", "그립퍼·핑거 조립 불량", "서보 파라미터 드리프트"],
        "countermeasures": [
            "로딩/언로딩 인덱스 티치 포인트 정기 재교정 (분기 1회)",
            "그립퍼 체결 토크 기준 문서화 및 작업 표준 적용",
            "서보 파라미터 정기 점검 항목 PM 체크리스트 포함",
        ],
        "prevention": [
            "픽앤플레이스 성공률 자동 집계 → 임계치 알람",
            "인덱스 위치 편차 트렌드 기록",
        ],
        "priority": "상",
    },
    "기계/실린더": {
        "root_causes": ["실린더 로드·씰 마모", "윤활 불량", "반복 충격에 의한 변형"],
        "countermeasures": [
            "실린더 씰 키트 교체 주기 표준화 (6개월 또는 작동횟수 기준)",
            "윤활 포인트별 급유 주기 PM 스케줄 등록",
            "실린더 속도·압력 설정값 기준 문서화",
        ],
        "prevention": [
            "실린더 동작 속도 이상 감지 로직 추가",
            "PM 교체 이력 MES 기록",
        ],
        "priority": "중",
    },
    "센서/감지": {
        "root_causes": ["센서 광축 틀어짐", "오염(코팅 파우더·이물질)", "체결부 이완"],
        "countermeasures": [
            "센서 감지 거리·감도 점검을 PM 항목에 명시",
            "PVD 코팅 파우더 부착 방지를 위한 주기적 에어 블로우 절차 수립",
            "센서 마운팅 브래킷 체결 토크 관리",
        ],
        "prevention": [
            "센서 미감지 이벤트 자동 로그 기록",
            "세척 주기 단축 검토 (오염 심한 장비 대상)",
        ],
        "priority": "중",
    },
    "파워/전원": {
        "root_causes": ["전원 모듈·UPS 배터리 노후", "과전류·과열", "결선 접촉 불량"],
        "countermeasures": [
            "UPS 배터리 교체 주기 준수 (제조사 권장 3~5년)",
            "전원 모듈 정격 전압·전류 정기 측정 및 기록",
            "결선 단자 체결 상태 연 1회 전수 점검",
        ],
        "prevention": [
            "누전차단기·퓨즈 규격 재확인 및 현장 보유 재고 관리",
            "전원 이상 이벤트 실시간 모니터링 적용",
        ],
        "priority": "상",
    },
    "냉각/수냉": {
        "root_causes": ["냉각수 유량 감소", "수냉 배관 누수·막힘"],
        "countermeasures": [
            "냉각수 유량·온도 정기 측정 및 기준값 관리",
            "냉각 필터 교체 주기 설정 (반기)",
        ],
        "prevention": [
            "냉각수 온도 이상 알람 임계값 설정",
        ],
        "priority": "하",
    },
    "진공/진공도": {
        "root_causes": ["진공 펌프 오일 열화", "챔버 씰 마모·리크"],
        "countermeasures": [
            "진공 펌프 오일 교체 주기 준수 (제조사 기준)",
            "챔버 O-ring·씰 정기 교체 계획 수립",
        ],
        "prevention": [
            "진공도 도달 시간 추이 모니터링 → 펌프 성능 저하 조기 감지",
        ],
        "priority": "하",
    },
    "코팅 품질": {
        "root_causes": ["타겟 수명 초과", "챔버 오염", "공정 파라미터 편차"],
        "countermeasures": [
            "타겟 사용량 추적 및 교체 기준 수립",
            "챔버 세정 주기 표준화",
            "공정 파라미터 기준값 문서화 및 이탈 시 알람",
        ],
        "prevention": [
            "코팅 두께 샘플 검사 주기 설정",
        ],
        "priority": "중",
    },
}

PRIORITY_COLOR = {"상": "#FF5C5C", "중": "#FFC000", "하": "#70AD47"}
PRIORITY_BG    = {"상": "#2d1515", "중": "#2d2500", "하": "#1a2d15"}

COLORS = [
    '#4472C4','#ED7D31','#A9D18E','#FF5C5C','#FFC000',
    '#5B9BD5','#70AD47','#264478','#9E480E','#636363'
]
ICONS = ['📋','⚠️','🔩','🔄','⚙️','🔍','⚡','❄️','💨','🎨']

def clean(t):
    if not t: return ''
    return t.replace('<','&lt;').replace('>','&gt;').replace('\n','<br>')

def media_html(imgs, vids):
    parts = []
    for url in imgs[:2]:
        parts.append(
            '<div class="media-item">'
            '<img src="' + url + '" alt="첨부" loading="lazy" '
            'onerror="this.parentElement.style.display=\'none\'">'
            '</div>'
        )
    for url in vids[:1]:
        parts.append(
            '<div class="media-item">'
            '<video controls preload="metadata"><source src="' + url + '">동영상 미지원</video>'
            '</div>'
        )
    if not parts:
        return '<div class="no-media">📎 첨부 미디어 없음</div>'
    return ''.join(parts)

slides_html_parts = []
for i, s in enumerate(slides):
    color = COLORS[i]
    icon = ICONS[i]
    cat = s['category']
    imp = IMPROVEMENTS.get(cat, {})
    prio = imp.get('priority', '중')
    pc = PRIORITY_COLOR.get(prio, '#8b949e')
    pb = PRIORITY_BG.get(prio, '#161b22')

    pct = round(s['total'] / 641 * 100, 1)
    bar_w = min(pct * 3, 100)
    date_str = s['received_at'][:10] if s.get('received_at') else '-'

    has_media = bool(s.get('img_urls') or s.get('vid_urls'))
    badge_cls = 'has-media' if has_media else 'no-media-badge'
    badge_txt = '✓ 미디어 있음' if has_media else '미디어 없음'

    media = media_html(s.get('img_urls',[]), s.get('vid_urls',[]))

    # Root causes list
    rc_items = ''.join(
        '<li>' + rc + '</li>'
        for rc in imp.get('root_causes', [])
    )
    # Countermeasures
    cm_items = ''.join(
        '<li>' + cm + '</li>'
        for cm in imp.get('countermeasures', [])
    )
    # Prevention
    pv_items = ''.join(
        '<li>' + pv + '</li>'
        for pv in imp.get('prevention', [])
    )

    slide = (
        '<div class="slide" id="slide-' + str(i+1) + '" style="--accent:' + color + '">'

        # Header
        '<div class="slide-header">'
        '<div class="rank-badge">' + icon + '<br>#' + str(i+1) + '</div>'
        '<div class="header-content">'
        '<div class="category-name">' + cat + '</div>'
        '<div class="stat-row">'
        '<span class="stat-total">' + str(s['total']) + '건</span>'
        '<span class="stat-pct">' + str(pct) + '%</span>'
        '<span class="media-badge ' + badge_cls + '">' + badge_txt + '</span>'
        '<span class="prio-badge" style="background:' + pb + ';color:' + pc + ';border-color:' + pc + '">중요도: ' + prio + '</span>'
        '</div>'
        '</div>'
        '<div class="bar-container"><div class="bar-fill" style="width:' + str(bar_w) + '%"></div></div>'
        '</div>'

        # Body — 3-column grid
        '<div class="slide-body">'

        # Row 1: Case info
        '<div class="case-info">'
        '<div class="case-title">📌 대표 사례: ' + clean(s.get('title','')) + '</div>'
        '<div class="case-meta">'
        '<span>🏭 ' + (s.get('project_name') or '-') + '</span>'
        '<span>🏢 ' + (s.get('customer') or '-') + '</span>'
        '<span>📅 ' + date_str + '</span>'
        '</div>'
        '</div>'

        # Row 2: 3 columns
        '<div class="three-col">'

        # Col 1: 증상 + 미디어
        '<div class="col-box">'
        '<div class="col-label">🔍 증상 사례</div>'
        '<div class="section-body">' + (clean(s.get('symptom','')) or '기록 없음') + '</div>'
        '<div class="col-label mt">📷 첨부 자료</div>'
        '<div class="media-grid">' + media + '</div>'
        '</div>'

        # Col 2: 주요 원인
        '<div class="col-box">'
        '<div class="col-label">🔴 주요 원인 (CS 이력 분석)</div>'
        '<ul class="cause-list">' + rc_items + '</ul>'
        '<div class="col-label mt">✅ 대응 방안</div>'
        '<ul class="action-list">' + cm_items + '</ul>'
        '</div>'

        # Col 3: 개선/예방
        '<div class="col-box">'
        '<div class="col-label">🛡 예방·개선 방안</div>'
        '<ul class="prev-list">' + pv_items + '</ul>'
        '<div class="metric-box" style="border-color:' + pc + ';background:' + pb + '">'
        '<div class="metric-label">우선순위</div>'
        '<div class="metric-value" style="color:' + pc + '">' + prio + '</div>'
        '<div class="metric-label mt4">' + str(s['with_media']) + '건 미디어 확보</div>'
        '</div>'
        '</div>'

        '</div>'  # three-col
        '</div>'  # slide-body
        '</div>'  # slide
    )
    slides_html_parts.append(slide)

nav_btns = ''.join(
    '<button class="nav-btn" onclick="goto(' + str(i+1) + ')">#' + str(i+1) + ' ' + s['category'] + '</button>'
    for i, s in enumerate(slides)
)

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Malgun Gothic','\ub9d1\uc740 \uace0\ub515',-apple-system,sans-serif;background:#0d1117;color:#e6edf3;}
.page-header{background:linear-gradient(135deg,#161b22,#1c2433);border-bottom:2px solid #30363d;padding:28px 40px;display:flex;align-items:center;gap:20px;}
.header-logo{width:52px;height:52px;background:#4472C4;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:26px;}
.header-text h1{font-size:22px;font-weight:700;color:#f0f6fc;}
.header-text p{font-size:13px;color:#8b949e;margin-top:4px;}
.header-stats{margin-left:auto;display:flex;gap:14px;}
.stat-box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 18px;text-align:center;}
.stat-box .num{font-size:24px;font-weight:700;color:#4472C4;}
.stat-box .lbl{font-size:11px;color:#8b949e;margin-top:2px;}
.nav-bar{position:sticky;top:0;z-index:100;background:#161b22;border-bottom:1px solid #30363d;padding:0 40px;display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;}
.nav-bar::-webkit-scrollbar{display:none;}
.nav-btn{padding:10px 12px;border:none;background:transparent;color:#8b949e;cursor:pointer;font-size:12px;font-family:inherit;white-space:nowrap;border-bottom:3px solid transparent;transition:all .2s;}
.nav-btn:hover,.nav-btn.active{color:#f0f6fc;border-bottom-color:#4472C4;}
.slides-container{padding:28px 40px;max-width:1500px;margin:0 auto;}
.slide{background:#161b22;border:1px solid #30363d;border-top:4px solid var(--accent);border-radius:12px;margin-bottom:28px;overflow:hidden;scroll-margin-top:52px;}
.slide-header{padding:16px 24px;display:flex;align-items:center;gap:14px;border-bottom:1px solid #30363d;background:linear-gradient(90deg,color-mix(in srgb,var(--accent) 8%,transparent),transparent);}
.rank-badge{width:52px;height:52px;background:var(--accent);border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0;line-height:1.3;}
.header-content{flex:1;}
.category-name{font-size:19px;font-weight:700;color:#f0f6fc;}
.stat-row{display:flex;align-items:center;gap:10px;margin-top:5px;flex-wrap:wrap;}
.stat-total{font-size:15px;font-weight:600;color:var(--accent);}
.stat-pct{font-size:12px;color:#8b949e;}
.media-badge,.prio-badge{font-size:11px;padding:2px 8px;border-radius:10px;}
.has-media{background:#1f6feb;color:#fff;}
.no-media-badge{background:#30363d;color:#8b949e;}
.prio-badge{border:1px solid;font-weight:600;}
.bar-container{width:100px;height:7px;background:#30363d;border-radius:4px;overflow:hidden;}
.bar-fill{height:100%;background:var(--accent);border-radius:4px;}
.slide-body{padding:20px 24px;}
.case-info{margin-bottom:14px;}
.case-title{font-size:15px;font-weight:600;color:#f0f6fc;margin-bottom:6px;}
.case-meta{display:flex;flex-wrap:wrap;gap:6px;font-size:12px;color:#8b949e;}
.case-meta span{background:#21262d;padding:3px 8px;border-radius:5px;}
.three-col{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;}
@media(max-width:1100px){.three-col{grid-template-columns:1fr 1fr;}}
@media(max-width:700px){.three-col{grid-template-columns:1fr;}.slides-container,.page-header,.nav-bar{padding-left:14px;padding-right:14px;}.header-stats{flex-wrap:wrap;}}
.col-box{background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:14px;}
.col-label{font-size:11px;font-weight:600;text-transform:uppercase;color:#8b949e;letter-spacing:.05em;margin-bottom:8px;}
.col-label.mt{margin-top:14px;}
.section-body{font-size:13px;line-height:1.7;color:#c9d1d9;max-height:120px;overflow-y:auto;}
.cause-list,.action-list,.prev-list{font-size:13px;line-height:1.8;color:#c9d1d9;padding-left:18px;}
.cause-list li{color:#ff8b8b;}
.action-list li{color:#79c0ff;}
.prev-list li{color:#a5d6a7;}
.media-grid{display:flex;flex-direction:column;gap:8px;margin-top:4px;}
.media-item{border-radius:6px;overflow:hidden;background:#21262d;}
.media-item img{width:100%;max-height:180px;object-fit:contain;display:block;}
.media-item video{width:100%;max-height:180px;display:block;}
.no-media{text-align:center;padding:20px;color:#484f58;font-size:13px;}
.metric-box{margin-top:14px;border:1px solid;border-radius:8px;padding:12px;text-align:center;}
.metric-label{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;}
.metric-label.mt4{margin-top:4px;}
.metric-value{font-size:28px;font-weight:700;margin:4px 0;}
.page-footer{text-align:center;padding:20px;color:#484f58;font-size:11px;border-top:1px solid #21262d;}
"""

JS = """
function goto(n){
  var el=document.getElementById('slide-'+n);
  if(el)el.scrollIntoView({behavior:'smooth'});
  document.querySelectorAll('.nav-btn').forEach(function(b,i){b.classList.toggle('active',i+1===n);});
}
var obs=new IntersectionObserver(function(entries){
  entries.forEach(function(e){
    if(e.isIntersecting){
      var id=parseInt(e.target.id.split('-')[1]);
      document.querySelectorAll('.nav-btn').forEach(function(b,i){b.classList.toggle('active',i+1===id);});
    }
  });
},{threshold:0.3});
document.querySelectorAll('.slide').forEach(function(s){obs.observe(s);});
"""

HTML = (
    '<!DOCTYPE html><html lang="ko">\n'
    '<head><meta charset="UTF-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
    '<title>PVD CS TOP10 — 대응 및 개선 방안</title>'
    '<style>' + CSS + '</style></head>\n'
    '<body>\n'
    '<div class="page-header">'
    '<div class="header-logo">🏭</div>'
    '<div class="header-text">'
    '<h1>PVD 장비 CS 이력 TOP 10 — 대응 및 개선 방안</h1>'
    '<p>WTA 윈텍오토메이션 | CS 이력 패턴 분석 기반 원인·대응·예방 방안</p>'
    '</div>'
    '<div class="header-stats">'
    '<div class="stat-box"><div class="num">641</div><div class="lbl">총 CS 건수</div></div>'
    '<div class="stat-box"><div class="num">37</div><div class="lbl">PVD 장비 수</div></div>'
    '<div class="stat-box"><div class="num">4</div><div class="lbl">상 우선순위 항목</div></div>'
    '</div>'
    '</div>\n'
    '<nav class="nav-bar">' + nav_btns + '</nav>\n'
    '<div class="slides-container">\n'
    + '\n'.join(slides_html_parts) +
    '\n</div>\n'
    '<div class="page-footer">WTA cs-agent 자동 생성 | 데이터 기준: 2026-03-31 | 641건 PVD CS 이력 패턴 분석</div>\n'
    '<script>' + JS + '</script>\n'
    '</body></html>'
)

out = 'C:/MES/wta-agents/workspaces/cs-agent/PVD_TOP10_Improvements.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('HTML saved:', out)
print('Size:', len(HTML), 'bytes')
