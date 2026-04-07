"""Generate complete manual-template.html with all 13 chapters in Korean."""
import json
import os

IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "templates", "images")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "templates", "manual-template.html")

with open(os.path.join(IMG_DIR, "base64-data.json"), "r") as f:
    img = json.load(f)

# Page counter for alternating headers
page_num = [0]

def header(even=True):
    """Return header bar HTML."""
    key = "header_even" if even else "header_odd"
    return f'<div class="page-header"><img src="{img[key]}" alt="header"></div>'

def footer(section, num, even=True):
    """Return footer HTML."""
    cls = "page-footer-even" if even else "page-footer-odd"
    return f'''<div class="page-footer {cls}">
    <img class="footer-logo" src="{img["wta_logo"]}" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">{num}</span>
  </div>'''

def page_start(section_label, num, even=True):
    """Return page opening with header."""
    return f'''<div class="page">
  {header(even)}
  <div class="page-section-label">{section_label}</div>
  <div class="page-body">'''

def page_end(section, num, even=True):
    """Return page closing with footer."""
    return f'''  </div>
  {footer(section, num, even)}
</div>'''

def danger_box(title, content):
    return f'''<div class="notice danger">
      <img class="notice-icon" src="{img["icon_danger"]}" alt="위험">
      <div class="notice-content">
        <div class="notice-title">{title}</div>
        {content}
      </div>
    </div>'''

def warning_box(title, content):
    return f'''<div class="notice">
      <img class="notice-icon" src="{img["icon_warning"]}" alt="경고">
      <div class="notice-content">
        <div class="notice-title">{title}</div>
        {content}
      </div>
    </div>'''

def caution_box(title, content):
    return f'''<div class="notice caution">
      <img class="notice-icon" src="{img["icon_caution"]}" alt="금지">
      <div class="notice-content">
        <div class="notice-title">{title}</div>
        {content}
      </div>
    </div>'''

def info_box(title, content):
    return f'''<div class="notice info">
      <img class="notice-icon" src="{img["icon_info"]}" alt="참고">
      <div class="notice-content">
        <div class="notice-title">{title}</div>
        {content}
      </div>
    </div>'''

def fig(caption, fig_key=None):
    if fig_key and fig_key in img:
        return f'''<div class="figure">
      <img src="{img[fig_key]}" alt="{caption}">
      <div class="figure-caption">{caption}</div>
    </div>'''
    return f'''<div class="figure">
      <div class="figure-placeholder">{caption}</div>
      <div class="figure-caption">{caption}</div>
    </div>'''

# Build HTML
parts = []

# ===== CSS (same as before but included inline) =====
parts.append(f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PVD Unloading User Manual — (주)윈텍오토메이션</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;900&display=swap');
  :root {{
    --wta-red: #C0392B;
    --wta-red-dark: #A93226;
    --wta-red-light: #E74C3C;
    --wta-gray: #7F8C8D;
    --text-primary: #0d0d0d;
    --text-secondary: #333;
    --text-light: #666;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  @page {{ size: A4; margin: 0; }}
  body {{
    font-family: '맑은 고딕', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
    font-size: 9.5pt; color: var(--text-primary); line-height: 1.6; background: #e8e8e8;
  }}
  .page {{
    width: 210mm; min-height: 297mm; margin: 8mm auto; background: #fff;
    box-shadow: 0 1px 6px rgba(0,0,0,0.15); position: relative; overflow: hidden;
    page-break-after: always;
  }}
  .page:last-child {{ page-break-after: auto; }}
  .page-body {{ padding: 0 18mm 25mm 18mm; }}
  @media print {{
    body {{ background: #fff; }}
    .page {{ margin: 0; box-shadow: none; width: 100%; min-height: auto; }}
  }}
  .page-header {{ width: 100%; margin-bottom: 8px; }}
  .page-header img {{ width: 100%; height: auto; display: block; }}
  .page-section-label {{
    text-align: right; font-size: 8.5pt; color: var(--text-light);
    font-style: italic; padding: 0 18mm 4px 0; margin-bottom: 8px;
  }}
  .page-footer {{
    position: absolute; bottom: 0; left: 0; right: 0;
    display: flex; align-items: center; padding: 6px 18mm 10mm;
  }}
  .page-footer-even {{ flex-direction: row; }}
  .page-footer-odd {{ flex-direction: row-reverse; }}
  .page-footer .footer-logo {{ height: 28px; }}
  .page-footer .footer-slogan {{
    font-size: 8pt; color: var(--text-light); font-style: italic; margin: 0 12px; flex: 1;
  }}
  .page-footer-even .footer-slogan {{ text-align: left; }}
  .page-footer-odd .footer-slogan {{ text-align: right; }}
  .page-footer .page-num {{ font-size: 9pt; font-weight: 600; color: var(--text-secondary); }}

  .cover-page {{ position: relative; width: 210mm; min-height: 297mm; }}
  .cover-stripe {{ position: absolute; top: 0; right: 0; width: 22mm; height: 100%; min-height: 297mm; }}
  .cover-stripe-main {{ position: absolute; top: 0; right: 0; width: 14mm; height: 85%; background: var(--wta-red); }}
  .cover-stripe-accent1 {{ position: absolute; top: 0; right: 16mm; width: 3mm; height: 12%; background: var(--wta-red); transform: skewY(-2deg); }}
  .cover-stripe-accent2 {{ position: absolute; top: 4%; right: 16mm; width: 3mm; height: 10%; background: var(--wta-red); transform: skewY(-2deg); }}
  .cover-stripe-gradient {{ position: absolute; bottom: 0; right: 0; width: 14mm; height: 15%; background: linear-gradient(180deg, var(--wta-red) 0%, #E67E73 60%, var(--wta-gray) 100%); }}
  .cover-logo {{ position: absolute; top: 28mm; left: 25mm; }}
  .cover-logo img {{ height: 48px; }}
  .cover-content {{ position: absolute; top: 38%; left: 25mm; right: 35mm; }}
  .cover-title {{ font-size: 20pt; font-weight: 700; color: var(--text-primary); line-height: 1.4; margin-bottom: 20px; }}
  .cover-meta {{ font-size: 10pt; color: var(--text-light); line-height: 2; margin-top: 30px; }}
  .cover-meta-label {{ display: inline-block; width: 80px; font-weight: 600; color: var(--text-secondary); }}
  .cover-bottom {{ position: absolute; bottom: 25mm; left: 25mm; }}
  .cover-company {{ font-size: 10pt; font-weight: 700; color: var(--text-secondary); }}
  .cover-company-en {{ font-size: 8pt; color: #999; }}

  .back-cover {{ display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 260mm; padding: 40mm; }}
  .back-cover img {{ width: 120px; }}

  .toc-title {{ font-size: 22pt; font-weight: 700; color: var(--text-primary); margin-bottom: 20px; }}
  .toc-list {{ list-style: none; }}
  .toc-chapter {{ font-size: 11pt; font-weight: 700; color: var(--text-primary); padding: 6px 0 3px; display: flex; justify-content: space-between; border-bottom: 1px solid #eee; }}
  .toc-section {{ font-size: 9.5pt; font-weight: 400; color: var(--text-secondary); padding: 3px 0 3px 16px; display: flex; justify-content: space-between; }}
  .toc-subsection {{ font-size: 9pt; font-weight: 400; color: var(--text-light); padding: 2px 0 2px 32px; display: flex; justify-content: space-between; }}
  .toc-subsection .toc-marker {{ color: var(--wta-red); margin-right: 6px; font-size: 8pt; }}
  .toc-page {{ color: var(--text-light); flex-shrink: 0; margin-left: 8px; }}
  .toc-dots {{ flex: 1; border-bottom: 1px dotted #ccc; margin: 0 8px; align-self: flex-end; margin-bottom: 3px; }}

  h1.chapter {{ font-size: 18pt; font-weight: 700; color: var(--text-primary); padding-bottom: 8px; border-bottom: 3px solid var(--wta-red); margin-bottom: 16px; page-break-after: avoid; }}
  h2.section {{ font-size: 12pt; font-weight: 700; color: var(--text-primary); margin: 20px 0 10px; padding-bottom: 4px; border-bottom: 1px solid #ddd; page-break-after: avoid; }}
  h3.subsection {{ font-size: 10pt; font-weight: 700; color: var(--text-primary); margin: 14px 0 6px; padding-left: 12px; border-left: 4px solid #333; page-break-after: avoid; }}
  p {{ font-size: 9.5pt; color: var(--text-primary); line-height: 1.7; margin-bottom: 8px; text-align: justify; }}

  .notice {{ display: flex; align-items: flex-start; gap: 12px; background: #FFF3CD; border: 2px solid #F0AD4E; padding: 10px 14px; margin: 12px 0; font-size: 9pt; }}
  .notice-icon {{ width: 44px; height: 44px; flex-shrink: 0; object-fit: contain; }}
  .notice-content {{ flex: 1; }}
  .notice-title {{ font-weight: 700; margin-bottom: 4px; }}
  .notice.danger {{ background: #FDEDEE; border-color: var(--wta-red); }}
  .notice.danger .notice-title {{ color: var(--wta-red-dark); }}
  .notice.caution {{ background: #FFF8E1; border-color: #FFC107; }}
  .notice.info {{ background: #EBF5FB; border-color: #2E86C1; }}
  .notice.info .notice-title {{ color: #1B4F72; }}

  table.manual-table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 9pt; }}
  table.manual-table th {{ background: #F2F2F2; color: var(--text-primary); font-weight: 600; padding: 6px 10px; text-align: center; border: 1px solid #bbb; }}
  table.manual-table td {{ padding: 5px 10px; border: 1px solid #ddd; vertical-align: middle; }}
  table.manual-table tr:nth-child(even) {{ background: #fafafa; }}

  .figure {{ text-align: center; margin: 16px 0; page-break-inside: avoid; }}
  .figure img {{ max-width: 100%; max-height: 180mm; border: 1px solid #e0e0e0; }}
  .figure-caption {{ font-size: 8.5pt; color: var(--text-secondary); margin-top: 6px; font-weight: 700; text-align: center; }}
  .figure-placeholder {{ width: 100%; height: 100px; background: #f5f5f5; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; color: #999; font-size: 9pt; }}

  ol.steps {{ margin: 8px 0 8px 24px; font-size: 9.5pt; }}
  ol.steps li {{ margin-bottom: 6px; line-height: 1.6; }}
  ul.items {{ margin: 8px 0 8px 20px; font-size: 9.5pt; list-style: disc; }}
  ul.items li {{ margin-bottom: 4px; line-height: 1.6; }}

  table.error-table td:first-child {{ font-weight: 600; text-align: center; color: var(--wta-red); }}

  .maint-table {{ font-size: 8.5pt; }}
  .maint-table th {{ font-size: 8.5pt; padding: 4px 6px; }}
  .maint-table td {{ font-size: 8.5pt; padding: 4px 6px; }}

  .parts-table td {{ font-size: 8pt; padding: 3px 6px; }}
  .parts-table th {{ font-size: 8pt; padding: 3px 6px; }}
</style>
</head>
<body>

<!-- ═══ PAGE 1: 표지 ═══ -->
<div class="page cover-page">
  <div class="cover-stripe">
    <div class="cover-stripe-accent1"></div>
    <div class="cover-stripe-accent2"></div>
    <div class="cover-stripe-main"></div>
    <div class="cover-stripe-gradient"></div>
  </div>
  <div class="cover-logo"><img src="{img["wta_logo"]}" alt="WTA"></div>
  <div class="cover-content">
    <div class="cover-title">PVD Unloading User Manual</div>
    <div class="cover-meta">
      <div><span class="cover-meta-label">Doc No.</span>0001</div>
      <div><span class="cover-meta-label">Version</span>1.0</div>
      <div><span class="cover-meta-label">Date</span>2026-03-31</div>
      <div><span class="cover-meta-label">Author</span>WTA</div>
      <div><span class="cover-meta-label">Customer</span></div>
    </div>
  </div>
  <div class="cover-bottom">
    <div class="cover-company">(주)윈텍오토메이션</div>
    <div class="cover-company-en">WINTEC AUTOMATION Co., Ltd.</div>
  </div>
</div>

<!-- ═══ PAGE 2: 개정 이력 ═══ -->
{page_start("개정 이력", "ii", True)}
    <h1 class="chapter">개정 이력</h1>
    <table class="manual-table">
      <thead><tr><th style="width:60px;">버전</th><th style="width:100px;">날짜</th><th>변경 내용</th><th style="width:80px;">작성자</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1.0</td><td style="text-align:center;">2026-03-31</td><td>초판 발행</td><td style="text-align:center;">WTA</td></tr>
      </tbody>
    </table>
{page_end("개정 이력", "ii", True)}

<!-- ═══ PAGE 3: 목차 (1/2) ═══ -->
{page_start("목차", "iii", False)}
    <h1 class="toc-title">목차</h1>
    <ul class="toc-list">
      <li class="toc-chapter"><span>1. 개요</span><span class="toc-dots"></span><span class="toc-page">5</span></li>
      <li class="toc-section"><span>1.1. 사용 설명서</span><span class="toc-dots"></span><span class="toc-page">5</span></li>
      <li class="toc-section"><span>1.2. 장비 사용 안내</span><span class="toc-dots"></span><span class="toc-page">6</span></li>
      <li class="toc-section"><span>1.3. 장비 외관</span><span class="toc-dots"></span><span class="toc-page">7</span></li>

      <li class="toc-chapter"><span>2. 안전 유의 사항</span><span class="toc-dots"></span><span class="toc-page">10</span></li>
      <li class="toc-section"><span>2.1. 위험 표시 안내</span><span class="toc-dots"></span><span class="toc-page">10</span></li>
      <li class="toc-section"><span>2.2. 장비 사용 지침 준수 및 면책</span><span class="toc-dots"></span><span class="toc-page">10</span></li>
      <li class="toc-section"><span>2.3. 부착 경고 표시 및 안전 유의 사항</span><span class="toc-dots"></span><span class="toc-page">11</span></li>
      <li class="toc-section"><span>2.4. 비상 정지 버튼</span><span class="toc-dots"></span><span class="toc-page">12</span></li>
      <li class="toc-section"><span>2.5. 특수 위험 유의 사항</span><span class="toc-dots"></span><span class="toc-page">14</span></li>

      <li class="toc-chapter"><span>3. 시운전</span><span class="toc-dots"></span><span class="toc-page">16</span></li>
      <li class="toc-section"><span>3.1. 장비 운반 및 취급</span><span class="toc-dots"></span><span class="toc-page">16</span></li>
      <li class="toc-section"><span>3.2. 조립 및 설치</span><span class="toc-dots"></span><span class="toc-page">16</span></li>
      <li class="toc-section"><span>3.3. 전원 ON/OFF</span><span class="toc-dots"></span><span class="toc-page">17</span></li>
      <li class="toc-section"><span>3.4. 기본 조작</span><span class="toc-dots"></span><span class="toc-page">19</span></li>

      <li class="toc-chapter"><span>4. 메인 화면</span><span class="toc-dots"></span><span class="toc-page">20</span></li>
      <li class="toc-section"><span>4.1. 메인 화면 구조</span><span class="toc-dots"></span><span class="toc-page">20</span></li>

      <li class="toc-chapter"><span>5. 모델 관리</span><span class="toc-dots"></span><span class="toc-page">23</span></li>
      <li class="toc-section"><span>5.1. 모델 생성 및 설정</span><span class="toc-dots"></span><span class="toc-page">23</span></li>
      <li class="toc-section"><span>5.2. 패턴 설정</span><span class="toc-dots"></span><span class="toc-page">24</span></li>

      <li class="toc-chapter"><span>6. 팔레트 관리</span><span class="toc-dots"></span><span class="toc-page">25</span></li>
      <li class="toc-section"><span>6.1. 팔레트 관리 설정</span><span class="toc-dots"></span><span class="toc-page">25</span></li>
      <li class="toc-section"><span>6.2. 팔레트 원점 설정</span><span class="toc-dots"></span><span class="toc-page">27</span></li>
      <li class="toc-section"><span>6.3. 봉 관리 설정</span><span class="toc-dots"></span><span class="toc-page">28</span></li>
      <li class="toc-section"><span>6.4. 스페이서 관리 설정</span><span class="toc-dots"></span><span class="toc-page">29</span></li>

      <li class="toc-chapter"><span>7. 적재 관리</span><span class="toc-dots"></span><span class="toc-page">30</span></li>
      <li class="toc-section"><span>7.1. 모델 선택 및 LOT 입력</span><span class="toc-dots"></span><span class="toc-page">30</span></li>
      <li class="toc-section"><span>7.2. 팔레트 설정</span><span class="toc-dots"></span><span class="toc-page">31</span></li>
      <li class="toc-section"><span>7.3. 인덱스 봉 설정</span><span class="toc-dots"></span><span class="toc-page">32</span></li>
    </ul>
{page_end("목차", "iii", False)}

<!-- ═══ PAGE 4: 목차 (2/2) ═══ -->
{page_start("목차", "iv", True)}
    <ul class="toc-list">
      <li class="toc-chapter"><span>8. 환경설정</span><span class="toc-dots"></span><span class="toc-page">33</span></li>
      <li class="toc-section"><span>8.1. 기본 설정</span><span class="toc-dots"></span><span class="toc-page">33</span></li>
      <li class="toc-section"><span>8.2. 팔레트 동작 설정</span><span class="toc-dots"></span><span class="toc-page">34</span></li>
      <li class="toc-section"><span>8.3. 로터리 적재 설정</span><span class="toc-dots"></span><span class="toc-page">35</span></li>

      <li class="toc-chapter"><span>9. 작업 위치</span><span class="toc-dots"></span><span class="toc-page">36</span></li>
      <li class="toc-section"><span>9.1. 티칭 위치 설정</span><span class="toc-dots"></span><span class="toc-page">36</span></li>

      <li class="toc-chapter"><span>10. 자동 운전</span><span class="toc-dots"></span><span class="toc-page">38</span></li>
      <li class="toc-section"><span>10.1. 원점 복귀</span><span class="toc-dots"></span><span class="toc-page">38</span></li>
      <li class="toc-section"><span>10.2. 시작 및 일시정지</span><span class="toc-dots"></span><span class="toc-page">39</span></li>
      <li class="toc-section"><span>10.3. 정지</span><span class="toc-dots"></span><span class="toc-page">39</span></li>
      <li class="toc-section"><span>10.4. 카메라 위치 보정</span><span class="toc-dots"></span><span class="toc-page">40</span></li>
      <li class="toc-section"><span>10.5. 이미지 설정</span><span class="toc-dots"></span><span class="toc-page">41</span></li>
      <li class="toc-section"><span>10.6. 소모품 확인</span><span class="toc-dots"></span><span class="toc-page">42</span></li>

      <li class="toc-chapter"><span>11. 작업자 조작 순서</span><span class="toc-dots"></span><span class="toc-page">43</span></li>
      <li class="toc-section"><span>11.1. 팔레트 설정</span><span class="toc-dots"></span><span class="toc-page">43</span></li>
      <li class="toc-section"><span>11.2. 봉 설정</span><span class="toc-dots"></span><span class="toc-page">44</span></li>
      <li class="toc-section"><span>11.3. 스페이서 설정</span><span class="toc-dots"></span><span class="toc-page">44</span></li>
      <li class="toc-section"><span>11.4. 모델 파일 생성</span><span class="toc-dots"></span><span class="toc-page">47</span></li>
      <li class="toc-section"><span>11.5. 적재 설정</span><span class="toc-dots"></span><span class="toc-page">48</span></li>
      <li class="toc-section"><span>11.6. 환경설정</span><span class="toc-dots"></span><span class="toc-page">49</span></li>
      <li class="toc-section"><span>11.7. 티칭 선택</span><span class="toc-dots"></span><span class="toc-page">49</span></li>
      <li class="toc-section"><span>11.8. 운전 시작</span><span class="toc-dots"></span><span class="toc-page">50</span></li>
      <li class="toc-section"><span>11.9. 비전 설정</span><span class="toc-dots"></span><span class="toc-page">51</span></li>

      <li class="toc-chapter"><span>12. 에러 알람</span><span class="toc-dots"></span><span class="toc-page">55</span></li>
      <li class="toc-section"><span>12.1. 에러 리스트</span><span class="toc-dots"></span><span class="toc-page">55</span></li>

      <li class="toc-chapter"><span>13. 유지보수</span><span class="toc-dots"></span><span class="toc-page">62</span></li>
      <li class="toc-section"><span>13.1. 정기 점검</span><span class="toc-dots"></span><span class="toc-page">62</span></li>
      <li class="toc-section"><span>13.2. 자주 발생하는 문제</span><span class="toc-dots"></span><span class="toc-page">86</span></li>
      <li class="toc-section"><span>13.3. 소모품 리스트</span><span class="toc-dots"></span><span class="toc-page">89</span></li>

      <li class="toc-chapter"><span>부록 A. 도면</span><span class="toc-dots"></span><span class="toc-page">91</span></li>
    </ul>
{page_end("목차", "iv", True)}
''')

# ═══ Chapter 1: 개요 ═══
parts.append(f'''
{page_start("1. 개요", 5, True)}
    <h1 class="chapter">1. 개요</h1>
    <h2 class="section">1.1. 사용 설명서</h2>
    <h3 class="subsection">참고 사항</h3>
    <p>본 사용 설명서는 아래 장비 모델의 사용, 설정, 운영 및 관리에 대해 상세히 설명합니다.</p>
    <p>시운전, 유지보수 또는 수리 작업 전에 작업자는 반드시 본 사용 설명서를 읽고 이해해야 합니다.</p>
    <p>또한 안전 유의 사항에 일반적인 안전 정보가 제공됩니다.</p>
    <p>본 사용 설명서는 설치 장소에 항상 비치하여야 하며, 안전하고 올바른 사용을 위해 반드시 숙지하여야 합니다.</p>
    {info_box("참고", "<ul class='items'><li>본 설명서의 그림은 세부 사항을 설명하기 위해 커버나 안전 보호대를 제거한 상태로 그려져 있을 수 있습니다.</li><li>설명서의 그림 및 사진은 대표적인 예시이며 납품된 장비와 다를 수 있습니다.</li><li>손상 또는 분실로 교체 매뉴얼이 필요한 경우 WTA에 문의하십시오.</li><li>고객의 제품 수정으로 인한 문제에 대해서는 책임지지 않으며, 비인가 수정은 보증을 무효화합니다.</li></ul>")}
    <h3 class="subsection">장비 표시</h3>
    <table class="manual-table">
      <thead><tr><th>모델명</th><th>HAM-PVD-UL (Unloading)</th></tr></thead>
      <tbody>
        <tr><td>장비 치수</td><td>1,800(W) × 1,850(D) × 2,150(H) mm</td></tr>
        <tr><td>공급 전압</td><td>400V / 30A / 3Phase / 50,60Hz</td></tr>
        <tr><td>공압</td><td>Ø12 / 0.5MPa</td></tr>
      </tbody>
    </table>
    <table class="manual-table">
      <thead><tr><th>표시</th><th>의미</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;"><img src="{img["icon_danger"]}" style="height:28px;" alt="위험"></td><td>위험</td><td>잘못 사용하면 사망 또는 중상의 위험</td></tr>
        <tr><td style="text-align:center;"><img src="{img["icon_warning"]}" style="height:28px;" alt="경고"></td><td>주의</td><td>잘못 사용하면 경상 또는 재산 피해 가능</td></tr>
        <tr><td style="text-align:center;"><img src="{img["icon_caution"]}" style="height:28px;" alt="금지"></td><td>금지</td><td>해당 행위를 절대 하지 말 것</td></tr>
      </tbody>
    </table>

    <h2 class="section">1.2. 장비 사용 안내</h2>
    <h3 class="subsection">운영 담당자 안내</h3>
    <ul class="items">
      <li>시운전 전 사용 설명서를 숙지하십시오.</li>
      <li>안전 관련 기술 사항에 특히 주의하십시오.</li>
      <li>장비에 부착된 "안전 유의 사항" 표시를 반드시 확인하십시오.</li>
    </ul>
    <h3 class="subsection">장비 적용 범위</h3>
    <p>본 장비는 고객 맞춤 부품의 코팅 공정 자동화에 사용됩니다. 고객 맞춤 부가 장치 및 주변 장치(그리퍼 등)를 제공하여 장비를 최적화할 수 있습니다.</p>
    <h3 class="subsection">장비 명판</h3>
    <p>장비 명판은 유틸리티 공급 커버 내부에 부착되어 있습니다.</p>

    <h2 class="section">1.3. 장비 외관</h2>
    {fig("그림 1-1 전면부", "fig_1_1")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>No.</th><th>명칭</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>시그널 램프</td><td style="text-align:center;">5</td><td>패널 데이터 유닛 (USB, AC전원, LAN)</td></tr>
        <tr><td style="text-align:center;">2</td><td>전면 HMI (터치스크린)</td><td style="text-align:center;">6</td><td>터치 패널</td></tr>
        <tr><td style="text-align:center;">3</td><td>제어 패널</td><td style="text-align:center;">7</td><td>작업 도어</td></tr>
        <tr><td style="text-align:center;">4</td><td>키보드, 마우스</td><td style="text-align:center;">8</td><td>패널 (PC)</td></tr>
      </tbody>
    </table>
    {fig("그림 1-2 후면부", "fig_1_2")}
    {fig("그림 1-3 측면부", "fig_1_3")}
{page_end("1. 개요", 5, True)}
''')

# ═══ Chapter 2: 안전 유의 사항 ═══
parts.append(f'''
{page_start("2. 안전 유의 사항", 10, True)}
    <h1 class="chapter">2. 안전 유의 사항</h1>
    <h2 class="section">2.1. 위험 표시 안내</h2>
    <p>설치, 운전, 유지보수 및 검사 전에 본 설명서를 충분히 읽고 이해하십시오.</p>
    <p>본 문서는 안전 주의 사항을 위험, 주의, 금지로 분류합니다.</p>

    <h2 class="section">2.2. 장비 사용 지침 준수 및 면책</h2>
    <ul class="items">
      <li>장비는 본 사용 설명서에 기술된 용도로만 사용해야 합니다.</li>
      <li>그 외의 사용은 부적합 사용으로 간주되며, 이로 인한 손해에 대해 제조사는 책임지지 않습니다.</li>
      <li>적합한 사용에는 사용 설명서의 안내 사항 준수와 유지보수 점검이 포함됩니다.</li>
      <li>비인가 개조 또는 제조사와 협의하지 않은 기술 적용은 장비 안전에 영향을 줄 수 있으며, 이에 따른 손해에 대해 제조사는 책임지지 않습니다.</li>
    </ul>

    <h2 class="section">2.3. 부착 경고 표시 및 안전 유의 사항</h2>
    {danger_box("전기 위험", "<ul class='items'><li>전기 전압으로 인한 위험</li></ul><strong>주의!</strong><ul class='items'><li>수리 시 반드시 메인 전원을 차단하고 안전 장갑을 착용하십시오.</li></ul><p style='font-size:8pt;color:#666;'>부착 위치: 제어 패널 도어, 각종 배선 덕트 커버</p>")}
    {warning_box("끼임/말림 위험", "<ul class='items'><li>장비 운전 중 끼임 및 말림 위험</li></ul><strong>주의!</strong><ul class='items'><li>장비 가동 중 위험 구역에 접근하지 마십시오.</li></ul><p style='font-size:8pt;color:#666;'>부착 위치: 로터리 메커니즘 구동부, 로봇 구동부</p>")}
    {warning_box("충돌 위험", "<ul class='items'><li>돌출부 충돌 위험</li></ul><strong>주의!</strong><ul class='items'><li>장비 가동 중 위험 구역 접근을 금지하십시오.</li></ul><p style='font-size:8pt;color:#666;'>부착 위치: 로봇 구동부, 기구물 돌출부</p>")}
    {caution_box("도어 인터록 운전 중", "<ul class='items'><li>운전 중 인터록 도어를 열면 장비가 자동 정지합니다.</li></ul><strong>주의!</strong><ul class='items'><li>운전 중 도어 개방에 주의하고, 생산 중 인터록을 확인하십시오.</li></ul><p style='font-size:8pt;color:#666;'>부착 위치: 외부 도어, 작업 도어</p>")}

    <h2 class="section">2.4. 비상 정지 버튼</h2>
    <p>장비에는 여러 개의 비상 정지 버튼이 장착되어 있습니다. E-Stop 버튼은 ISO 13850 요구사항을 충족합니다.</p>
    <p>작동 시 장비 내 모든 축이 즉시 전기적으로 정지합니다. 따라서 이 기능은 인명 또는 장비 보호가 최우선인 상황에서만 사용해야 합니다.</p>
    {fig("그림 2-1 비상 정지 버튼", "fig_2_1")}
    {info_box("참고", "비상 정지로 운전이 중단된 경우, 재가동을 위해 해당 비상 정지 버튼을 시계 방향으로 회전하여 잠금을 해제해야 합니다.")}

    <h3 class="subsection">안전도어 및 작업도어</h3>
    <p>장비에는 각 방향의 접근구에 안전도어 또는 작업도어가 설치되어 있습니다.</p>
    {info_box("참고", "생산 운전 중 안전도어를 열면 장비가 자동으로 일시 정지 상태로 전환됩니다. 이후 운전을 연결하려면 모든 도어를 닫고 시작 버튼을 누르십시오.")}

    <h3 class="subsection">시그널 램프</h3>
    <table class="manual-table">
      <thead><tr><th>색상</th><th>장비 상태</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center; font-weight:600;">적색 - 유지</td><td>장비 정지 상태 (복귀 미실행 또는 생산 완료)</td></tr>
        <tr><td style="text-align:center; font-weight:600;">황색 - 유지</td><td>장비 '일시 정지' 상태</td></tr>
        <tr><td style="text-align:center; font-weight:600;">녹색 - 유지</td><td>장비 '운전' 상태</td></tr>
        <tr><td style="text-align:center; font-weight:600;">부저</td><td>비상 정지 및 알람</td></tr>
      </tbody>
    </table>

    <h2 class="section">2.5. 특수 위험 유의 사항</h2>
    <h3 class="subsection">전기 위험</h3>
    {danger_box("위험! 감전 위험", "<ul class='items'><li>전체 전원을 차단하더라도 장비 내 잔류 전력이 남아 있을 수 있습니다.</li><li>검사 시 최소 3분간 전원을 차단한 후 무전압 상태를 확인하십시오.</li><li>전기 설비 작업은 전문 교육을 받은 인력만 수행해야 합니다.</li></ul>")}
    <h3 class="subsection">시각 광선</h3>
    <ul class="items"><li>설비에 부착된 광 센서의 직접광 또는 반사광을 직접 보지 마십시오.</li><li>광선을 사람에게 향하지 않도록 하십시오.</li></ul>
    <h3 class="subsection">먼지, 증기, 연기</h3>
    <ul class="items"><li>항상 환기가 잘 되는 환경에서 장비를 운영하십시오.</li></ul>
    <h3 class="subsection">공압</h3>
    <ul class="items"><li>공압 작업은 전문 지식과 경험을 갖춘 인력이 수행해야 합니다.</li><li>공압 호스 및 라인의 접합부를 정기적으로 점검하십시오.</li></ul>
    <h3 class="subsection">구동 액추에이터</h3>
    <ul class="items"><li>가동 중인 벨트 또는 기타 액추에이터에 손을 넣지 마십시오.</li></ul>
    <h3 class="subsection">서보 축</h3>
    {danger_box("위험! 원점 데이터 손실 위험", "<ul class='items'><li>예상치 못한 원점 데이터 손실 상태에서의 시운전은 심각한 인적 피해를 초래할 수 있습니다.</li><li>원점 데이터 손실에 대한 대응 및 작업은 윈텍오토메이션 서비스 인력이 수행해야 합니다.</li></ul>")}
{page_end("2. 안전 유의 사항", 10, True)}
''')

# ═══ Chapter 3: 시운전 ═══
parts.append(f'''
{page_start("3. 시운전", 16, True)}
    <h1 class="chapter">3. 시운전</h1>
    <p>장비의 시운전은 윈텍오토메이션에 의해서만 수행되어야 합니다.</p>

    <h2 class="section">3.1. 장비 운반 및 취급</h2>
    <p>장비는 적합한 운송 지지대를 사용하여 이동해야 합니다. 사용자 재량으로 운반할 경우, 사전에 제조사와 협의하십시오.</p>
    {warning_box("주의!", "운반 시 적절한 리프팅 장비 및 운송 장치를 사용해야 합니다.")}

    <h2 class="section">3.2. 조립 및 설치</h2>
    <h3 class="subsection">공압 설치</h3>
    <p>공압 연결은 [장비 명판]에 명시된 사양에 맞게 설치해야 합니다.</p>
    <h3 class="subsection">전기 설치</h3>
    <p>전기 연결은 전문가에 의해 수행되어야 합니다. 공급 전원 케이블의 단면적을 충분히 분석하여 필요한 안전 조치를 취하십시오.</p>

    <h2 class="section">3.3. 전원 ON/OFF</h2>
    <h3 class="subsection">전원 켜기</h3>
    {fig("그림 3-1 전원 켜기", "fig_3_1")}
    <ol class="steps">
      <li>메인 전원 스위치를 "ON" 방향으로 설정합니다.</li>
      <li>Power 램프가 점등되는 것을 확인하고 대기합니다 (약 2분).</li>
      <li>제어 PC 부팅 완료 후 HMI 자동 실행을 기다립니다.</li>
    </ol>
    <h3 class="subsection">전원 끄기</h3>
    <ol class="steps">
      <li>비상 정지 버튼을 누릅니다.</li>
      <li>메인 전원 스위치를 "OFF" 방향으로 설정합니다.</li>
      <li>장비 내 잔류 전압이 비위험 수준에 도달할 때까지 대기합니다 (약 3분).</li>
    </ol>
    {info_box("참고", "메인 전원을 차단해도 내부 UPS(무정전 전원 장치)로 인해 제어 PC가 일정 시간 동작합니다. HMI 정상 저장 및 종료는 1분 이내, UPS 전원 차단은 2분 이내에 이루어집니다.")}
    {warning_box("주의!", "제어 PC의 운영 체제를 별도로 종료하지 마십시오. 위 순서를 따르지 않으면 재전원 시 정상 기동이 되지 않을 수 있습니다.")}
    <h3 class="subsection">장비 재시작</h3>
    <p>필요 시 전원 차단 절차를 실행하고, 최소 3분 대기 후 전원 투입 절차를 실행하십시오.</p>

    <h2 class="section">3.4. 기본 조작</h2>
    <h3 class="subsection">제어 패널 설명</h3>
    <p>설비 전면에 위치한 제어 스위치에 대한 설명입니다.</p>
    {fig("그림 3-2 제어 패널", "fig_3_2")}
    <table class="manual-table">
      <thead><tr><th>구분</th><th>기능</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">POWER 램프</td><td>설비의 전원 상태를 표시합니다 (녹색 LED 점등 시 전원 ON).</td></tr>
        <tr><td style="text-align:center;">START 버튼</td><td>운전 시작 후 HMI 일시 정지를 해제합니다. 버튼을 누르면 LED가 점멸 → 한 번 더 누르면 해제.</td></tr>
        <tr><td style="text-align:center;">PAUSE 버튼</td><td>HMI의 운전을 시작 및 일시 정지합니다.</td></tr>
        <tr><td style="text-align:center;">E-STOP 버튼</td><td>장비 비상 정지. 긴급 상황 시 전원을 차단합니다.</td></tr>
      </tbody>
    </table>
{page_end("3. 시운전", 16, True)}
''')

# ═══ Chapter 4: 메인 화면 ═══
parts.append(f'''
{page_start("4. 메인 화면", 20, True)}
    <h1 class="chapter">4. 메인 화면</h1>
    <h2 class="section">4.1. 메인 화면 구조</h2>
    <h3 class="subsection">위치별 기능</h3>
    {fig("그림 4-1 메인 화면", "fig_4_1")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>상태 알림 램프</td><td>ENABLE: 모터 ON/OFF, RUN: 운전, PAUSE: 일시정지, ERROR: 에러/알람, E-STOP: 비상 정지</td></tr>
        <tr><td style="text-align:center;">2</td><td>작업 상태 알림</td><td>장비의 현재 작업 내용을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>작업 모델명 표시</td><td>현재 작업 중인 모델명을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>작업 수량</td><td>SPM, 평균 SPM, 사이클 타임, 팔레트 완료 수량, 예상 작업 시간</td></tr>
        <tr><td style="text-align:center;">5</td><td>모니터링</td><td>물류/플레이트 분류 진행률 또는 검출 카메라 이미지를 실시간 표시</td></tr>
        <tr><td style="text-align:center;">6</td><td>메뉴 버튼</td><td>원점 복귀, 운전 시작, 일시 정지/재개, 적재 설정, 환경설정, 작업 위치, I/O, 운영 이력, 모델 관리 등</td></tr>
        <tr><td style="text-align:center;">7</td><td>에러 표시</td><td>에러 발생 시 표시</td></tr>
        <tr><td style="text-align:center;">8</td><td>코팅 타워 연동 상태</td><td>코팅 타워의 전체 연동 상태를 실시간 표시</td></tr>
      </tbody>
    </table>
{page_end("4. 메인 화면", 20, True)}
''')

# ═══ Chapter 5: 모델 관리 ═══
parts.append(f'''
{page_start("5. 모델 관리", 23, False)}
    <h1 class="chapter">5. 모델 관리</h1>
    <h2 class="section">5.1. 모델 생성 및 설정</h2>
    {fig("그림 5-1 모델 생성 및 설정", "fig_5_1")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>새 모델 생성</td><td>새 모델을 생성합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>모델 삭제</td><td>선택한 모델을 삭제합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>모델 복사</td><td>선택한 모델을 복사합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>설정 저장</td><td>변경된 모델 정보를 저장합니다.</td></tr>
      </tbody>
    </table>
    {fig("그림 5-2 모델 상세 설정", "fig_5_2")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>모델명</td><td>모델의 이름(파일명)을 지정합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>타입</td><td>제품의 외형을 설정합니다 (이미지 티칭 시 기본 트래커로 설정).</td></tr>
        <tr><td style="text-align:center;">3</td><td>인서트 높이</td><td>제품의 높이를 설정합니다 (봉 적재 높이 계산에 필요).</td></tr>
        <tr><td style="text-align:center;">5</td><td>팔레트</td><td>모델에 사용할 팔레트를 선택합니다.</td></tr>
        <tr><td style="text-align:center;">6</td><td>스페이서명</td><td>모델에 사용할 스페이서 파일을 선택합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">5.2. 패턴 설정</h2>
    {fig("그림 5-3 패턴 설정", "fig_5_3")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>Normal</td><td>인서트를 봉 패턴에 추가합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>Invert</td><td>인서트를 뒤집은 상태로 봉 패턴에 추가합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>Space</td><td>봉 패턴에 공간을 추가합니다.</td></tr>
      </tbody>
    </table>
{page_end("5. 모델 관리", 23, False)}
''')

# ═══ Chapter 6: 팔레트 관리 ═══
parts.append(f'''
{page_start("6. 팔레트 관리", 25, False)}
    <h1 class="chapter">6. 팔레트 관리</h1>
    <h2 class="section">6.1. 팔레트 관리 설정</h2>
    {fig("그림 6-1 팔레트 관리 설정", "fig_6_1")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>새 팔레트 생성</td><td>새 팔레트를 생성합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>팔레트 삭제</td><td>선택한 팔레트를 삭제합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>설정 복사</td><td>선택한 팔레트 정보를 복사합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>설정 저장</td><td>수정된 팔레트 정보를 저장합니다.</td></tr>
      </tbody>
    </table>
    {fig("그림 6-2 팔레트 상세 설정", "fig_6_2")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>팔레트명</td><td>팔레트 이름을 입력합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>수평 수량</td><td>팔레트의 수평 수량을 입력합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>수직 수량</td><td>팔레트의 수직 수량을 입력합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>수평 간격</td><td>포켓의 수평 크기를 입력합니다.</td></tr>
        <tr><td style="text-align:center;">5</td><td>수직 간격</td><td>포켓의 수직 크기를 입력합니다.</td></tr>
        <tr><td style="text-align:center;">6</td><td>포켓 형태</td><td>포켓의 형태를 설정합니다.</td></tr>
        <tr><td style="text-align:center;">7</td><td>원점 오프셋 X,Y</td><td>첫 번째 포켓의 원점 오프셋을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">8</td><td>원점 오프셋2 X,Y</td><td>마지막 포켓의 원점 오프셋을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">9</td><td>팔레트 두께</td><td>팔레트의 두께를 입력합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">6.2. 팔레트 원점 설정</h2>
    <p>하단의 Pallet Org 버튼을 클릭하여 상부 카메라로 원점을 설정합니다.</p>
    <ol class="steps"><li>첫 번째 포켓의 중심을 카메라 중앙에 맞춥니다.</li><li>마지막 포켓의 중심을 카메라 중앙에 맞춥니다.</li></ol>

    <h2 class="section">6.3. 봉 관리 설정</h2>
    {fig("그림 6-3 봉 관리 설정", "fig_6_3")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>봉 이름</td><td>봉의 이름을 입력합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>봉 두께(직경)</td><td>봉의 두께를 입력합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>Index_Elv 위치</td><td>봉 작업 시 Index_Elv Z축 값을 입력합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>Center_Elv 하한 위치</td><td>Center_Elv의 하부 스페이서 그립 위치를 입력합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">6.4. 스페이서 관리 설정</h2>
    {fig("그림 6-5 스페이서 관리 설정", "fig_6_5")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>스페이서명</td><td>스페이서의 이름을 입력합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>스페이서 길이</td><td>스페이서의 길이를 입력합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>외경</td><td>스페이서의 외경을 입력합니다.</td></tr>
      </tbody>
    </table>
{page_end("6. 팔레트 관리", 25, False)}
''')

# ═══ Chapters 7-11 (combined for brevity) ═══
parts.append(f'''
{page_start("7. 적재 관리", 30, True)}
    <h1 class="chapter">7. 적재 관리</h1>
    <h2 class="section">7.1. 모델 선택 및 LOT 입력</h2>
    {fig("그림 7-1 적재 관리", "fig_7_1")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>모델명</td><td>선택된 모델의 이름을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>모델 선택</td><td>대기 팔레트에 설정할 모델을 선택합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>추가 버튼</td><td>선택한 모델 정보를 로더에 추가합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">7.2. 팔레트 설정</h2>
    {fig("그림 7-3 팔레트 설정", "fig_7_3")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>작업 레이어</td><td>현재 작업 중인 팔레트의 상태를 표시합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>대기 저장</td><td>대기 중인 팔레트의 상태를 표시합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>저장 없음</td><td>팔레트가 없는 상태를 표시합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>팔레트 제거</td><td>대기열의 팔레트를 제거합니다.</td></tr>
        <tr><td style="text-align:center;">5</td><td>수량 설정</td><td>작업 수량을 표시하며, 클릭 시 수량 변경이 가능합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">7.3. 인덱스 봉 설정</h2>
    {fig("그림 7-4 인덱스 설정", "fig_7_4")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>작업 중 (황색)</td><td>작업 중인 봉이 있음을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>작업 완료 (녹색)</td><td>완료된 봉이 있음을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>작업 대기 (주황)</td><td>대기 중인 봉이 있음을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">4-6</td><td>없음 (회색)</td><td>봉이 없는 상태를 표시합니다.</td></tr>
      </tbody>
    </table>
{page_end("7. 적재 관리", 30, True)}

{page_start("8. 환경설정", 33, False)}
    <h1 class="chapter">8. 환경설정</h1>
    <h2 class="section">8.1. 기본 설정</h2>
    {fig("그림 8-1 기본 작업 설정", "fig_8_1")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>기본 작업 속도</td><td>Z축 속도를 제외한 각 위치의 잔여 속도를 지정합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">8.2. 팔레트 동작 설정</h2>
    {fig("그림 8-2 팔레트 동작 설정", "fig_8_2")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>팔레트 작업 속도 (Z)</td><td>팔레트에서 작업 시 Z축 속도를 설정합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>팔레트 동작 속도</td><td>팔레트 축의 속도를 설정합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>인서트 잡기 전 대기 시간</td><td>인서트를 잡기 전 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>인서트 잡은 후 대기 시간</td><td>인서트를 잡은 후 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">5</td><td>인서트 놓기 전 대기 시간</td><td>인서트를 놓기 전 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">6</td><td>인서트 놓은 후 대기 시간</td><td>인서트를 놓은 후 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">7</td><td>팔레트 그리퍼 압력</td><td>팔레트 그리퍼의 공압을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">8</td><td>팔레트 핀 검출 사용</td><td>핀 팔레트 사용 시 On으로 설정하여 적재 전 핀 검출을 수행합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">8.3. 로터리 적재 설정</h2>
    {fig("그림 8-3 로터리 스태커", "fig_8_3")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>봉에서 제품 픽업 전 대기 시간</td><td>봉에서 제품을 픽업하기 전 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>봉에서 제품 픽업 후 대기 시간</td><td>봉에서 제품을 픽업한 후 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>터너 적재 전 대기 시간</td><td>터너에 제품을 적재하기 전 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>터너 적재 후 대기 시간</td><td>터너에 제품을 적재한 후 대기 시간을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">5</td><td>반전 전 그리퍼 압력</td><td>반전 전 그리퍼의 공압을 설정합니다.</td></tr>
        <tr><td style="text-align:center;">6</td><td>반전 후 그리퍼 압력</td><td>반전 후 그리퍼의 공압을 설정합니다.</td></tr>
      </tbody>
    </table>
{page_end("8. 환경설정", 33, False)}

{page_start("9. 작업 위치", 36, True)}
    <h1 class="chapter">9. 작업 위치</h1>
    <h2 class="section">9.1. 티칭 위치 설정</h2>
    <h3 class="subsection">티칭 위치 선택</h3>
    {fig("그림 9-1 티칭 예약", "fig_9_1")}
    <p>자동 운전 중 카메라 또는 작업 위치를 변경해야 할 경우, 위치를 선택하고 티칭을 예약할 수 있습니다.</p>
    <h3 class="subsection">위치 오프셋 설정</h3>
    {fig("그림 9-2 위치 오프셋 설정", "fig_9_2")}
    <p>자동 운전 중 위치를 조정할 때, 아래 화면에서 +/- 값을 조정할 수 있습니다.</p>
{page_end("9. 작업 위치", 36, True)}

{page_start("10. 자동 운전", 38, True)}
    <h1 class="chapter">10. 자동 운전</h1>
    <h2 class="section">10.1. 원점 복귀</h2>
    {fig("그림 10-1 원점 복귀", "fig_10_1")}
    <ol class="steps">
      <li>"복귀 버튼"을 클릭하면 복귀 진행 알림 창이 표시되고, 각 축의 전원이 켜지며 원점 위치로 이동합니다.</li>
      <li>비상 정지 또는 기타 사유로 전원이 차단된 경우 복구하는 방법 중 하나입니다.</li>
    </ol>
    <h2 class="section">10.2. 시작 및 일시정지</h2>
    {fig("그림 10-2 일시정지", "fig_10_2")}
    <p>자동 운전 중 STOP 버튼을 누르거나 도어를 열면 장비가 일시 정지 상태로 전환됩니다. START 버튼을 두 번 클릭하면 작업을 재개할 수 있습니다.</p>
    <h2 class="section">10.3. 정지</h2>
    {fig("그림 10-3 작업 정지", "fig_10_3")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>사이클 정지</td><td>제품 투입을 완료하고 현 위치에서 정지합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>즉시 정지</td><td>현재 위치에서 즉시 정지합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">10.4. 카메라 위치 보정</h2>
    {fig("그림 10-4 위치 보정 실행", "fig_10_4")}
    <p>각 작업 위치에서 각 그리퍼(Jaw, Magnetic)와 상/하부 카메라 간의 위치 보정을 실행합니다.</p>
    <h2 class="section">10.5. 이미지 설정</h2>
    {fig("그림 10-5 이미지 설정", "fig_10_5")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>촬영 이미지</td><td>촬영된 이미지를 표시합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>조명 설정</td><td>조명 값을 0~255로 조절합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>설정/등록</td><td>Acquisition(이미지 획득 및 트래커 생성), Acceptance(검출 점수 허용값), Register(제품 검출 사양 등록), Detect(위치 검출)</td></tr>
        <tr><td style="text-align:center;">4</td><td>트래커 조정</td><td>선택한 트래커의 위치, 각도, 크기를 조정합니다.</td></tr>
        <tr><td style="text-align:center;">5</td><td>검출 결과</td><td>검출 결과 값을 표시합니다.</td></tr>
        <tr><td style="text-align:center;">6</td><td>저장</td><td>설정을 저장합니다.</td></tr>
      </tbody>
    </table>
    <h2 class="section">10.6. 소모품 확인</h2>
    {fig("그림 10-6 소모품 확인", "fig_10_6")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>카테고리 (목록)</td><td>장비에 등록된 소모품 목록</td></tr>
        <tr><td style="text-align:center;">2</td><td>소모품</td><td>선택한 제품의 고유 정보 및 외관 확인</td></tr>
        <tr><td style="text-align:center;">3</td><td>항목</td><td>제품의 교체 정보 및 상태 확인</td></tr>
        <tr><td style="text-align:center;">4</td><td>정보</td><td>소모품 교체 이력 정보 확인</td></tr>
      </tbody>
    </table>
{page_end("10. 자동 운전", 38, True)}

{page_start("11. 작업자 조작 순서", 43, False)}
    <h1 class="chapter">11. 작업자 조작 순서</h1>
    {fig("그림 11-1 작업자 조작 순서 흐름도", "fig_11_1")}
    <p>표시된 부분은 각 파일에 대해 처음에만 수행합니다.</p>
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>팔레트 관리</td><td>팔레트 파일 생성 (팔레트 원점 티칭 필요)</td></tr>
        <tr><td style="text-align:center;">2</td><td>봉 관리</td><td>봉 파일 생성</td></tr>
        <tr><td style="text-align:center;">3</td><td>스페이서 관리</td><td>스페이서 파일 생성 (팔레트 원점 티칭 필요)</td></tr>
        <tr><td style="text-align:center;">4</td><td>모델 파일 생성</td><td>모델명, 제품 높이, 봉, 스페이서, 팔레트, 그리퍼 선택 및 핀 적재 패턴 설정</td></tr>
        <tr><td style="text-align:center;">5</td><td>적재 설정</td><td>모델 선택, + 버튼으로 팔레트 추가</td></tr>
        <tr><td style="text-align:center;">6</td><td>환경설정</td><td>작업 속도, 지연 시간 등 확인</td></tr>
        <tr><td style="text-align:center;">7</td><td>티칭 선택</td><td>티칭 위치 선택</td></tr>
        <tr><td style="text-align:center;">8</td><td>운전 시작</td><td>자동 운전 시작</td></tr>
        <tr><td style="text-align:center;">9</td><td>비전 설정</td><td>비전 파라미터 설정</td></tr>
        <tr><td style="text-align:center;">10</td><td>적재 높이 설정</td><td>적재 높이 조정</td></tr>
      </tbody>
    </table>

    <h2 class="section">11.1. 팔레트 설정</h2>
    <ol class="steps">
      <li>팔레트 기본 파일을 생성합니다.</li>
      <li>왼쪽 목록에서 새로 생성한 이름을 선택합니다.</li>
      <li>팔레트 정보를 입력합니다: 팔레트명, 적재 공간 수량(수평/수직)</li>
      <li>팔레트 원점 티칭(시작점/끝점): 십자선의 중심을 포켓 중심에 맞춥니다.</li>
    </ol>
    {fig("그림 11-2 팔레트 관리", "fig_11_2")}

    <h2 class="section">11.2. 봉 설정</h2>
    <ol class="steps">
      <li>봉 기본 파일을 생성합니다.</li>
      <li>왼쪽 목록에서 이름을 선택하고 봉 정보를 입력합니다.</li>
      <li>봉 이름, 적재 유효 길이, 두께(직경), 인덱스 높이, CENTER_ELV 언로딩 시작 위치를 입력합니다.</li>
      <li>파일을 저장합니다.</li>
    </ol>

    <h2 class="section">11.3. 스페이서 설정</h2>
    <ol class="steps">
      <li>스페이서 기본 파일을 생성합니다.</li>
      <li>스페이서 이름, 길이, 내경, 외경, 픽업 높이(G2Z축)를 입력합니다.</li>
      <li>파일을 저장합니다.</li>
    </ol>

    <h2 class="section">11.4. 모델 파일 생성</h2>
    <ol class="steps">
      <li>모델명, 부품 형태, 높이, 길이, 팔레트, 봉, 스페이서, 작업 유형 등을 선택합니다.</li>
      <li>1단계에서 팔레트를 이미 생성해야 선택할 수 있습니다.</li>
      <li>핀 적재 패턴 설정을 완료하고 저장합니다.</li>
    </ol>
    {fig("그림 11-5 모델 파일 생성", "fig_11_5")}

    <h2 class="section">11.5. 적재 설정</h2>
    <ol class="steps">
      <li>모델을 선택합니다.</li>
      <li>+ 버튼으로 팔레트를 하나 추가합니다.</li>
      <li>큰 원 안의 작은 숫자 원을 클릭하여 작업 인덱스를 설정합니다.</li>
    </ol>
    {fig("그림 11-6 적재 설정", "fig_11_6")}

    <h2 class="section">11.6. 환경설정</h2>
    <p>파라미터를 조정합니다.</p>
    {fig("그림 11-7 환경설정", "fig_11_7")}

    <h2 class="section">11.7. 티칭 선택</h2>
    {fig("그림 11-8 티칭 선택", "fig_11_8")}

    <h2 class="section">11.8. 운전 시작</h2>
    {fig("그림 11-9 운전 시작", "fig_11_9")}
    <p>TP 조작 화면 (티칭 시):</p>
    <ol class="steps">
      <li>축 선택 버튼</li>
      <li>상/하/좌/우 버튼</li>
      <li>빠른 동작 버튼 (좌→우: 빈 에어 블로우 / 반전 전기 그리퍼 / 팔레트 픽업 그리퍼 / 제품 그리퍼 / 스페이서 그리퍼)</li>
      <li>Move / Jog 선택</li>
      <li>Move 시 1회 이동 거리</li>
      <li>수동 조작 시 이동 속도</li>
      <li>저장/취소 버튼</li>
    </ol>

    <h2 class="section">11.9. 비전 설정</h2>
    {fig("그림 11-10 비전 설정", "fig_11_10")}
    <table class="manual-table">
      <thead><tr><th>No.</th><th>명칭</th><th>설명</th></tr></thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>밝기 설정</td><td>검출용 이미지의 밝기를 설정합니다.</td></tr>
        <tr><td style="text-align:center;">2</td><td>형태 설정</td><td>인서트의 형태를 선택하고 크기를 조정합니다.</td></tr>
        <tr><td style="text-align:center;">3</td><td>등록</td><td>형태 설정이 완료된 이미지를 등록합니다.</td></tr>
        <tr><td style="text-align:center;">4</td><td>검출</td><td>검출 결과를 확인합니다.</td></tr>
      </tbody>
    </table>
    <h3 class="subsection">조명 설정</h3>
    <p>캡처 버튼을 클릭하여 이미지를 표시하고, 제품 검출에 최적인 조건으로 밝기를 조정합니다 (최대 255).</p>
    <h3 class="subsection">형태 설정</h3>
    <ol class="steps">
      <li>인서트의 형태 타입을 설정합니다.</li>
      <li>형태 타입을 선택합니다.</li>
      <li>빨간선을 인서트 외곽에, 파란선을 내부 구멍에 맞춥니다.</li>
    </ol>
    <h3 class="subsection">등록</h3>
    <p>'Register' 버튼을 클릭하여 검출용 기준 이미지를 등록합니다. 등록된 이미지를 확인하고 보정 통과 점수를 설정합니다.</p>
    <h3 class="subsection">검출</h3>
    <p>'Detect' 버튼을 클릭하여 인서트가 올바르게 검출되는지 확인합니다. 검출 결과는 점수로 표시됩니다.</p>
    <h3 class="subsection">마스킹</h3>
    <p>인서트의 칩 브레이커가 복잡한 형상으로 인해 검출 오류가 발생할 수 있는 경우, 특정 영역을 마스킹하여 검출 안정성을 확보합니다.</p>
{page_end("11. 작업자 조작 순서", 43, False)}
''')

# ═══ Chapter 12: 에러 알람 ═══
parts.append(f'''
{page_start("12. 에러 알람", 55, False)}
    <h1 class="chapter">12. 에러 알람</h1>
    <h2 class="section">12.1. 에러 리스트</h2>
    <p>에러 발생 시 HMI 화면에 3자리 에러 코드 번호가 표시되고 부저가 울립니다.</p>
    <p>아래 표는 발생 가능한 에러 코드, 원인 및 대처 방법입니다.</p>

    <table class="manual-table error-table">
      <thead><tr><th style="width:60px;">코드</th><th>내용</th><th>원인</th><th>대처 방법</th></tr></thead>
      <tbody>
        <tr><td>001</td><td>프로그램 이미 실행 중</td><td>프로그램 중복 실행 시</td><td>기존 프로그램 종료 후 재실행</td></tr>
        <tr><td>002</td><td>운영 이력 DB 파일 없음</td><td>DB 파일 누락 시</td><td>WTA에 문의</td></tr>
        <tr><td>013</td><td>메인 에어 공급 없음</td><td>공압 미공급</td><td>공압 라인 확인</td></tr>
        <tr><td>027</td><td>정보 손상</td><td>데이터 파일 손상 시</td><td>WTA에 문의</td></tr>
        <tr><td>028</td><td>정보 없음</td><td>데이터 파일 손상 시</td><td>WTA에 문의</td></tr>
        <tr><td>128</td><td>컨트롤러 미연결</td><td>컨트롤러 통신 불가 시</td><td>연결 상태 확인</td></tr>
        <tr><td>132</td><td>I/O 설정 미완료</td><td>I/O 설정 누락 시</td><td>I/O 설정 완료</td></tr>
        <tr><td>133</td><td>시스템 정보 오류</td><td>시스템 정보 이상 시</td><td>WTA에 문의</td></tr>
        <tr><td>134</td><td>시스템 정보 읽기 실패</td><td>시스템 파일 손상 시</td><td>WTA에 문의</td></tr>
        <tr><td>135</td><td>해당 축 이미 이동 중</td><td>축 중복 동작 시</td><td>동작 완료 후 재시도</td></tr>
        <tr><td>145</td><td>메인 도어 열림</td><td>안전 도어 미닫힘</td><td>도어 닫기 후 재시도</td></tr>
        <tr><td>165</td><td>절대값 데이터 읽기 실패</td><td>엔코더 배터리 소진</td><td>배터리 교체 후 원점 재설정</td></tr>
      </tbody>
    </table>

    <p style="font-weight:700; margin-top:20px;">팔레트 피더 관련 에러</p>
    <table class="manual-table error-table">
      <thead><tr><th style="width:60px;">코드</th><th>내용</th><th>원인</th><th>대처 방법</th></tr></thead>
      <tbody>
        <tr><td>2000</td><td>팔레트 공급 실패</td><td>해당 층에 팔레트 없음 등</td><td>엘리베이터 팔레트 확인</td></tr>
        <tr><td>2001</td><td>팔레트 잠금 실패</td><td>피더 팔레트 클램핑 불가</td><td>클램핑 실린더 확인</td></tr>
        <tr><td>2002</td><td>팔레트 잠금 해제 실패</td><td>피더 팔레트 언클램핑 불가</td><td>클램핑 실린더 확인</td></tr>
        <tr><td>2003</td><td>팔레트 상승 실패</td><td>피더 상하 실린더 동작 불가</td><td>실린더 동작 및 팔레트 적재 확인</td></tr>
        <tr><td>2004</td><td>팔레트 하강 실패</td><td>피더 상하 실린더 동작 불가</td><td>실린더 동작 확인</td></tr>
        <tr><td>2005</td><td>팔레트 투입 실린더 위치 감지 실패</td><td>실린더 이동 후 센서 미감지</td><td>실린더 동작, 팔레트 걸림 확인</td></tr>
        <tr><td>2006</td><td>팔레트 배출 실린더 위치 감지 실패</td><td>실린더 이동 후 센서 미감지</td><td>실린더 동작, 팔레트 걸림 확인</td></tr>
        <tr><td>2007</td><td>팔레트 적재 실린더 하강 실패</td><td>배출 적재 실린더 하강 후 센서 미감지</td><td>실린더 동작 확인</td></tr>
        <tr><td>2008</td><td>공급 팔레트 저장 잠금 실패</td><td>Push/Pull 실린더 Push 후 센서 미감지</td><td>실린더 동작, 걸림 확인</td></tr>
        <tr><td>2009</td><td>공급 팔레트 저장 잠금 해제 실패</td><td>Pull 후 센서 미감지</td><td>실린더 동작 확인</td></tr>
        <tr><td>2010</td><td>팔레트 투입 실패</td><td>피더 팔레트 투입 후 미감지</td><td>팔레트 감지 센서 확인</td></tr>
        <tr><td>2011</td><td>팔레트 배출 실패</td><td>피더 팔레트 배출 후 감지됨</td><td>팔레트 감지 센서 확인</td></tr>
        <tr><td>2012</td><td>공급 팔레트 이미 존재</td><td>투입 시 피더에 팔레트 존재</td><td>수동으로 팔레트 제거 후 재실행</td></tr>
        <tr><td>2013</td><td>공급 저장소에 팔레트 없음</td><td>저장소에 팔레트 미존재</td><td>저장소에 팔레트 공급</td></tr>
        <tr><td>2014</td><td>배출 팔레트 저장소 만석</td><td>배출 저장소 가득 참</td><td>팔레트 제거</td></tr>
      </tbody>
    </table>

    <p style="font-weight:700; margin-top:20px;">장비 동작 관련 에러</p>
    <table class="manual-table error-table">
      <thead><tr><th style="width:60px;">코드</th><th>내용</th><th>원인</th><th>대처 방법</th></tr></thead>
      <tbody>
        <tr><td>1000</td><td>[엘리베이터] 제품 픽업 실패</td><td>피딩 위치 픽업 실패</td><td>픽업 상태 확인</td></tr>
        <tr><td>1001</td><td>[인덱스] 봉 피더/배출기 동작 실패</td><td>실린더 동작 불가</td><td>실린더 및 센서 확인</td></tr>
        <tr><td>1002</td><td>[인덱스] 봉 투입 그리퍼 구동 실패</td><td>투입 위치 그립 동작 실패</td><td>그리퍼 실린더 센서 및 핀치 라이트 확인</td></tr>
        <tr><td>1003</td><td>[스페이서] 투입 실린더 동작 실패</td><td>실린더 동작 불가</td><td>실린더 센서 확인</td></tr>
        <tr><td>1004</td><td>[스페이서] 공급 실패</td><td>스페이서 공급 실패</td><td>피더 동작 및 걸림 확인</td></tr>
        <tr><td>1005</td><td>[반전] 가이드 구동 실패</td><td>반전 전기 가이드 전후 동작 실패</td><td>실린더 센서 확인</td></tr>
        <tr><td>1007</td><td>[반전 전기] 제품 픽업 실패</td><td>반전 전기 위치에서 픽업 실패</td><td>제품 누락 또는 지연 확인</td></tr>
        <tr><td>1008</td><td>[봉] 제품 적재 실패</td><td>봉 적재 실패</td><td>제품 감지 센서 및 픽업 상태 확인</td></tr>
        <tr><td>1009</td><td>[인덱스] 사이드 라이트 승하강 실패</td><td>실린더 승하강 동작 실패</td><td>실린더 센서 및 핀치 라이트 확인</td></tr>
        <tr><td>1010</td><td>[인덱스] 인덱스 잠금 감지 실패</td><td>잠금 실린더 동작 실패</td><td>실린더 센서 확인</td></tr>
        <tr><td>1011</td><td>[인덱스] 인덱스 잠금 해제 감지 실패</td><td>잠금 실린더 동작 실패</td><td>실린더 센서 확인</td></tr>
        <tr><td>1013</td><td>[인덱스] 하부 그립 감지 실패</td><td>하부 그리퍼 동작 실패</td><td>그리퍼 센서 확인</td></tr>
        <tr><td>1014</td><td>[인덱스] 하부 언그립 감지 실패</td><td>하부 그리퍼 동작 실패</td><td>센서 및 핀치 라이트 확인</td></tr>
        <tr><td>1015</td><td>[인덱스] 하부 그리퍼 UP 센서 감지 실패</td><td>하부 그리퍼 실린더 동작 실패</td><td>센서 확인</td></tr>
        <tr><td>1016</td><td>[인덱스] 하부 그리퍼 DOWN 센서 감지 실패</td><td>하부 그리퍼 실린더 동작 실패</td><td>센서 및 핀치 라이트 확인</td></tr>
      </tbody>
    </table>
{page_end("12. 에러 알람", 55, False)}
''')

# ═══ Chapter 13: 유지보수 ═══
parts.append(f'''
{page_start("13. 유지보수", 62, True)}
    <h1 class="chapter">13. 유지보수</h1>
    <h2 class="section">13.1. 정기 점검</h2>
    <p>본 절에서는 장비를 구성하는 경량 소재의 장기간 무고장 사용을 보장하기 위한 유지보수 점검에 대해 설명합니다.</p>
    <h3 class="subsection">상시/정기 점검 체크리스트</h3>
    <p>유지보수 점검에는 상시 점검과 정기 점검의 두 가지 유형이 있습니다.</p>
    <table class="manual-table maint-table">
      <thead><tr><th>구분</th><th>점검 항목</th><th>점검 기준</th><th>상시</th><th>월간</th><th>연간</th></tr></thead>
      <tbody>
        <tr><td>본체</td><td>외관</td><td>절단, 파손, 변형 없음</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>본체</td><td>이상 소음</td><td>기계적 이상 또는 소음 없음</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>본체</td><td>공압 저하</td><td>레귤레이터 점검 및 청소</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>각축 로봇</td><td>진동 발생 시</td><td>볼트 풀림 또는 마모 부품 확인</td><td></td><td style="text-align:center;">V</td><td></td></tr>
        <tr><td>각축 로봇</td><td>케이블베이어 확인</td><td>처짐 또는 부하 없는지 확인</td><td></td><td></td><td style="text-align:center;">V</td></tr>
        <tr><td>각축 로봇</td><td>과주행 시</td><td>벨트 장력 조정 및 교체</td><td></td><td></td><td style="text-align:center;">V</td></tr>
        <tr><td>픽업</td><td>Jaw 유닛 압력 확인</td><td>제품 손상 시 소형 레귤레이터 압력 조정</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>픽업</td><td>Jaw/Vacuum 이중 배관 확인</td><td>오염 시 배관 교체</td><td></td><td style="text-align:center;">V</td><td></td></tr>
        <tr><td>픽업</td><td>그리퍼 회전 이상 시</td><td>벨트 장력 조정 및 교체</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>팔레트 리프트</td><td>리프트 승/하강 이상 시</td><td>벨트 장력 조정 및 교체</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>팔레트 피더</td><td>벨트 기울기 발생 시</td><td>양쪽 텐션 볼트로 장력 조정</td><td></td><td></td><td style="text-align:center;">V</td></tr>
        <tr><td>캠 및 P.P</td><td>Jaw 유닛 압력 확인</td><td>제품 손상 시 소형 레귤레이터 압력 조정</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>반전</td><td>그립 이상 시</td><td>그리퍼 마모 확인</td><td style="text-align:center;">V</td><td></td><td></td></tr>
        <tr><td>인덱스 유닛</td><td>테이블 승/하강 이상 시</td><td>벨트 장력 조정 및 교체</td><td></td><td></td><td style="text-align:center;">V</td></tr>
        <tr><td>전기</td><td>앱솔루트 배터리 저전압</td><td>3년 주기 교체, 서보 드라이브 고장 시</td><td></td><td></td><td style="text-align:center;">V</td></tr>
      </tbody>
    </table>

    <h2 class="section">13.2. 자주 발생하는 문제</h2>
    <table class="manual-table">
      <thead><tr><th>유닛</th><th>문제</th><th>빈도</th><th>중요도</th></tr></thead>
      <tbody>
        <tr><td>반전 유닛</td><td>반전 전 위치에서 제품 픽업 실패</td><td>조건에 따라 (낮음)</td><td style="text-align:center; font-weight:600; color:var(--wta-red);">높음</td></tr>
        <tr><td>팔레트/피더</td><td>제품 적재 방향 및 위치 불일치</td><td>조건에 따라 (낮음)</td><td style="text-align:center;">중간</td></tr>
      </tbody>
    </table>
    <h3 class="subsection">3 Jaw 그리퍼 제품 그립 상태 확인</h3>
    <ol class="steps">
      <li>그리퍼가 제품을 올바르게 픽업했는지 확인합니다.</li>
      <li>3 Jaw 그리퍼 핀의 조립 상태를 확인합니다.</li>
    </ol>
    <p><strong>해결 방법:</strong></p>
    <ol class="steps">
      <li>모델 설정에서 제품 높이 설정이 올바른지 확인합니다.</li>
      <li>그리퍼 핀의 조립 높이가 일관되게 조정합니다.</li>
    </ol>
    <h3 class="subsection">팔레트 적재 티칭 상태 확인</h3>
    <ol class="steps">
      <li>제품의 적재 방향과 적용된 오프셋 값을 확인합니다.</li>
    </ol>
    <p><strong>해결 방법:</strong></p>
    <ol class="steps">
      <li>팔레트 적재 위치를 재티칭합니다.</li>
      <li>조정 값이 작은 경우 오프셋 기능을 사용하여 조정합니다.</li>
    </ol>

    <h2 class="section">13.3. 소모품 리스트 (Wear Parts)</h2>
    <table class="manual-table parts-table">
      <thead><tr><th>유닛</th><th>주문번호</th><th>품명</th><th>규격</th><th>제조사</th><th>수량</th></tr></thead>
      <tbody>
        <tr><td>Grip Tool</td><td>P05001040</td><td>3Jaw Grip Pin (Ø1.0) (3개 세트)</td><td>Ø1.0, 19mm</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Grip Tool</td><td>P05001050</td><td>3Jaw Grip Pin Holder (Ø1.0) (3개 세트)</td><td>Ø1.0</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Grip Tool</td><td>P05001060</td><td>3Jaw Grip Pin (Ø0.8) (3개 세트)</td><td>Ø0.8, 19mm</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Grip Tool</td><td>P05001070</td><td>3Jaw Grip Pin Holder (Ø0.8) (3개 세트)</td><td>Ø0.8</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Grip Tool</td><td>P05001500</td><td>3Jaw Reflective plate</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Grip Tool</td><td>A05013010</td><td>Magnet Tool Pin 1.5</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Grip Tool</td><td>P05003391</td><td>P2Jaw Grip Cap</td><td>Cap For Un-0.6mm/0.8mm Pin</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Grip Tool</td><td>P05003501</td><td>P2Jaw Grip Pin Un-0.8mm (2개 세트)</td><td>L19.5/W0.8/PinL5.5</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Grip Tool</td><td>B100000</td><td>P2Jaw Gripper spring set</td><td>Spring 1, Fix Pin 2, Bolt 2</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Reversal</td><td>P05410360</td><td>Grip Turn Plate</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Reversal</td><td>P05410230</td><td>Centering Pin Plate</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Reversal</td><td>P05410240</td><td>Grip Turn Pin</td><td>-</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Skewer Elv</td><td>P02300680</td><td>Spacer Gripper Center (2개 세트)</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Skewer Elv</td><td>P02300700</td><td>Spacer Gripper Left,Right (2개 세트)</td><td>-</td><td>WTA</td><td style="text-align:center;">2</td></tr>
      </tbody>
    </table>

    <p style="font-weight:700; margin-top:16px;">부속품 (Accessories)</p>
    <table class="manual-table parts-table">
      <thead><tr><th>유닛</th><th>주문번호</th><th>품명</th><th>규격</th><th>제조사</th><th>수량</th></tr></thead>
      <tbody>
        <tr><td>Grip Tool</td><td>A05013000</td><td>Magnet Tool</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Grip Tool</td><td>A05003002</td><td>P2Jaw Grip Tool Cylinder</td><td>핀 제외</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Grip Tool</td><td>A05001000</td><td>3Jaw Grip Tool Cylinder</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Skewer Unloading Elv</td><td>P023061030</td><td>Skewer Elevator Gripper Holder</td><td>-</td><td>WTA</td><td style="text-align:center;">2</td></tr>
        <tr><td>Skewer Index</td><td>P02501970</td><td>Skewer Index Gripper Brkt</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Skewer Index</td><td>P02501980</td><td>Skewer Index Gripper (2개 세트)</td><td>-</td><td>WTA</td><td style="text-align:center;">1</td></tr>
        <tr><td>Control</td><td>B006577</td><td>Encoder Battery</td><td>-</td><td>Maxell</td><td style="text-align:center;">-</td></tr>
        <tr><td>Control</td><td>B006580</td><td>UPS Battery</td><td>-</td><td>APC</td><td style="text-align:center;">1</td></tr>
        <tr><td>Control</td><td>B006578</td><td>Relay</td><td>-</td><td>IOLINK</td><td style="text-align:center;">-</td></tr>
      </tbody>
    </table>
{page_end("13. 유지보수", 62, True)}
''')

# ═══ Appendix ═══
parts.append(f'''
{page_start("부록 A", 91, False)}
    <h1 class="chapter">부록 A. 도면</h1>
    <h2 class="section">A.1. 전기 회로도</h2>
    {fig("전기 회로도 — 별도 첨부")}
    <h2 class="section">A.2. 공압 도면</h2>
    {fig("공압 도면 — 별도 첨부")}
    <h2 class="section">A.3. 상세 매뉴얼</h2>
    {fig("상세 매뉴얼 — 별도 첨부")}
{page_end("부록 A", 91, False)}
''')

# ═══ Back Cover ═══
parts.append(f'''
<div class="page">
  <div class="back-cover">
    <img src="{img["wta_back_logo"]}" alt="WTA">
  </div>
</div>

</body>
</html>''')

html = "\n".join(parts)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Written: {os.path.basename(OUT_PATH)} ({len(html):,} bytes)")
