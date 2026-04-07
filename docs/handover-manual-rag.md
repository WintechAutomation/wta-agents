# 매뉴얼 RAG 시스템 인수인계 문서

> 작성일: 2026-03-30 | 작성자: cs-agent → 문서작성 전담팀 인계

---

## 1. 보유 매뉴얼 관련 자산

### 1.1 부품 매뉴얼 (벡터 임베딩 완료분)

| 카테고리 | 폴더 | 파일 수 | 청크 수 |
|---------|------|--------|--------|
| 1_robot | data/manuals-ready/1_robot | - | 32,397 |
| 2_sensor | data/manuals-ready/2_sensor | - | 11,075 |
| 3_hmi | data/manuals-ready/3_hmi | - | 29,196 |
| 4_servo | data/manuals-ready/4_servo | - | 78,232 |
| 5_inverter | data/manuals-ready/5_inverter | - | 508 |
| 6_plc | data/manuals-ready/6_plc | - | 5,465 |
| 7_pneumatic | data/manuals-ready/7_pneumatic | - | 665 |
| 8_etc | data/manuals-ready/8_etc | - | 31,282 |
| **합계** | | **810/892개** | **188,820청크** |

- 원본 위치: `C:\MES\wta-agents\data\manuals-ready\` (카테고리별 서브폴더)
- 스킵된 파일: `data/manuals-skipped/skip_log.jsonl` (11개, 텍스트 500자 미만)
- 진행 추적: `data/manual_progress.json`

### 1.2 WTA 자체 매뉴얼 (부분 임베딩)

| 카테고리 | 파일 수 |
|---------|--------|
| Press (프레스 핸들러) | 188 |
| Inspection (검사기) | 75 |
| PVD | 83 |
| Packaging (포장기) | 48 |
| Sintering_Sorter (소결취출기) | 46 |
| Honing (호닝기) | 26 |
| 기타 13개 카테고리 | 123 |
| **합계** | **590개** |

- 원본 위치: `C:\MES\wta-agents\data\wta-manuals-final\` (영문 카테고리 서브폴더)
- 임베딩 현황: PVD(47,739청크), CBN(141청크) 일부만 완료
- 파싱 완료분: `data/wta_parsed/` (321개 JSON)

### 1.3 CS 이력 임베딩

- 데이터 소스: `csagent.cs_history` 테이블
- 임베딩 건수: **3,318건** (csagent.vector_embeddings)
- 임베딩 모델: Qwen3-Embedding-8B (외부 서버 182.224.6.147:11434)
- 차원: 2000 (Matryoshka 4096→2000 truncate)

### 1.4 QC 체크리스트 임베딩

- 저장 위치: `manual.qc_documents` (633청크)
- 데이터: 출하검사 체크리스트 항목

---

## 2. RAG 파이프라인 구조

### 2.1 부품 매뉴얼 파이프라인

```
PDF 파일 (data/manuals-ready/)
    ↓
manual-embed.py (파싱 + 임베딩)
    ├── PyMuPDF: 텍스트 추출
    ├── pdfplumber: 표 추출
    ├── 이미지: Supabase Storage 업로드
    └── Qwen3-Embedding-8B 임베딩 서버 (182.224.6.147:11434)
    ↓
manual.documents (PostgreSQL, pgvector)
    ↓
manual-search.py / API 검색
```

**스크립트 실행 방법:**
```bash
cd C:\MES\wta-agents

# 전체 처리 (증분 모드 — 이미 완료된 파일 자동 스킵)
py scripts/manual-embed.py

# 특정 카테고리만
py scripts/manual-embed.py --dir data/manuals-ready/4_servo

# 단일 파일
py scripts/manual-embed.py --file "data/manuals-ready/4_servo/파일명.pdf"

# 진행률 확인
py scripts/check-embed-progress.py
```

### 2.2 CS 이력 파이프라인

```
csagent.cs_history (PostgreSQL)
    ↓
cs-embed.py (임베딩)
    └── Qwen3-Embedding-8B (182.224.6.147:11434)
    ↓
csagent.vector_embeddings (pgvector)
    ↓
cs_rag_agent.py / API 검색
```

**스크립트 실행 방법:**
```bash
cd C:\MES\wta-agents

# 증분 모드 (신규/변경 건만)
py scripts/cs-embed.py

# 전체 재임베딩
py scripts/cs-embed.py --full
```

### 2.3 검색 API

- 매뉴얼 검색: `scripts/manual-search.py`
- CS 이력 벡터 검색: `scripts/cs-vector-search.py`
- 통합 RAG 에이전트: `scripts/cs_rag_agent.py` (Pydantic AI 기반)
- 대시보드 API: `http://localhost:5555/api/query/` (등록된 쿼리 목록)

---

## 3. 진행 중인 작업 현황

### 3.1 부품 매뉴얼 임베딩 (진행 중)

| 항목 | 현황 |
|------|------|
| 목표 | 892개 PDF |
| 완료 | 810개 (90.8%) |
| 남은 것 | 82개 |
| 진행 추적 | data/manual_progress.json |
| 로그 | logs/manual-embed-resume.log |

**현재 상태:** 백그라운드 실행 중 (2026-03-30 18:46 기준)
- 일부 파일에서 `current transaction is aborted` 에러 발생하나 파일 단위로 처리되어 계속 진행됨

### 3.2 WTA 매뉴얼 임베딩 (미완료)

| 항목 | 현황 |
|------|------|
| 총 파일 | 590개 (wta-manuals-final/) |
| 파싱 완료 | 321개 (wta_parsed/) |
| 임베딩 완료 | PVD, CBN 일부 (48,585청크) |
| 나머지 | 검사기, Press, 호닝기 등 대량 미임베딩 |

**실행 방법 (WTA 매뉴얼용 별도 스크립트 필요):**
현재 `manual-embed.py`는 `data/manuals-ready/`를 기본 경로로 사용.
WTA 매뉴얼은 `data/wta-manuals-final/`에 있으므로:
```bash
py scripts/manual-embed.py --dir data/wta-manuals-final/Press
```
단, DB 테이블이 `manual.wta_documents`여야 하므로 스크립트 내 `TABLE_NAME` 변수 확인 필요.

---

## 4. 필요한 접근 권한 및 설정 정보

### 4.1 데이터베이스 (PostgreSQL)

```
호스트: localhost:55432
DB: postgres
유저: postgres
비밀번호: (스크립트 내 DB_CONFIG 참조)
```

**핵심 테이블:**
- `manual.documents` — 부품 매뉴얼 벡터 (188,820청크)
- `manual.wta_documents` — WTA 자체 매뉴얼 벡터
- `manual.qc_documents` — QC 체크리스트 벡터
- `csagent.vector_embeddings` — CS 이력 벡터 (3,318건)

### 4.2 임베딩 서버

| 서버 | 주소 | 모델 | 용도 |
|------|------|------|------|
| Qwen3 (외부) | http://182.224.6.147:11434/api/embed | qwen3-embedding:8b | 부품 매뉴얼 + CS 이력 |

**Qwen3 임베딩 서버 상태 확인:**
```bash
curl http://182.224.6.147:11434/api/tags
```

### 4.3 Supabase Storage (이미지)

```
로컬: http://localhost:8000
버킷: vector
이미지 경로: manuals/{카테고리}/{파일명}/page_{n}_img_{m}.png
```

환경변수 `.env`에서:
- `SUPABASE_KEY`: 서비스 롤 키
- `SUPABASE_PUBLIC_URL`: 외부 공개 URL (기본 localhost:8000)

### 4.4 주요 파일 경로

```
C:\MES\wta-agents\
├── scripts\
│   ├── manual-embed.py         # 부품 매뉴얼 파싱+임베딩
│   ├── cs-embed.py             # CS 이력 임베딩
│   ├── qc-embed.py             # QC 체크리스트 임베딩
│   ├── check-embed-progress.py # 진행률 확인
│   ├── manual-search.py        # 매뉴얼 검색 테스트
│   ├── cs-vector-search.py     # CS 이력 벡터 검색
│   ├── cs_rag_agent.py         # 통합 RAG 에이전트
│   ├── batch-parse.py          # 배치 파싱 (임베딩 없이)
│   └── batch-parse-docling.py  # Docling 기반 고품질 파싱
├── data\
│   ├── manuals-ready\          # 부품 매뉴얼 원본 PDF (카테고리별)
│   ├── manuals-skipped\        # 스킵된 파일 + skip_log.jsonl
│   ├── manual_progress.json    # 처리 상태 추적
│   ├── wta-manuals-final\      # WTA 자체 매뉴얼 (영문 분류)
│   └── wta_parsed\             # WTA 매뉴얼 파싱 결과 JSON
└── logs\
    └── manual-embed-resume.log # 최근 임베딩 실행 로그
```

---

## 5. 주의사항 / 노하우

### 5.1 트랜잭션 에러 처리

임베딩 중 간헐적으로 `current transaction is aborted` 에러 발생.
**원인:** 이전 청크 삽입 실패 후 트랜잭션이 롤백되지 않은 상태에서 다음 쿼리 실행.
**대응:** 스크립트가 파일 단위로 예외 처리하므로 해당 파일만 스킵되고 전체 프로세스는 계속됨.
**수동 조치 필요 시:** `manual_progress.json`에서 해당 파일 상태를 `"parsed"`로 되돌리고 재실행.

### 5.2 증분 처리 (이미 완료된 파일 자동 스킵)

`manual_progress.json`에 `"status": "embedded"`인 파일은 자동 스킵됨.
전체 재처리하려면 해당 파일에서 status를 `"parsed"`로 변경 후 실행.

### 5.3 대용량 파일 처리

- 500페이지 이상 PDF는 처리 시간이 10분+ 소요될 수 있음 (Mitsubishi 737페이지 = ~3분)
- 청크 크기: 기본 512토큰 (겹침 128토큰)
- 배치 크기: 16개 (Qwen3 서버 부하 조절용)

### 5.4 WTA 매뉴얼 vs 부품 매뉴얼 DB 테이블 분리

| 분류 | DB 테이블 | 비고 |
|------|-----------|------|
| 부품 매뉴얼 (외부 제조사) | manual.documents | Fanuc, Panasonic, SMC 등 |
| WTA 자체 매뉴얼 | manual.wta_documents | 장비 운용 매뉴얼 |
| QC 체크리스트 | manual.qc_documents | 출하검사 항목 |

스크립트 실행 시 `--table` 옵션 또는 환경변수로 대상 테이블 지정 필요.

### 5.5 WTA 매뉴얼 파싱 현황

WTA 매뉴얼 590개 중 321개만 파싱 완료 (`wta_parsed/`).
나머지 269개는 파싱 미완료 상태이며 임베딩도 미진행.
파싱 재개: `py scripts/batch-parse.py --dir data/wta-manuals-final/`

### 5.6 임베딩 서버 GPU 확인

Qwen3 임베딩 서버(외부) 상태 확인:
```bash
curl http://182.224.6.147:11434/api/tags
# qwen3-embedding:8b 모델이 목록에 있는지 확인
```

---

## 6. 향후 과제

1. **WTA 매뉴얼 임베딩 완료** (269개 파싱 미완료, 대량 미임베딩)
2. **트랜잭션 에러 근본 수정** (manual-embed.py 내 savepoint 처리 추가)
3. **정기 임베딩 스케줄** (신규 CS 이력 자동 임베딩 — 현재 수동)
4. **검색 품질 평가** (RAG 답변 정확도 측정 체계 구축)
5. **멀티모달 검색** (이미지 첨부 CS 이력 → 이미지 임베딩 추가)

---

*문의: cs-agent (이관 전) → 문서작성 전담팀 (이관 후)*
