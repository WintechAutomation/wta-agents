# manuals-v2 RAG + GraphRAG 파이프라인 (v1 확정)

부서장 승인일: 2026-04-11
담당: docs-agent (파이프라인 실행), db-manager (스키마), crafter/admin-agent (인프라 지원)

## 개요

`data/manuals/` 원본 약 1,939건을 재분류 → 표준명 정리 → Docling 파싱 → 청킹 → Qwen3 임베딩 → LightRAG 엔티티 추출 → 검색/리랭킹 파이프라인까지 구축한다. 핵심 요구사항은 **본문 텍스트와 첨부 이미지(그림/도면/회로도) 간의 관계성 보존**이다.

## 단계별 설계

### 1. 파서 (Parser)

- **Docling** (메인)
  - 옵션: `PdfPipelineOptions(generate_picture_images=True, images_scale=2.0)`
  - 표: `TableFormer`로 구조 보존, 별도 청크 단위로 저장
  - 섹션 계층(H1/H2/H3), 그림/표, 페이지 메타데이터를 `DoclingDocument` 트리로 통합
- **MinerU (PaddleOCR)** — 한국어 OCR 품질 저하 시 폴백 후보로 검토

### 2. OCR

- Docling 내장 **EasyOCR** 사용 (CID 바이너리 / 스캔 PDF 대응)
- **DOCX**는 Docling DOCX 모드로 일관 처리

### 3. 청킹 (Chunking)

- **512 토큰 + 64 오버랩** (초기 1024 대비 하향 확정)
- `HierarchicalChunker` — 섹션/페이지 경계 준수
- 표/코드블록은 단일 청크로 분리 보존
- 섹션 헤더(H1/H2/H3) 컨텍스트를 청크 프리픽스에 포함

### 4. 임베딩 (Embedding)

- **Qwen3-Embedding-8B** (2000차원, MRL 슬라이싱)
- 로컬 Ollama: `http://182.224.6.147:11434/api/embed`
- 모델명: `qwen3-embedding:8b`

### 5. 리랭커 (Reranker) — 신규

- **Qwen3-Reranker-4B**, vLLM 로컬 실행
- 검색 흐름: `BM25 + Dense RRF → Qwen3-Reranker-4B 재순위화`
- PostgreSQL BM25: `pg_bm25` 확장 확인 후 가능하면 DB 레벨 처리, 아니면 앱 레벨 fallback

### 6. GraphRAG — LightRAG 채택

- **LightRAG** 프레임워크 (MS GraphRAG 대신)
- 엔티티 추출 LLM: **qwen3.5:35b-a3b** (로컬 Ollama)
- 청크 단위 엔티티/관계 추출, 증분 업데이트 지원
- 노드 타입: 기본 Entity/Relation 외에 **`Figure` / `Table` / `Diagram`** 추가

### 7. 텍스트-이미지 정렬 (핵심)

- Docling의 `PictureItem` / `TableItem` 노드로 다음 메타 자동 보존
  - `page_no`, `bbox (l,t,r,b)`, `parent_section`, `caption`
- 본문 상호참조 매칭: `(?:그림|Figure|Fig\.?|표|Table)\s*[\d\-\.]+` 정규식 후처리
  - `caption → figure_id` 역인덱스 → `{chunk_id: [figure_ids]}` 맵 생성
- **Qwen2.5-VL-7B** 로컬로 figure 설명 자동 생성 → `vlm_description` 필드 저장
- 텍스트 청크와 이미지 설명을 **동일 벡터 공간(Qwen3-Embedding-8B)** 에서 인덱싱
- 이미지 PNG: **Supabase Storage `manual-images` 버킷** 업로드
  - 경로: `{category}/{file_id}/page_{N}_{figure_id}.png`
  - 썸네일 256px 별도 저장 (프론트 렌더 최적화)

### 8. 저장 스키마 — `manual.documents_v2`

```sql
CREATE TABLE manual.documents_v2 (
  id              BIGSERIAL PRIMARY KEY,
  file_id         TEXT NOT NULL,
  chunk_id        TEXT NOT NULL,
  category        TEXT,        -- 1_robot, 2_sensor, ...
  mfr             TEXT,
  model           TEXT,
  doctype         TEXT,
  lang            TEXT,
  section_path    JSONB,       -- ["3. 배선", "3.2 전원결선"]
  page_start      INTEGER,
  page_end        INTEGER,
  content         TEXT,        -- 청크 텍스트
  embedding       vector(2000),
  figure_refs     JSONB,       -- [{figure_id, caption, image_url, bbox, page, image_type, vlm_description}]
  table_refs      JSONB,       -- [{table_id, html, page}]
  inline_refs     JSONB,       -- 본문 "그림 3.2" 등 매칭 결과
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON manual.documents_v2 USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON manual.documents_v2 (category, mfr, model);
CREATE INDEX ON manual.documents_v2 USING gin (figure_refs);
```

기존 `manual.documents` (218k 청크), `manual.wta_documents` (67k 청크)는 유지. v2 검증 완료 후 단계적 마이그레이션.

### 9. 2차 확장 (차후)

- **ColQwen2** 멀티벡터 페이지 검색 — pgvector multi-vector 지원 확인 후 도입
- **Jina-CLIP-v2** 보조 이미지 벡터화 (크로스모달 확장용)

## 카테고리별 진행 상태 (2026-04-11 기준)

| 카테고리 | 총건수 | unique | dup | ok | ocr필요 | docx | 상태 |
|---|---|---|---|---|---|---|---|
| 1_robot | 199 | 111 | 88 | 108 | 0 | 3 | 완료 |
| 2_sensor | 122 | 102 | 20 | 55 | 45 | 2 | 완료 |
| 3_hmi | 60 | 59 | 1 | 56 | 1 | 2 | 완료 |
| 5_inverter | 17 | 17 | 0 | 6 | 11 | 0 | 완료 |
| 6_plc | 85 | 84 | 1 | 69 | 9 | 6 | 완료 |
| 7_pneumatic | 65 | 65 | 0 | 35 | 30 | 0 | 완료 |
| 4_servo | 315 | - | - | - | - | - | 진행중 |
| 8_etc | 1,076 | - | - | - | - | - | 진행중 |

## 실행 순서

1. **db-manager 협의**: `manual.documents_v2` 테이블 + Supabase `manual-images` 버킷 생성
2. **batch-parse-docling.py 수정**: 이미지 export 옵션 추가, 청킹 512/64, 본문-이미지 매핑 후처리
3. **Qwen3-Reranker-4B 환경 구축**: vLLM 로컬 실행 (crafter 지원)
4. **Qwen2.5-VL-7B Ollama pull**: admin-agent에 모델 요청
5. **1_robot PoC 3건** (Mitsubishi BFP-A8586 급 대형 매뉴얼)
6. **품질 검증** → 승인 시 1_robot 전체 → 나머지 카테고리 확장

## 예상 처리 시간/비용

- 1_robot 108건: Docling 파싱 3~5h, 임베딩 1h, GraphRAG 2~3h = **6~9h**
- 전체 1,939건: 약 **80~120h** (병렬 가능)
- 이미지 추출/업로드: 파일당 +30초 → +50~90분
- 외부 API 비용: **0원** (Claude/OpenAI 미사용, 모두 로컬 Qwen/Ollama/Docling)
- Supabase Storage: `manual-images` 버킷 약 500MB (1_robot 기준 5,400 PNG 예상)

## 관련 파일

- 파이프라인 스크립트: `workspaces/docs-agent/manuals_v2_pipeline.py`
- 카테고리별 CSV: `workspaces/docs-agent/manuals_v2_{cat}_classification.csv`
- 요약: `workspaces/docs-agent/manuals_v2_summary.json`
- 결과 폴더: `data/manuals-v2/{cat}/`, `data/manuals-v2/_filtered/{duplicate|ocr_needed|docx}/{cat}/`
