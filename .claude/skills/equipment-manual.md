# 장비 매뉴얼 제작 스킬

## 트리거 키워드
매뉴얼, 장비 매뉴얼, 사용자 매뉴얼, User Manual, 취급설명서, 운영 매뉴얼

## 개요
WTA 장비 매뉴얼을 A4 인쇄 가능한 HTML 문서로 제작한다.
기준 템플릿: `PVD_Unloading_Manual_KR.html`

## 디자인 규칙

### 색상 체계
```
--wta-red:        #C0392B   /* 메인 레드 — 제목 하단선, 강조 */
--wta-red-dark:   #A93226   /* 위험 경고 */
--wta-red-light:  #E74C3C   /* 커버 스트라이프 */
--wta-gray:       #7F8C8D   /* 보조 회색 */
--text-primary:   #0d0d0d   /* 본문 텍스트 */
--text-secondary: #333      /* 소제목 */
--text-light:     #666      /* 캡션, 보조 텍스트 */
```

### 폰트
- 주 폰트: `'맑은 고딕', 'Malgun Gothic', 'Noto Sans KR', sans-serif`
- 본문: 9.5pt, 줄간격 1.6
- 장 제목(h1): 18pt, border-bottom: 3px solid var(--wta-red)
- 절 제목(h2): 12pt, border-bottom: 1px solid #ddd
- 항 제목(h3): 10pt, border-left: 4px solid #333

### 페이지 규격
- A4 (210mm x 297mm)
- 여백: 좌우 18mm, 하단 25mm
- page-break-after: always (각 .page)
- 인쇄 최적화: @media print 포함

---

## HTML 구조 템플릿

### 기본 뼈대
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>{{장비명}} User Manual — (주)윈텍오토메이션</title>
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
  @page { size: A4; margin: 0; }
  body {
    font-family: '맑은 고딕', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
    font-size: 9.5pt; color: var(--text-primary); line-height: 1.6; background: #e8e8e8;
  }

  /* ── 페이지 ── */
  .page {
    width: 210mm; min-height: 297mm; margin: 8mm auto; background: #fff;
    box-shadow: 0 1px 6px rgba(0,0,0,0.15); position: relative; overflow: hidden;
    page-break-after: always;
  }
  .page:last-child { page-break-after: auto; }
  .page-body { padding: 0 18mm 25mm 18mm; }
  @media print {
    body { background: #fff; }
    .page { margin: 0; box-shadow: none; width: 100%; min-height: auto; }
  }

  /* ── 페이지 헤더/푸터 ── */
  .page-header { width: 100%; margin-bottom: 8px; }
  .page-header img { width: 100%; height: auto; display: block; }
  .page-section-label {
    text-align: right; font-size: 8.5pt; color: var(--text-light);
    font-style: italic; padding: 0 18mm 4px 0; margin-bottom: 8px;
  }
  .page-footer {
    position: absolute; bottom: 0; left: 0; right: 0;
    display: flex; align-items: center; padding: 6px 18mm 10mm;
  }
  .page-footer-even { flex-direction: row; }
  .page-footer-odd { flex-direction: row-reverse; }
  .page-footer .footer-logo { height: 28px; }
  .page-footer .footer-slogan {
    font-size: 8pt; color: var(--text-light); font-style: italic; margin: 0 12px; flex: 1;
  }
  .page-footer-even .footer-slogan { text-align: left; }
  .page-footer-odd .footer-slogan { text-align: right; }
  .page-footer .page-num { font-size: 9pt; font-weight: 600; color: var(--text-secondary); }

  /* ── 표지 ── */
  .cover-page { position: relative; width: 210mm; min-height: 297mm; }
  .cover-stripe { position: absolute; top: 0; right: 0; width: 22mm; height: 100%; min-height: 297mm; }
  .cover-stripe-main { position: absolute; top: 0; right: 0; width: 14mm; height: 85%; background: var(--wta-red); }
  .cover-stripe-accent1 { position: absolute; top: 0; right: 16mm; width: 3mm; height: 12%; background: var(--wta-red); transform: skewY(-2deg); }
  .cover-stripe-accent2 { position: absolute; top: 4%; right: 16mm; width: 3mm; height: 10%; background: var(--wta-red); transform: skewY(-2deg); }
  .cover-stripe-gradient { position: absolute; bottom: 0; right: 0; width: 14mm; height: 15%; background: linear-gradient(180deg, var(--wta-red) 0%, #E67E73 60%, var(--wta-gray) 100%); }
  .cover-logo { position: absolute; top: 28mm; left: 25mm; }
  .cover-logo img { height: 48px; }
  .cover-content { position: absolute; top: 38%; left: 25mm; right: 35mm; }
  .cover-title { font-size: 20pt; font-weight: 700; color: var(--text-primary); line-height: 1.4; margin-bottom: 20px; }
  .cover-meta { font-size: 10pt; color: var(--text-light); line-height: 2; margin-top: 30px; }
  .cover-meta-label { display: inline-block; width: 80px; font-weight: 600; color: var(--text-secondary); }
  .cover-bottom { position: absolute; bottom: 25mm; left: 25mm; }
  .cover-company { font-size: 10pt; font-weight: 700; color: var(--text-secondary); }
  .cover-company-en { font-size: 8pt; color: #999; }

  /* ── 뒷표지 ── */
  .back-cover { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 260mm; padding: 40mm; }

  /* ── 목차 ── */
  .toc-title { font-size: 22pt; font-weight: 700; color: var(--text-primary); margin-bottom: 20px; }
  .toc-list { list-style: none; }
  .toc-chapter { font-size: 11pt; font-weight: 700; color: var(--text-primary); padding: 6px 0 3px; display: flex; justify-content: space-between; border-bottom: 1px solid #eee; }
  .toc-section { font-size: 9.5pt; font-weight: 400; color: var(--text-secondary); padding: 3px 0 3px 16px; display: flex; justify-content: space-between; }
  .toc-dots { flex: 1; border-bottom: 1px dotted #ccc; margin: 0 8px; align-self: flex-end; margin-bottom: 3px; }
  .toc-page { color: var(--text-light); flex-shrink: 0; margin-left: 8px; }

  /* ── 제목 계층 ── */
  h1.chapter { font-size: 18pt; font-weight: 700; color: var(--text-primary); padding-bottom: 8px; border-bottom: 3px solid var(--wta-red); margin-bottom: 16px; page-break-after: avoid; }
  h2.section { font-size: 12pt; font-weight: 700; color: var(--text-primary); margin: 20px 0 10px; padding-bottom: 4px; border-bottom: 1px solid #ddd; page-break-after: avoid; }
  h3.subsection { font-size: 10pt; font-weight: 700; color: var(--text-primary); margin: 14px 0 6px; padding-left: 12px; border-left: 4px solid #333; page-break-after: avoid; }
  p { font-size: 9.5pt; color: var(--text-primary); line-height: 1.7; margin-bottom: 8px; text-align: justify; }

  /* ── 경고 박스 ── */
  .notice { display: flex; align-items: flex-start; gap: 12px; padding: 10px 14px; margin: 12px 0; font-size: 9pt; }
  .notice-icon { width: 44px; height: 44px; flex-shrink: 0; object-fit: contain; }
  .notice-content { flex: 1; }
  .notice-title { font-weight: 700; margin-bottom: 4px; }
  .notice.danger { background: #FDEDEE; border: 2px solid var(--wta-red); }
  .notice.danger .notice-title { color: var(--wta-red-dark); }
  .notice.caution { background: #FFF8E1; border: 2px solid #FFC107; }
  .notice.info { background: #EBF5FB; border: 2px solid #2E86C1; }
  .notice.info .notice-title { color: #1B4F72; }

  /* ── 표 ── */
  table.manual-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 9pt; }
  table.manual-table th { background: #F2F2F2; color: var(--text-primary); font-weight: 600; padding: 6px 10px; text-align: center; border: 1px solid #bbb; }
  table.manual-table td { padding: 5px 10px; border: 1px solid #ddd; vertical-align: middle; }
  table.manual-table tr:nth-child(even) { background: #fafafa; }

  /* ── 그림 ── */
  .figure { text-align: center; margin: 16px 0; page-break-inside: avoid; }
  .figure img { max-width: 100%; max-height: 180mm; border: 1px solid #e0e0e0; }
  .figure-caption { font-size: 8.5pt; color: var(--text-secondary); margin-top: 6px; font-weight: 700; text-align: center; }
  .figure-placeholder { width: 100%; height: 100px; background: #f5f5f5; border: 1px solid #ddd; display: flex; align-items: center; justify-content: center; color: #999; font-size: 9pt; }

  /* ── 순서 목록 ── */
  ol.steps { margin: 8px 0 8px 24px; font-size: 9.5pt; }
  ol.steps li { margin-bottom: 6px; line-height: 1.6; }
  ul.items { margin: 8px 0 8px 20px; font-size: 9.5pt; list-style: disc; }
  ul.items li { margin-bottom: 4px; line-height: 1.6; }
</style>
</head>
<body>
<!-- 표지, 목차, 본문, 뒷표지 순서로 구성 -->
</body>
</html>
```

---

## 페이지 구성 요소

### 1. 표지 (cover-page)
```html
<div class="page cover-page">
  <div class="cover-stripe">
    <div class="cover-stripe-main"></div>
    <div class="cover-stripe-accent1"></div>
    <div class="cover-stripe-accent2"></div>
    <div class="cover-stripe-gradient"></div>
  </div>
  <div class="cover-logo"><img src="/assets/MAX/template-images/wta-logo.png" alt="WTA"/></div>
  <div class="cover-content">
    <div class="cover-title">{{장비명}}<br/>User Manual</div>
    <div class="cover-meta">
      <div><span class="cover-meta-label">문서번호</span>{{문서번호}}</div>
      <div><span class="cover-meta-label">버전</span>{{버전}}</div>
      <div><span class="cover-meta-label">작성일</span>{{작성일}}</div>
      <div><span class="cover-meta-label">작성자</span>{{작성자}}</div>
    </div>
  </div>
  <div class="cover-bottom">
    <div class="cover-company">(주)윈텍오토메이션</div>
    <div class="cover-company-en">WinTec Automation Co., Ltd.</div>
  </div>
</div>
```

### 2. 목차 (TOC)
```html
<div class="page">
  <div class="page-body" style="padding-top: 30mm;">
    <div class="toc-title">목차</div>
    <ul class="toc-list">
      <li class="toc-chapter"><span>1. {{장 제목}}</span><span class="toc-dots"></span><span class="toc-page">3</span></li>
      <li class="toc-section"><span>1.1 {{절 제목}}</span><span class="toc-dots"></span><span class="toc-page">3</span></li>
    </ul>
  </div>
</div>
```

### 3. 본문 페이지
```html
<div class="page">
  <div class="page-section-label">Chapter {{N}} — {{장 이름}}</div>
  <div class="page-body">
    <h1 class="chapter">{{N}}. {{장 제목}}</h1>
    <h2 class="section">{{N.M}} {{절 제목}}</h2>
    <p>{{본문}}</p>

    <h3 class="subsection">{{소제목}}</h3>
    <ol class="steps">
      <li>{{절차 1}}</li>
      <li>{{절차 2}}</li>
    </ol>
  </div>
  <div class="page-footer page-footer-odd">
    <span class="page-num">{{페이지 번호}}</span>
    <span class="footer-slogan">WinTec Automation — Quality beyond precision</span>
  </div>
</div>
```

### 4. 경고 박스
```html
<!-- 위험 (빨간) -->
<div class="notice danger">
  <div class="notice-content">
    <div class="notice-title">&#9888; 위험</div>
    <div>{{위험 내용}}</div>
  </div>
</div>

<!-- 주의 (노랑) -->
<div class="notice caution">
  <div class="notice-content">
    <div class="notice-title">&#9888; 주의</div>
    <div>{{주의 내용}}</div>
  </div>
</div>

<!-- 참고 (파랑) -->
<div class="notice info">
  <div class="notice-content">
    <div class="notice-title">&#8505; 참고</div>
    <div>{{참고 내용}}</div>
  </div>
</div>
```

### 5. 그림/이미지
```html
<div class="figure">
  <img src="{{이미지 경로}}" alt="{{설명}}"/>
  <div class="figure-caption">그림 {{번호}}. {{캡션}}</div>
</div>

<!-- 이미지 없을 때 -->
<div class="figure">
  <div class="figure-placeholder">[ 이미지 삽입 위치: {{설명}} ]</div>
  <div class="figure-caption">그림 {{번호}}. {{캡션}}</div>
</div>
```

### 6. 표
```html
<table class="manual-table">
  <tr><th>{{헤더1}}</th><th>{{헤더2}}</th><th>{{헤더3}}</th></tr>
  <tr><td>{{데이터}}</td><td>{{데이터}}</td><td>{{데이터}}</td></tr>
</table>
```

### 7. 뒷표지
```html
<div class="page">
  <div class="back-cover">
    <img src="/assets/MAX/template-images/wta-logo.png" alt="WTA"/>
    <p style="margin-top:20px; font-size:10pt; color:#999;">(주)윈텍오토메이션</p>
    <p style="font-size:8pt; color:#bbb;">WinTec Automation Co., Ltd.</p>
  </div>
</div>
```

---

## 매뉴얼 표준 목차 (장비별 조정)

1. **안전 주의사항** — 위험/경고/주의 등급, 안전 기호
2. **장비 개요** — 용도, 주요 사양, 외형도
3. **설치** — 설치 환경, 전원, 에어, 연결
4. **조작부 설명** — HMI 패널, 버튼, 스위치
5. **운전 절차** — 시작/정지/자동/수동 모드
6. **유지보수** — 일일/주간/월간 점검표
7. **고장 진단** — 에러 코드, 원인, 조치
8. **부품 목록** — 소모품, 교체 주기
9. **부록** — 회로도, 배관도, 승인 이력

---

## 제작 프로세스

1. 원본 자료 확인: `data/wta-manuals-final/` 또는 `data/wta_parsed/` 에서 파싱된 원본 참조
2. 목차 구성: 위 표준 목차 기반으로 장비에 맞게 조정
3. HTML 작성: 위 템플릿 구조 사용
4. 이미지: 원본 매뉴얼에서 추출하거나 figure-placeholder로 위치 표시
5. 저장: `C:/MES/wta-agents/reports/{{장비명}}_Manual_KR.html`
6. 번역 필요 시: 동일 구조로 `_EN.html`, `_CN.html`, `_JP.html` 생성

## 저장 위치
`C:/MES/wta-agents/reports/` 하위

## 외부 접근
reports/ 폴더에 저장하면 자동으로 외부 접속 가능:
`https://father-changed-swing-brook.trycloudflare.com/{{파일명(확장자 제외)}}`
