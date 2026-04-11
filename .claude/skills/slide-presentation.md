# WTA 공식 슬라이드 제작 스킬

## 트리거 키워드
슬라이드, 프레젠테이션, PPT, 보고서 슬라이드, HTML 슬라이드, 발표자료

## 개요
WTA 공식 Template.pptx 기반 슬라이드를 HTML로 제작한다.
배경 이미지(표지/내용/엔딩), 색상, 폰트, 레이아웃 모두 회사 템플릿을 따른다.

---

## 1. 템플릿 설정 파일
반드시 먼저 읽을 것: `config/templates/slide-template.json`

## 2. 배경 이미지 (Template.pptx에서 추출 → Supabase Storage)
| 용도 | 이미지 | URL |
|------|--------|-----|
| 표지 | image2.jpeg | `https://agent.mes-wta.com/api/files/bd028b463d6d4d95918bea750e20b841.jpeg` |
| 내용 슬라이드 | image1.jpeg | `https://agent.mes-wta.com/api/files/a89d5031ddf944299d06d7cc81d85ae5.jpeg` |
| 목차 | image3.jpeg | `https://agent.mes-wta.com/api/files/4bfb9fda9b44478f853fe05dfee0da0b.jpeg` |
| 구역 머리글 | image4.jpeg | `https://agent.mes-wta.com/api/files/767f5f539c6d4552b09572a599182cd8.jpeg` |
| 엔딩 | image5.jpeg | `https://agent.mes-wta.com/api/files/9b5e7c81a5774beda5c9a37a0bf98454.jpeg` |

> **중요**: 절대 URL을 사용하므로 HTML 저장 위치에 무관하게 동작함. 로컬 상대경로(`template-images/`) 사용 금지.

## 3. 디자인 규칙

### 색상 체계
```
primary_red:     #CC0000   — 제목, 강조, 주요 포인트
safe_green:      #2E7D32   — 긍정/완료/안전
info_blue:       #1565C0   — 정보/참고
warning_orange:  #E65100   — 주의/경고
text_dark:       #222222   — 강조 텍스트
text_body:       #444444   — 본문
text_light:      #888888   — 보조/캡션
background:      #FFFFFF   — 슬라이드 배경
card_bg:         #F8F8F8   — 박스/카드 배경
page_bg:         #E8E8E8   — 페이지 배경 (body)
```

### 폰트
- 기본: `'맑은 고딕', 'Malgun Gothic', -apple-system, sans-serif`
- 표지 제목: 34px, 슬라이드 제목: 25px, 본문: 17px, 리스트: 16px
- 박스 제목: 17px, 박스 본문: 15px, 캡션: 13px

### 슬라이드 비율
- **16:9 비율 필수** — `aspect-ratio: 16/9` 적용
- max-width: 1100px, min-height: 580px
- **내용이 넘치면 내용을 압축** (overflow:hidden, 넘치는 슬라이드 금지)

## 4. HTML 구조

### 필수 슬라이드 구성
1. **표지** (cover) — 배경: image2.jpeg
2. **내용 슬라이드** (content-slide) — 배경: image1.jpeg, 여러 장
3. **엔딩** (ending) — 배경: image5.jpeg, **내용 없이 빈 슬라이드** (배경 이미지에 Thank You 포함)

### 내용 슬라이드 레이아웃 (핵심)
```html
<div class="slide content-slide">
  <div class="s-header"><div class="s-title">슬라이드 제목</div></div>
  <div class="s-body">
    <!-- 본문 내용 -->
  </div>
  <div class="slide-num">01</div>
</div>
```

- `s-header`: 높이 90px, 배경 삼각형 오른쪽에 제목 배치
- `s-title`: padding-left: calc(2em + 25px) (삼각형 회피 + 우측 여백), 검정(#000000), 25px, bold, margin-top: 11px
- `s-body`: padding: 48px 40px 16px 40px, flex:1, overflow:hidden

### 상단 버튼 바 (필수 — 모든 슬라이드 HTML에 항상 포함)

두 버튼: **PPT 변환** / **PDF 저장**
- PPT는 반드시 API 사용(`/api/convert/html-to-pptx-v2`). 사전 생성·하드코딩 금지.
- PDF도 API 사용(`/api/convert/html-to-pdf`).
- 현재 보고 있는 HTML 파일 자신을 서버에 업로드 → 변환 결과 다운로드.

```html
<div class="ppt-bar">
  <button class="ppt-btn" onclick="convertSlide('pptx')">📥 PPT 변환</button>
  <button class="ppt-btn pdf" onclick="convertSlide('pdf')">📄 PDF 저장</button>
</div>

<script>
async function convertSlide(kind){
  const btn = event.currentTarget;
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = kind === 'pptx' ? '변환 중...' : '저장 중...';
  try {
    // 현재 페이지의 HTML 원본을 fetch → multipart upload
    const htmlResp = await fetch(location.href);
    const htmlText = await htmlResp.text();
    const blob = new Blob([htmlText], { type: 'text/html' });

    const rawName = (location.pathname.split('/').pop() || 'slide').replace(/\.html$/i,'');
    const filename = rawName + '.html';

    const form = new FormData();
    form.append('html_file', blob, filename);

    const endpoint = kind === 'pptx'
      ? 'https://agent.mes-wta.com/api/convert/html-to-pptx-v2'
      : 'https://agent.mes-wta.com/api/convert/html-to-pdf';

    const res = await fetch(endpoint, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.text();
      alert('변환 실패: ' + err.slice(0, 200));
      return;
    }
    const outBlob = await res.blob();
    const url = URL.createObjectURL(outBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = rawName + (kind === 'pptx' ? '.pptx' : '.pdf');
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('오류: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
}
</script>
```

관련 CSS(ppt-bar, ppt-btn)는 §5에 정의되어 있으며 `.ppt-btn.pdf { background:#1565C0 }` 같은 variant를 추가해 색 구분한다.

## 5. CSS 템플릿

```css
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'맑은 고딕','Malgun Gothic',-apple-system,sans-serif;background:#e8e8e8;color:#333}
.slide-wrap{max-width:1100px;margin:0 auto;padding:20px}

/* 슬라이드 공통 — 16:9 고정, 내용 벗어남 금지 */
.slide{background:#fff;border-radius:4px;padding:0;margin-bottom:24px;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.15);display:flex;flex-direction:column;aspect-ratio:16/9}
.slide-num{position:absolute;bottom:10px;right:28px;font-size:11px;color:#999;font-weight:600}

/* 표지 — Supabase Storage 절대 URL */
.cover{background:url('https://agent.mes-wta.com/api/files/bd028b463d6d4d95918bea750e20b841.jpeg') center/cover no-repeat;justify-content:center;align-items:flex-start;padding:80px;overflow:hidden}
.cover h1{font-size:34px;font-weight:700;color:#333;line-height:1.3;margin-bottom:10px}
.cover .sub{font-size:18px;color:#666;margin-bottom:28px;line-height:1.5}
.cover .meta{font-size:14px;color:#888;line-height:1.8}

/* 내용 슬라이드 */
.content-slide{background:url('https://agent.mes-wta.com/api/files/a89d5031ddf944299d06d7cc81d85ae5.jpeg') center/cover no-repeat;padding:0;overflow:hidden}
.content-slide .s-header{height:64px;display:flex;align-items:center;padding-left:40px;flex-shrink:0}
.content-slide .s-title{font-size:25px;font-weight:700;color:#000000;margin:11px 0 0 0;padding-left:calc(2em + 25px)}
.content-slide .s-body{padding:48px 40px 16px 40px;flex:1;overflow:hidden}
.content-slide .s-body>*{margin-bottom:8px}
.content-slide .s-body>*:last-child{margin-bottom:0}

/* 엔딩 — 배경 이미지에 Thank You가 포함되어 있으므로 내용 없이 빈 슬라이드 */
.ending{background:url('https://agent.mes-wta.com/api/files/9b5e7c81a5774beda5c9a37a0bf98454.jpeg') center/cover no-repeat;justify-content:center;align-items:center;text-align:center;padding:80px;overflow:hidden}

/* 타이포그래피 */
.slide p{font-size:17px;line-height:1.9;color:#444;margin-bottom:10px}
.slide li{font-size:16px;line-height:2;color:#444;margin-bottom:4px}
.slide ul{padding-left:24px}
.slide strong{color:#222;font-weight:700}
.hl{color:#CC0000;font-weight:700}
.safe{color:#2E7D32}
.accent{color:#CC0000}

/* 박스 */
.box{background:#f8f8f8;border:1px solid #e0e0e0;border-radius:8px;padding:20px 24px;margin:12px 0}
.box.red{border-left:4px solid #CC0000}
.box.green{border-left:4px solid #2E7D32}
.box.blue{border-left:4px solid #1565C0}
.box.orange{border-left:4px solid #E65100}
.box h4{font-size:17px;font-weight:700;margin-bottom:8px;color:#222}
.box p{font-size:15px;margin-bottom:4px}

/* 그리드 */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:12px 0}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0}

/* 큰 숫자 */
.big{text-align:center;padding:16px}
.big .num{font-size:48px;font-weight:900;line-height:1}
.big .num.red{color:#CC0000}
.big .num.green{color:#2E7D32}
.big .num.blue{color:#1565C0}
.big .label{font-size:13px;color:#888;margin-top:6px}

/* 태그 */
.tag{display:inline-block;padding:3px 12px;border-radius:4px;font-size:13px;font-weight:700}
.tag.green{background:#E8F5E9;color:#2E7D32}
.tag.yellow{background:#FFF8E1;color:#E65100}
.tag.red{background:#FFEBEE;color:#C62828}

/* 표 */
table{width:100%;border-collapse:collapse;margin:12px 0}
th{text-align:left;padding:10px 14px;background:#f5f5f5;color:#666;font-size:13px;font-weight:600;border-bottom:2px solid #CC0000}
td{padding:10px 14px;border-bottom:1px solid #eee;font-size:14px;color:#444}
tr:hover td{background:#fafafa}

/* VS 비교 */
.vs{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;margin:12px 0}
.vs-col{padding:20px}
.vs-col.bad{background:#FFF5F5;border-right:1px solid #e0e0e0}
.vs-col.good{background:#F0FFF0}

/* 상단 버튼 바 (PPT 변환 / PDF 저장) */
.ppt-bar{max-width:1100px;margin:0 auto;padding:12px 20px 0;display:flex;justify-content:flex-end;gap:8px}
.ppt-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 18px;background:#CC0000;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none;font-family:inherit}
.ppt-btn:hover{background:#a00}
.ppt-btn.pdf{background:#1565C0}
.ppt-btn.pdf:hover{background:#0d4a94}
.ppt-btn:disabled{opacity:0.6;cursor:not-allowed}

.footer{text-align:center;padding:24px;color:#999;font-size:11px}
@media print{.slide{break-inside:avoid;page-break-inside:avoid;box-shadow:none}.ppt-bar{display:none}}
```

## 6. 콘텐츠 작성 규칙

### 16:9 비율 유지 (필수)
1. 내용 작성 후 슬라이드 높이 확인
2. 넘치면 텍스트 압축, 패딩 축소, 항목 통합
3. **절대 overflow 허용하지 않음**

### 슬라이드 수 권장
- 간단 보고: 5~8장
- 일반 보고서: 10~15장
- 전체 발표: 15~20장

### 구성요소 선택
| 내용 유형 | 권장 요소 |
|----------|----------|
| 핵심 수치 | `.big .num` + `.label` |
| 비교 | `.vs` (좌우 비교) 또는 `.g2` |
| Q&A | `.box` 반복 |
| 데이터 | `table` |
| 강조 | `.box.green` / `.box.red` |
| 도식 | `.diagram` + `.d-node` |

## 7. 저장 및 배포

### 저장 위치 (필수)
```
C:/MES/wta-agents/reports/MAX/{{파일명}}.html
```
또는 에이전트별:
```
C:/MES/wta-agents/reports/{{에이전트명}}/{{파일명}}.html
```

### 클라우드플레어 접근 경로
저장 후 자동으로 접근 가능:
```
https://agent.mes-wta.com/{{파일명}}
```
(reports/ 하위 폴더는 URL에 포함하지 않음)

### PDF 내보내기 (Playwright)
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('file:///C:/MES/wta-agents/reports/MAX/{{파일명}}.html')
    page.wait_for_timeout(3000)
    page.pdf(path='{{출력경로}}.pdf',
             width='11.458in', height='6.445in',
             print_background=True,
             margin={'top':'0','bottom':'0','left':'0','right':'0'})
    browser.close()
```
> **핵심**: PDF 페이지 크기를 슬라이드 실제 비율(1100x619px → 11.458x6.445in)에 정확히 맞춰야 함. A4나 표준 16:9(13.333x7.5in) 사용 금지.

### PPT 내보내기
PPTX 파일이 필요한 경우:
1. `workspaces/MAX/gen_security_slide_pptx.py` 참조하여 python-pptx 스크립트 작성
2. `C:/MES/frontend/public/{{파일명}}.pptx`에 저장
3. MES 백엔드 `pptx_handler.go`에 엔드포인트 추가
4. HTML 상단 PPT 다운로드 버튼 연결

### 완료 보고 시 포함할 정보
1. 파일명 및 경로
2. 클라우드플레어 URL
3. 슬라이드 수
4. PPT 다운로드 가능 여부

## 8. 참조 파일
- 템플릿 설정: `config/templates/slide-template.json`
- 실제 구현 예시: `reports/MAX/security-slide.html`
- PPTX 생성 스크립트: `workspaces/MAX/gen_security_slide_pptx.py`
- 배경 이미지: Supabase Storage `template-images` bucket (원본: `reports/MAX/template-images/image1~5.jpeg`)
- 템플릿 쇼케이스: `reports/MAX/template-showcase.html`
