# CI Assets

WTA HTML 슬라이드 문서에 사용되는 이미지 자산 폴더.
출처: `data/uploads/template.pptx` (추출일: 2026-03-31)

## 등록된 파일

| 파일명 | 원본 | 크기 | 용도 | 슬라이드 클래스 |
|--------|------|------|------|--------------|
| `bg-title.jpeg` | image2 | 103KB | 표지 슬라이드 배경 — 우측 빨간 곡선+회색 원형+WTA 로고 | `slide-title` |
| `bg-slide.jpeg` | image3 | 140KB | 일반 콘텐츠 슬라이드 배경 — 우상단 WTA 로고+하단 웨이브 | `slide-content` |
| `bg-slide-alt.jpeg` | image4 | 85KB | 섹션 구분 슬라이드 배경 — 좌상단 빨간 곡선+우상단 WTA 로고 | (선택 사용) |
| `bg-slide-header.jpeg` | image1 | 85KB | 헤더 강조 슬라이드 배경 — 좌상단 빨간 삼각형+구분선 | (선택 사용) |
| `bg-ending.jpeg` | image5 | 103KB | 마지막 슬라이드 — "THANK YOU / WTA aspire Global No.1" 완성본 | `slide-ending` |
| `logo.png` | (기존) | 8.7KB | WTA 로고 — 빨간 육각형 아이콘 + WTA 텍스트 (다크 배경용) | — |
| `logo_white.png` | (기존) | 8.7KB | WTA 로고 화이트 버전 (어두운 배경용) | — |

> 원본 파일 (`image1.jpeg` ~ `image5.jpeg`)도 동일 폴더에 보존됨.

## 슬라이드 클래스 사용법

```html
<!-- 표지 슬라이드 -->
<div class="slide slide-title active" id="slide-1">...</div>

<!-- 일반 콘텐츠 슬라이드 -->
<div class="slide slide-content" id="slide-2">...</div>

<!-- 마지막 슬라이드 (내용 없이 배경만) -->
<div class="slide slide-ending" id="slide-N"></div>
```

## 참고

- `bg-title.jpeg`, `bg-slide.jpeg`, `bg-slide-alt.jpeg`에는 WTA 로고가 배경에 포함됨
  → `slide-title`, `slide-content` 클래스에서 `.wta-logo` 이미지는 자동 숨김 처리됨
- `slide-ending`은 배경 자체가 완성된 화면이므로 내부 콘텐츠 자동 숨김
- 로고가 없는 배경(`bg-slide-header.jpeg`) 사용 시 `.wta-logo` img 태그를 수동으로 추가할 것
