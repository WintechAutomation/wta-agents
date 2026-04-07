"""Generate manual-template.html with embedded base64 images."""
import json
import os

IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "templates", "images")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "templates", "manual-template.html")

with open(os.path.join(IMG_DIR, "base64-data.json"), "r") as f:
    img = json.load(f)

html = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{manual_title}} — (주)윈텍오토메이션</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;900&display=swap');

  :root {
    --wta-red: #C0392B;
    --wta-red-dark: #A93226;
    --wta-red-light: #E74C3C;
    --wta-gray: #7F8C8D;
    --text-primary: #0d0d0d;
    --text-secondary: #333;
    --text-light: #666;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  @page {
    size: A4;
    margin: 0;
  }

  body {
    font-family: '맑은 고딕', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
    font-size: 9.5pt;
    color: var(--text-primary);
    line-height: 1.6;
    background: #e8e8e8;
  }

  .page {
    width: 210mm;
    min-height: 297mm;
    margin: 8mm auto;
    background: #fff;
    box-shadow: 0 1px 6px rgba(0,0,0,0.15);
    position: relative;
    overflow: hidden;
    page-break-after: always;
  }
  .page:last-child { page-break-after: auto; }

  .page-body {
    padding: 0 18mm 25mm 18mm;
  }

  @media print {
    body { background: #fff; }
    .page { margin: 0; box-shadow: none; width: 100%; min-height: auto; }
  }

  /* ── Header bar (real images) ── */
  .page-header {
    width: 100%;
    margin-bottom: 8px;
  }
  .page-header img {
    width: 100%;
    height: auto;
    display: block;
  }

  .page-section-label {
    text-align: right;
    font-size: 8.5pt;
    color: var(--text-light);
    font-style: italic;
    padding: 0 18mm 4px 0;
    margin-bottom: 8px;
  }

  /* ── Footer ── */
  .page-footer {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    padding: 6px 18mm 10mm;
  }
  .page-footer-even { flex-direction: row; }
  .page-footer-odd { flex-direction: row-reverse; }
  .page-footer .footer-logo { height: 28px; }
  .page-footer .footer-slogan {
    font-size: 8pt;
    color: var(--text-light);
    font-style: italic;
    margin: 0 12px;
    flex: 1;
  }
  .page-footer-even .footer-slogan { text-align: left; }
  .page-footer-odd .footer-slogan { text-align: right; }
  .page-footer .page-num {
    font-size: 9pt;
    font-weight: 600;
    color: var(--text-secondary);
  }

  /* ══ Cover Page ══ */
  .cover-page {
    position: relative;
    width: 210mm;
    min-height: 297mm;
  }
  .cover-stripe {
    position: absolute;
    top: 0; right: 0;
    width: 22mm; height: 100%;
    min-height: 297mm;
  }
  .cover-stripe-main {
    position: absolute;
    top: 0; right: 0;
    width: 14mm; height: 85%;
    background: var(--wta-red);
  }
  .cover-stripe-accent1 {
    position: absolute;
    top: 0; right: 16mm;
    width: 3mm; height: 12%;
    background: var(--wta-red);
    transform: skewY(-2deg);
  }
  .cover-stripe-accent2 {
    position: absolute;
    top: 4%; right: 16mm;
    width: 3mm; height: 10%;
    background: var(--wta-red);
    transform: skewY(-2deg);
  }
  .cover-stripe-gradient {
    position: absolute;
    bottom: 0; right: 0;
    width: 14mm; height: 15%;
    background: linear-gradient(180deg, var(--wta-red) 0%, #E67E73 60%, var(--wta-gray) 100%);
  }
  .cover-logo {
    position: absolute;
    top: 28mm; left: 25mm;
  }
  .cover-logo img { height: 48px; }
  .cover-content {
    position: absolute;
    top: 38%;
    left: 25mm; right: 35mm;
  }
  .cover-title {
    font-size: 20pt;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.4;
    margin-bottom: 20px;
  }
  .cover-meta {
    font-size: 10pt;
    color: var(--text-light);
    line-height: 2;
    margin-top: 30px;
  }
  .cover-meta-label {
    display: inline-block;
    width: 80px;
    font-weight: 600;
    color: var(--text-secondary);
  }
  .cover-bottom {
    position: absolute;
    bottom: 25mm; left: 25mm;
  }
  .cover-company {
    font-size: 10pt;
    font-weight: 700;
    color: var(--text-secondary);
  }
  .cover-company-en {
    font-size: 8pt;
    color: #999;
  }

  /* ══ Back Cover ══ */
  .back-cover {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 260mm;
    padding: 40mm;
  }
  .back-cover img { width: 120px; }

  /* ══ TOC ══ */
  .toc-title {
    font-size: 22pt;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 20px;
  }
  .toc-list { list-style: none; }
  .toc-chapter {
    font-size: 12pt;
    font-weight: 700;
    color: var(--text-primary);
    padding: 8px 0 4px;
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #eee;
  }
  .toc-section {
    font-size: 9.5pt;
    font-weight: 400;
    color: var(--text-secondary);
    padding: 3px 0 3px 16px;
    display: flex;
    justify-content: space-between;
  }
  .toc-subsection {
    font-size: 9pt;
    font-weight: 400;
    color: var(--text-light);
    padding: 2px 0 2px 32px;
    display: flex;
    justify-content: space-between;
  }
  .toc-subsection .toc-marker {
    color: var(--wta-red);
    margin-right: 6px;
    font-size: 8pt;
  }
  .toc-page { color: var(--text-light); flex-shrink: 0; margin-left: 8px; }
  .toc-dots { flex: 1; border-bottom: 1px dotted #ccc; margin: 0 8px; align-self: flex-end; margin-bottom: 3px; }

  /* ══ Body Styles ══ */
  h1.chapter {
    font-size: 18pt;
    font-weight: 700;
    color: var(--text-primary);
    padding-bottom: 8px;
    border-bottom: 3px solid var(--wta-red);
    margin-bottom: 16px;
    page-break-after: avoid;
  }
  h2.section {
    font-size: 12pt;
    font-weight: 700;
    color: var(--text-primary);
    margin: 20px 0 10px;
    padding-bottom: 4px;
    border-bottom: 1px solid #ddd;
    page-break-after: avoid;
  }
  h3.subsection {
    font-size: 10pt;
    font-weight: 700;
    color: var(--text-primary);
    margin: 14px 0 6px;
    padding-left: 12px;
    border-left: 4px solid #333;
    page-break-after: avoid;
  }
  p {
    font-size: 9.5pt;
    color: var(--text-primary);
    line-height: 1.7;
    margin-bottom: 8px;
    text-align: justify;
  }

  /* Notice boxes with real icons */
  .notice {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: #FFF3CD;
    border: 2px solid #F0AD4E;
    padding: 10px 14px;
    margin: 12px 0;
    font-size: 9pt;
  }
  .notice-icon {
    width: 40px;
    height: 36px;
    flex-shrink: 0;
    object-fit: contain;
  }
  .notice-content { flex: 1; }
  .notice-title { font-weight: 700; margin-bottom: 4px; }

  .notice.danger {
    background: #FDEDEE;
    border-color: var(--wta-red);
  }
  .notice.danger .notice-title { color: var(--wta-red-dark); }

  .notice.caution {
    background: #FFF8E1;
    border-color: #FFC107;
  }

  .notice.info {
    background: #EBF5FB;
    border-color: #2E86C1;
  }
  .notice.info .notice-title { color: #1B4F72; }

  /* Tables */
  table.manual-table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 9pt;
  }
  table.manual-table th {
    background: #F2F2F2;
    color: var(--text-primary);
    font-weight: 600;
    padding: 6px 10px;
    text-align: center;
    border: 1px solid #bbb;
  }
  table.manual-table td {
    padding: 5px 10px;
    border: 1px solid #ddd;
    vertical-align: middle;
  }
  table.manual-table tr:nth-child(even) { background: #fafafa; }

  /* Figures */
  .figure {
    text-align: center;
    margin: 16px 0;
    page-break-inside: avoid;
  }
  .figure img { max-width: 100%; max-height: 180mm; border: 1px solid #e0e0e0; }
  .figure-caption {
    font-size: 8.5pt;
    color: var(--text-secondary);
    margin-top: 6px;
    font-weight: 700;
    text-align: center;
  }
  .figure-placeholder {
    width: 100%; height: 120px; background: #f5f5f5; border: 1px solid #ddd;
    display: flex; align-items: center; justify-content: center; color: #999;
  }

  /* Lists */
  ol.steps { margin: 8px 0 8px 24px; font-size: 9.5pt; }
  ol.steps li { margin-bottom: 6px; line-height: 1.6; }
  ul.items { margin: 8px 0 8px 20px; font-size: 9.5pt; list-style: disc; }
  ul.items li { margin-bottom: 4px; line-height: 1.6; }

  table.error-table td:first-child { font-weight: 600; text-align: center; color: var(--wta-red); }
</style>
</head>
<body>

<!-- PAGE 1: Cover -->
<div class="page cover-page">
  <div class="cover-stripe">
    <div class="cover-stripe-accent1"></div>
    <div class="cover-stripe-accent2"></div>
    <div class="cover-stripe-main"></div>
    <div class="cover-stripe-gradient"></div>
  </div>
  <div class="cover-logo">
    <img src="IMG_WTA_LOGO" alt="WTA">
  </div>
  <div class="cover-content">
    <div class="cover-title">{{manual_title}}</div>
    <div class="cover-meta">
      <div><span class="cover-meta-label">Doc No.</span>{{doc_number}}</div>
      <div><span class="cover-meta-label">Version</span>{{doc_version}}</div>
      <div><span class="cover-meta-label">Date</span>{{doc_date}}</div>
      <div><span class="cover-meta-label">Author</span>{{doc_author}}</div>
      <div><span class="cover-meta-label">Customer</span>{{customer_name}}</div>
    </div>
  </div>
  <div class="cover-bottom">
    <div class="cover-company">(주)윈텍오토메이션</div>
    <div class="cover-company-en">WINTEC AUTOMATION Co., Ltd.</div>
  </div>
</div>

<!-- PAGE 2: Revision History -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_EVEN" alt="header"></div>
  <div class="page-section-label">Revision History</div>
  <div class="page-body">
    <h1 class="chapter">개정 이력</h1>
    <table class="manual-table">
      <thead>
        <tr>
          <th style="width:60px;">버전</th>
          <th style="width:100px;">날짜</th>
          <th>변경 내용</th>
          <th style="width:80px;">작성자</th>
        </tr>
      </thead>
      <tbody>
        <!-- {% for rev in revisions %} -->
        <tr>
          <td style="text-align:center;">{{rev_version}}</td>
          <td style="text-align:center;">{{rev_date}}</td>
          <td>{{rev_description}}</td>
          <td style="text-align:center;">{{rev_author}}</td>
        </tr>
        <!-- {% endfor %} -->
      </tbody>
    </table>
  </div>
  <div class="page-footer page-footer-even">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">ii</span>
  </div>
</div>

<!-- PAGE 3: Table of Contents -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_ODD" alt="header"></div>
  <div class="page-section-label">Table of Contents</div>
  <div class="page-body">
    <h1 class="toc-title">Table of Contents</h1>
    <ul class="toc-list">
      <li class="toc-chapter"><span>1. 개요</span><span class="toc-dots"></span><span class="toc-page">4</span></li>
      <li class="toc-section"><span>1.1. 사용 설명서</span><span class="toc-dots"></span><span class="toc-page">4</span></li>
      <li class="toc-subsection"><span><span class="toc-marker">▌</span>참고 사항</span><span class="toc-dots"></span><span class="toc-page">4</span></li>
      <li class="toc-subsection"><span><span class="toc-marker">▌</span>장비 표시</span><span class="toc-dots"></span><span class="toc-page">4</span></li>
      <li class="toc-section"><span>1.2. 장비 사용 안내</span><span class="toc-dots"></span><span class="toc-page">5</span></li>
      <li class="toc-subsection"><span><span class="toc-marker">▌</span>운영 담당자 안내</span><span class="toc-dots"></span><span class="toc-page">5</span></li>
      <li class="toc-section"><span>1.3. 장비 외관</span><span class="toc-dots"></span><span class="toc-page">6</span></li>
      <li class="toc-chapter"><span>2. 안전 유의 사항</span><span class="toc-dots"></span><span class="toc-page">9</span></li>
      <li class="toc-chapter"><span>3. 시운전</span><span class="toc-dots"></span><span class="toc-page">15</span></li>
      <li class="toc-chapter"><span>4. 메인 화면</span><span class="toc-dots"></span><span class="toc-page">19</span></li>
      <li class="toc-chapter"><span>5. 메인 메뉴 기능 (장비 조작)</span><span class="toc-dots"></span><span class="toc-page">21</span></li>
      <li class="toc-chapter"><span>6. 자재 관리</span><span class="toc-dots"></span><span class="toc-page">24</span></li>
      <li class="toc-chapter"><span>7. 적재 관리</span><span class="toc-dots"></span><span class="toc-page">29</span></li>
      <li class="toc-chapter"><span>8. 환경설정</span><span class="toc-dots"></span><span class="toc-page">32</span></li>
      <li class="toc-chapter"><span>9. 작업 위치</span><span class="toc-dots"></span><span class="toc-page">34</span></li>
      <li class="toc-chapter"><span>10. 자동 운전</span><span class="toc-dots"></span><span class="toc-page">35</span></li>
      <li class="toc-chapter"><span>11. 작업자 조작 순서</span><span class="toc-dots"></span><span class="toc-page">38</span></li>
      <li class="toc-chapter"><span>12. 에러 알람</span><span class="toc-dots"></span><span class="toc-page">53</span></li>
      <li class="toc-chapter"><span>13. 유지보수</span><span class="toc-dots"></span><span class="toc-page">60</span></li>
    </ul>
  </div>
  <div class="page-footer page-footer-odd">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">1</span>
  </div>
</div>

<!-- PAGE 4: 1. Overview -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_EVEN" alt="header"></div>
  <div class="page-section-label">1. Overview</div>
  <div class="page-body">
    <h1 class="chapter">1. 개요</h1>

    <h2 class="section">1.1. 사용 설명서</h2>
    <p>본 사용 설명서는 장비의 올바른 사용 방법과 유지보수 절차를 안내합니다. 장비를 조작하기 전에 반드시 본 설명서를 숙지하시기 바랍니다.</p>

    <h3 class="subsection">참고 사항</h3>
    <div class="notice info">
      <img class="notice-icon" src="IMG_ICON_NOTE" alt="참고">
      <div class="notice-content">
        <div class="notice-title">참고</div>
        본 설명서의 내용은 장비 사양 변경 시 사전 통보 없이 변경될 수 있습니다.
      </div>
    </div>

    <h3 class="subsection">장비 표시</h3>
    <table class="manual-table">
      <thead>
        <tr><th>표시</th><th>의미</th><th>설명</th></tr>
      </thead>
      <tbody>
        <tr>
          <td style="text-align:center;"><img src="IMG_ICON_DANGER" style="height:28px;" alt="위험"></td>
          <td>심각한 위험</td>
          <td>준수하지 않을 경우 사망 또는 중상 가능</td>
        </tr>
        <tr>
          <td style="text-align:center;"><img src="IMG_ICON_WARNING" style="height:28px;" alt="경고"></td>
          <td>잠재적 위험</td>
          <td>준수하지 않을 경우 부상 또는 장비 손상 가능</td>
        </tr>
        <tr>
          <td style="text-align:center;"><img src="IMG_ICON_CAUTION" style="height:28px;" alt="금지"></td>
          <td>금지 사항</td>
          <td>특정 행위를 절대 하지 말 것</td>
        </tr>
      </tbody>
    </table>

    <h2 class="section">1.2. 장비 사용 안내</h2>
    <h3 class="subsection">운영 담당자 안내</h3>
    <p>본 장비는 지정된 교육을 이수한 담당자만 조작할 수 있습니다.</p>
    <ul class="items">
      <li>장비 조작 전 안전 교육 필수 이수</li>
      <li>개인 보호장구(PPE) 착용</li>
      <li>비상 정지 위치 숙지</li>
    </ul>

    <h3 class="subsection">장비 명판</h3>
    <div class="figure">
      <div class="figure-placeholder">장비 명판 이미지</div>
      <div class="figure-caption">그림 1-1. 장비 명판 위치</div>
    </div>
  </div>
  <div class="page-footer page-footer-even">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">4</span>
  </div>
</div>

<!-- PAGE 5: 2. Safety Notes -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_ODD" alt="header"></div>
  <div class="page-section-label">2. Safety Notes</div>
  <div class="page-body">
    <h1 class="chapter">2. 안전 유의 사항</h1>

    <h2 class="section">2.3. 부착 경고 표시</h2>

    <h3 class="subsection">Electrical Warning</h3>
    <div class="notice danger">
      <img class="notice-icon" src="IMG_ICON_DANGER" alt="위험">
      <div class="notice-content">
        <div class="notice-title">Electrical Warning</div>
        <ul class="items">
          <li>Warnings due to electrical voltage</li>
        </ul>
        <strong>Caution!</strong>
        <ul class="items">
          <li>Be sure to disconnect the mains power and wear safety gloves when performing any repairs.</li>
        </ul>
      </div>
    </div>

    <h3 class="subsection">Risk of pinching/curling</h3>
    <div class="notice">
      <img class="notice-icon" src="IMG_ICON_WARNING" alt="경고">
      <div class="notice-content">
        <div class="notice-title">Risk of pinching/curling</div>
        <ul class="items">
          <li>Risk of pinching and curling during machine operation</li>
        </ul>
        <strong>Caution!</strong>
        <ul class="items">
          <li>Do not touch hazardous areas while the machine is running.</li>
        </ul>
      </div>
    </div>

    <h3 class="subsection">Collision risk</h3>
    <div class="notice">
      <img class="notice-icon" src="IMG_ICON_WARNING" alt="경고">
      <div class="notice-content">
        <div class="notice-title">Collision risk</div>
        <ul class="items">
          <li>Overhanging collision hazards</li>
        </ul>
        <strong>Caution!</strong>
        <ul class="items">
          <li>Prohibit access to hazardous areas while the machine is running.</li>
        </ul>
      </div>
    </div>

    <h3 class="subsection">Door interlock in operation</h3>
    <div class="notice">
      <img class="notice-icon" src="IMG_ICON_CAUTION" alt="금지">
      <div class="notice-content">
        <div class="notice-title">Door interlock in operation</div>
        <ul class="items">
          <li>When the interlocked doors are opened during the operation, the machine will stop.</li>
        </ul>
        <strong>Caution!</strong>
        <ul class="items">
          <li>Beware of opening the doors during the operations.</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="page-footer page-footer-odd">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">11</span>
  </div>
</div>

<!-- PAGE 6: 3. Commissioning -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_EVEN" alt="header"></div>
  <div class="page-section-label">3. Commissioning</div>
  <div class="page-body">
    <h1 class="chapter">3. 시운전</h1>

    <h2 class="section">3.4. 기본 조작</h2>

    <h3 class="subsection">Control panel descriptions</h3>
    <p>A description of the control switches located on the front of the installation.</p>

    <div class="figure">
      <div class="figure-placeholder">컨트롤 패널 이미지</div>
      <div class="figure-caption">Figure 3-2 Control panel descriptions</div>
    </div>

    <p style="font-weight:700; text-align:center; margin-bottom:8px;">Table 3-1 Control panel descriptions</p>
    <table class="manual-table">
      <thead>
        <tr><th>Separation</th><th>Features</th></tr>
      </thead>
      <tbody>
        <tr><td style="text-align:center;">POWER lamp</td><td>Displays the power status of the installation.<br>(powered on when the green LED is lit)</td></tr>
        <tr><td style="text-align:center;">START button</td><td>Unpause the HMI after it has started driving.</td></tr>
        <tr><td style="text-align:center;">PAUSE button</td><td>Start and pause driving on the HMI.</td></tr>
        <tr><td style="text-align:center;">E-STOP button</td><td>Emergency shutdown of the machine.</td></tr>
      </tbody>
    </table>
  </div>
  <div class="page-footer page-footer-even">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">19</span>
  </div>
</div>

<!-- PAGE 7: 12. Error Alarms -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_ODD" alt="header"></div>
  <div class="page-section-label">12. Error Alarms</div>
  <div class="page-body">
    <h1 class="chapter">12. 에러 알람</h1>

    <h2 class="section">12.1. 에러 리스트</h2>
    <p>아래 표는 장비 운전 시 발생할 수 있는 에러 코드와 대처 방법입니다.</p>

    <table class="manual-table error-table">
      <thead>
        <tr><th>코드</th><th>에러 내용</th><th>원인</th><th>대처 방법</th></tr>
      </thead>
      <tbody>
        <tr><td>E-01</td><td>비상 정지</td><td>비상 정지 버튼 동작</td><td>비상 정지 해제 후 리셋</td></tr>
        <tr><td>E-02</td><td>안전도어 열림</td><td>안전도어 미닫힘</td><td>도어 닫기 후 리셋</td></tr>
        <tr><td>E-03</td><td>서보 알람</td><td>서보 드라이버 이상</td><td>서보 알람 리셋, 재발 시 점검</td></tr>
        <tr><td>E-04</td><td>공압 이상</td><td>공압 공급 부족</td><td>공압 라인 및 레귤레이터 점검</td></tr>
        <tr><td>E-05</td><td>원점 복귀 실패</td><td>센서 미감지</td><td>센서 위치 및 배선 점검</td></tr>
      </tbody>
    </table>
  </div>
  <div class="page-footer page-footer-odd">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">53</span>
  </div>
</div>

<!-- PAGE 8: 13. Maintenance -->
<div class="page">
  <div class="page-header"><img src="IMG_HEADER_EVEN" alt="header"></div>
  <div class="page-section-label">13. Maintenance</div>
  <div class="page-body">
    <h1 class="chapter">13. 유지보수</h1>

    <h2 class="section">13.1. 지속/정기적 점검 목록</h2>
    <table class="manual-table">
      <thead>
        <tr><th>주기</th><th>점검 항목</th><th>점검 내용</th><th style="width:50px;">확인</th></tr>
      </thead>
      <tbody>
        <tr><td>일일</td><td>공압 확인</td><td>레귤레이터 압력 0.5MPa 이상</td><td style="text-align:center;">&#9744;</td></tr>
        <tr><td>일일</td><td>청소</td><td>장비 외관 및 작업대 청소</td><td style="text-align:center;">&#9744;</td></tr>
        <tr><td>주간</td><td>그리스 도포</td><td>LM 가이드 및 볼스크류</td><td style="text-align:center;">&#9744;</td></tr>
        <tr><td>주간</td><td>벨트 점검</td><td>타이밍 벨트 장력 및 마모</td><td style="text-align:center;">&#9744;</td></tr>
        <tr><td>월간</td><td>센서 점검</td><td>각 센서 동작 상태 확인</td><td style="text-align:center;">&#9744;</td></tr>
        <tr><td>반기</td><td>서보 점검</td><td>서보 드라이버 파라미터 확인</td><td style="text-align:center;">&#9744;</td></tr>
      </tbody>
    </table>

    <h2 class="section">13.3. 소모품 리스트</h2>
    <table class="manual-table">
      <thead>
        <tr><th>No</th><th>부품명</th><th>규격</th><th>수량</th><th>교체 주기</th></tr>
      </thead>
      <tbody>
        <tr><td style="text-align:center;">1</td><td>흡착 패드</td><td>&#934;10 진공패드</td><td style="text-align:center;">4</td><td>3개월</td></tr>
        <tr><td style="text-align:center;">2</td><td>실린더 씰</td><td>CDQSB20-15D</td><td style="text-align:center;">2</td><td>6개월</td></tr>
        <tr><td style="text-align:center;">3</td><td>타이밍 벨트</td><td>2GT-200</td><td style="text-align:center;">1</td><td>12개월</td></tr>
        <tr><td style="text-align:center;">4</td><td>필터 레귤레이터</td><td>AW30-02BG</td><td style="text-align:center;">1</td><td>12개월</td></tr>
      </tbody>
    </table>
  </div>
  <div class="page-footer page-footer-even">
    <img class="footer-logo" src="IMG_WTA_LOGO" alt="WTA">
    <span class="footer-slogan">WTA aspire Global No.1</span>
    <span class="page-num">60</span>
  </div>
</div>

<!-- PAGE 9: Back Cover -->
<div class="page">
  <div class="back-cover">
    <img src="IMG_WTA_BACK_LOGO" alt="WTA">
  </div>
</div>

</body>
</html>"""

# Replace placeholders with actual base64 data
replacements = {
    "IMG_WTA_LOGO": img["wta_logo"],
    "IMG_WTA_BACK_LOGO": img["wta_back_logo"],
    "IMG_HEADER_EVEN": img["header_even"],
    "IMG_HEADER_ODD": img["header_odd"],
    "IMG_ICON_DANGER": img["icon_danger"],
    "IMG_ICON_WARNING": img["icon_warning"],
    "IMG_ICON_CAUTION": img["icon_caution"],
    "IMG_ICON_NOTE": img["icon_note"],
}

for placeholder, data in replacements.items():
    html = html.replace(placeholder, data)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Written: {os.path.basename(OUT_PATH)} ({len(html):,} bytes)")
