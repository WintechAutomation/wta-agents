# 매뉴얼 이미지 카탈로그 제작 스킬

## 트리거 키워드
이미지 매칭, 이미지 정리, 이미지 카탈로그, 이미지 확인, 매뉴얼 이미지

## 개요
장비 매뉴얼 HTML에서 모든 이미지를 추출하여 구조화된 이름을 부여하고,
한눈에 확인할 수 있는 갤러리 HTML을 생성한다.
기준 예시: `reports/pvd_이미지_매칭_확인.html`

---

## 1. 입력
- 매뉴얼 HTML 파일 경로 (예: `reports/PVD_Unloading_Manual_KR.html`)
- 또는 매뉴얼 이미지 디렉토리 (예: `data/manual_images/1. User Manual (PVD Unloading MC)/`)

## 2. 이미지 파일명 규칙

### 형식
```
NNN_그림_X-Y_설명.ext
```

| 요소 | 설명 | 예시 |
|------|------|------|
| NNN | 3자리 순번 (001부터) | 001, 002, ... |
| 그림 | 고정 접두사 | 그림 |
| X-Y | 장-절 번호 (figure-caption 기준) | 1-1, 5-2, 10-3 |
| 설명 | 캡션 핵심 내용 (공백→언더스코어) | 전면부, 모델_상세_설정 |
| ext | 원본 확장자 유지 | .jpg, .png |

### 특수 이미지 (그림 번호 없는 경우)
```
NNN_부록_설명.ext
```
예: `037_전기_회로도_—_별도_첨부.png`

## 3. 갤러리 HTML 구조

### 파일명 규칙
```
{장비명_영문약어}_이미지_매칭_확인.html
```
예: `pvd_이미지_매칭_확인.html`, `cvd_이미지_매칭_확인.html`

### HTML 템플릿
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{{장비명}} 이미지 매칭 확인</title>
<style>
  body { font-family: '맑은 고딕', sans-serif; background: #f5f5f5; padding: 20px; }
  h1 { font-size: 14pt; color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }
  .summary { color: #555; font-size: 10pt; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
  .card { background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
  .card img { width: 100%; height: 160px; object-fit: contain; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }
  .seq { font-size: 9pt; color: #aaa; margin-bottom: 4px; }
  .cap { font-size: 10pt; font-weight: 700; color: #1a237e; margin-top: 8px; }
  .fname { font-size: 8pt; color: #888; font-family: monospace; margin-top: 2px; word-break: break-all; }
  .size { font-size: 8pt; color: #bbb; margin-top: 2px; }
</style>
</head>
<body>
<h1>{{장비명}} 매뉴얼 — 이미지 매칭 확인</h1>
<div class="summary">총 {{N}}개 파일 | {{출처 폴더}} | 파일명 = HTML figure-caption 기준</div>
<div class="grid">
    <!-- 카드 반복 -->
    <div class="card">
      <div class="seq">{{순번}}</div>
      <img src="{{이미지_src}}" alt="{{캡션}}"/>
      <div class="cap">{{캡션}}</div>
      <div class="fname">{{구조화된_파일명}}</div>
    </div>
</div>
</body>
</html>
```

## 4. 제작 프로세스

### Step 1: 매뉴얼에서 이미지 목록 추출
매뉴얼 HTML에서 `<div class="figure">` 블록을 모두 찾아:
- `<img>` 태그의 `src` 속성 (base64 또는 URL)
- `<div class="figure-caption">` 텍스트

### Step 2: 파일명 생성
각 이미지에 대해 `NNN_그림_X-Y_설명.ext` 형식의 파일명을 생성한다.
- 캡션에서 "그림 X-Y" 패턴을 추출하여 장-절 번호 결정
- 나머지 텍스트를 설명으로 사용 (공백→`_`, 특수문자 유지)
- 순번은 매뉴얼 등장 순서대로 001부터 부여

### Step 3: 갤러리 HTML 생성
위 템플릿에 따라 HTML 파일 생성.
- 이미지 src는 원본 매뉴얼의 src를 그대로 사용 (base64 또는 URL)
- 저장: `C:/MES/wta-agents/reports/{장비명_약어}_이미지_매칭_확인.html`

### Step 4: 이상 이미지 표시 (선택)
- 해상도가 너무 낮거나 (< 100x100px)
- 관련 없는 이미지 (아이콘, 로고 등)
- 영문/타언어 이미지가 한국어 매뉴얼에 삽입된 경우
→ 카드에 경고 표시 추가:
```html
<div class="card" style="border: 2px solid #e74c3c;">
  <!-- ... -->
  <div style="color:#e74c3c; font-size:8pt; margin-top:4px;">⚠ 확인 필요: {{사유}}</div>
</div>
```

## 5. 매뉴얼 이미지 소스 디렉토리

WTA 자체 장비 매뉴얼 이미지는 아래 경로에 있다:
```
C:\MES\wta-agents\data\manual_images\
```
- 디렉토리명이 매뉴얼명 (예: `1. User Manual (PVD Unloading MC)`)
- 파일명: `page_N_full.png` 또는 `img_NNN.ext`
- 약 1,442개 디렉토리 (부품 매뉴얼 포함)

### WTA 장비 매뉴얼 주요 키워드
PVD, CVD, Press, Honing, Loading, Unloading, Labeling, Repalleting, Grinder, Insert, Handler

## 6. 저장 위치
`C:/MES/wta-agents/reports/` 하위

## 7. 외부 접근
`https://agent.mes-wta.com/{파일명(확장자 제외)}`
