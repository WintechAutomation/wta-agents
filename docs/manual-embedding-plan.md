# 매뉴얼 파싱+임베딩 작업지시서

> CS RAG 널리지베이스 구축 프로젝트
> 최종 업데이트: 2026-03-28
> 이 문서만 읽으면 세션 재시작 후 바로 이어서 작업 가능

---

## 1. 프로젝트 개요

WTA 장비 매뉴얼을 임베딩하여 슬랙 #CS 기술문의에 자동 답변하는 RAG 널리지베이스 구축.

**목표**: data/manuals-filtered/ 하위 949개 PDF → Qwen3-Embedding-8B 임베딩 → pgvector → cs-agent 기술문의 답변

**현재 상태** (2026-03-28 기준):
- 임베딩 완료: 4개 파일 (1,353 청크)
- 미처리: 945개 파일
- 서비스 레이어: 완성 (`cs_rag_agent.py`)

---

## 2. 파일 현황

### 카테고리별 파일 수 (총 949개)

| 카테고리 | 경로 | 파일 수 |
|---------|------|---------|
| 1_robot | data/manuals-filtered/1_robot/ | 178개 |
| 2_sensor | data/manuals-filtered/2_sensor/ | 105개 |
| 3_hmi | data/manuals-filtered/3_hmi/ | 138개 |
| 4_servo | data/manuals-filtered/4_servo/ | 354개 |
| 5_inverter | data/manuals-filtered/5_inverter/ | 3개 |
| 6_plc | data/manuals-filtered/6_plc/ | 34개 |
| 7_pneumatic | data/manuals-filtered/7_pneumatic/ | 11개 |
| 8_etc | data/manuals-filtered/8_etc/ | 126개 |

### 임베딩 완료 파일 (건너뛰기)
- `1_robot/597-0027-06KO.pdf`
- `2_sensor/EX-10 SERIES.pdf`
- `2_sensor/레이져 마킹 작업공간.pdf`
- `4_servo/CSD5-UM001C-Drive-KO-Sep_2011 - 복사본.pdf`

---

## 3. 역할 분담

| 역할 | 담당 에이전트 | 작업 |
|------|------------|------|
| 파싱팀 (병렬 5명) | dev-agent, qa-agent, sales-agent, issue-manager, nc-manager | PDF 내용 확인 + 메타데이터 + 파싱 |
| 임베딩팀 (순차) | db-manager | 파싱 완료 파일 Qwen3-Embedding-8B 임베딩 + DB 저장 |
| 서비스 레이어 | crafter | Pydantic AI RAG 서비스 유지보수 |
| 조율 | MAX | 진행 상황 모니터링 + 에이전트 배정 |

### 카테고리 배정 (예시)
- dev-agent: 4_servo (354개 — 가장 많음, 개발자 친화적)
- qa-agent: 2_sensor + 7_pneumatic (116개)
- sales-agent: 3_hmi (138개)
- issue-manager: 1_robot (178개)
- nc-manager: 6_plc + 5_inverter + 8_etc (163개)

---

## 4. 파싱 작업 절차 (에이전트용 표준 워크플로)

### 4-1. 작업 시작 전 확인
```bash
# 진행 상황 파일 확인
cat C:/MES/wta-agents/data/manual_progress.json

# 이미 임베딩된 파일 목록 (DB 확인)
py -c "
import psycopg2
conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
  password='your-super-secret-and-long-postgres-password', dbname='postgres')
cur = conn.cursor()
cur.execute('SELECT DISTINCT source_file FROM manual.documents')
for r in cur.fetchall(): print(r[0])
conn.close()
"
```

### 4-2. 각 PDF 파일 처리 순서

1. **PDF 내용 확인** (Read 도구로 파일 열기)
   - 어떤 장비/제품 매뉴얼인지 파악
   - 제조사, 모델명, 문서 종류(사용설명서/설치매뉴얼/카탈로그), 언어 확인

2. **임베딩 가치 판단**
   - 임베딩 가치 있음: 기술 내용 포함 (에러코드, 파라미터, 조치방법, 배선도 등)
   - 임베딩 스킵: 빈 파일, 순수 카탈로그/가격표, 이미지만 있는 파일
   - 스킵 시: `data/manuals-skipped/{파일명}.txt`에 사유 기록

3. **메타데이터 추출**
   ```json
   {
     "manufacturer": "Mitsubishi",
     "model": "RH-F5",
     "doc_type": "setup_manual",
     "language": "ko",
     "pages": 250
   }
   ```

4. **파일명 리네이밍** (선택사항 — 너무 많으면 스킵)
   - 규칙: `{제조사}_{모델명}_{문서종류}_{언어}.pdf`
   - 예: `Mitsubishi_RH-F5_Setup_KO.pdf`

5. **파싱 실행** (manual-embed.py 사용)
   ```bash
   py C:/MES/wta-agents/scripts/manual-embed.py --file "파일경로"
   ```
   - 텍스트 청크 추출 + 표 Markdown 변환 + 이미지 추출
   - Qwen3-Embedding-8B 임베딩 + pgvector 저장 + Supabase Storage PDF 업로드 자동 처리

6. **진행 상황 업데이트**
   ```bash
   # manual_progress.json 업데이트 (상태: embedded)
   py C:/MES/wta-agents/scripts/update_progress.py "파일경로" embedded
   ```

### 4-3. 스킵 처리
```bash
# 스킵 기록
echo "사유: 카탈로그/가격표, 기술 내용 없음" > "C:/MES/wta-agents/data/manuals-skipped/{파일명}.txt"
# 진행 상황 업데이트
py C:/MES/wta-agents/scripts/update_progress.py "파일경로" skipped "카탈로그/가격표"
```

---

## 5. 임베딩 작업 절차 (db-manager용)

### 파싱 완료 파일 일괄 임베딩
```bash
# 특정 카테고리 전체 처리
py C:/MES/wta-agents/scripts/manual-embed.py --dir "C:/MES/wta-agents/data/manuals-filtered/4_servo"

# 단일 파일 처리
py C:/MES/wta-agents/scripts/manual-embed.py --file "파일경로"

# 강제 재처리 (변경 없어도)
py C:/MES/wta-agents/scripts/manual-embed.py --dir "경로" --force
```

### 임베딩 현황 확인
```bash
py -c "
import psycopg2
conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
  password='your-super-secret-and-long-postgres-password', dbname='postgres')
cur = conn.cursor()
cur.execute('SELECT category, COUNT(*) FROM manual.documents GROUP BY category ORDER BY count DESC')
for r in cur.fetchall(): print(r)
conn.close()
"
```

---

## 6. 진행 추적

### manual_progress.json 구조
파일 위치: `C:/MES/wta-agents/data/manual_progress.json`

```json
{
  "last_updated": "2026-03-28T06:00:00",
  "total": 949,
  "embedded": 4,
  "skipped": 0,
  "in_progress": 0,
  "pending": 945,
  "files": {
    "1_robot/597-0027-06KO.pdf": {
      "status": "embedded",
      "chunks": 160,
      "updated_at": "2026-03-28T05:53:00",
      "agent": "dev-agent"
    },
    "2_sensor/EX-10 SERIES.pdf": {
      "status": "embedded",
      "chunks": 75,
      "updated_at": "2026-03-28T05:53:00"
    }
  }
}
```

**상태값**: `pending` / `in_progress` / `embedded` / `skipped` / `error`

### 진행 상황 업데이트 스크립트
`C:/MES/wta-agents/scripts/update_progress.py` 참조

---

## 7. Supabase Storage 구조

버킷명: `vector`

```
vector/
├── pdfs/                          # 원본 PDF 파일
│   ├── CSD5-UM001C-Drive-KO.pdf
│   ├── EX-10_SERIES.pdf
│   └── ...
├── manuals/                       # 추출 이미지 (PNG)
│   ├── CSD5-UM001C-Drive-KO_p16_img0.png
│   └── ...
└── (향후) parsed/                 # 파싱 텍스트 (Markdown)
    └── CSD5-UM001C-Drive-KO.md
```

### PDF URL 접근
- 내부: `http://localhost:8000/storage/v1/object/public/vector/pdfs/{파일명}`
- 외부 (도메인 설정 후): `https://storage.cs-wta.com/storage/v1/object/public/vector/pdfs/{파일명}`
- 페이지 직접 이동: `{URL}#page={페이지번호}`

---

## 8. DB 스키마

### manual.documents
```sql
CREATE TABLE manual.documents (
  id           SERIAL PRIMARY KEY,
  source_file  TEXT NOT NULL,          -- ../manuals-filtered/4_servo/CSD5.pdf
  file_hash    TEXT NOT NULL,          -- SHA-256 앞 16자리 (변경 감지용)
  category     TEXT NOT NULL,          -- 1_robot, 2_sensor, 4_servo 등
  chunk_index  INTEGER NOT NULL,       -- 파일 내 청크 순번
  chunk_type   TEXT NOT NULL,          -- text | table | image_caption
  page_number  INTEGER,                -- 원본 PDF 페이지 번호
  content      TEXT NOT NULL,          -- 임베딩된 텍스트 내용
  image_url    TEXT DEFAULT '',        -- 이미지 청크: Supabase Storage URL
  pdf_url      TEXT DEFAULT '',        -- 원본 PDF Storage URL
  metadata     JSONB DEFAULT '{}',     -- {page, type, 기타}
  embedding    vector(1024),           -- Qwen3-Embedding-8B (2000차원, Matryoshka truncate)
  created_at   TIMESTAMPTZ,
  updated_at   TIMESTAMPTZ,
  UNIQUE (source_file, chunk_index)
);
-- HNSW 인덱스
CREATE INDEX idx_manual_docs_embedding ON manual.documents
  USING hnsw (embedding vector_cosine_ops);
```

### csagent.vector_embeddings (CS 이력)
```sql
CREATE TABLE csagent.vector_embeddings (
  id          TEXT,                    -- UUID
  source_type VARCHAR(50) NOT NULL,    -- 'cs_history'
  source_id   TEXT,                    -- cs_history.id
  text        TEXT NOT NULL,           -- "증상 및 원인: ...\n조치 결과: ..."
  metadata    JSONB,                   -- {project_name, customer, handling_method}
  embedding   vector(1024),            -- Qwen3-Embedding-8B (2000차원, Matryoshka truncate)
  created_at  TIMESTAMPTZ
);
```

---

## 9. 참고 스크립트

| 스크립트 | 용도 |
|---------|------|
| `scripts/manual-embed.py` | PDF 파싱 + 임베딩 + Storage 업로드 메인 스크립트 |
| `scripts/cs-embed.py` | CS 이력 임베딩 (csagent.cs_history → vector_embeddings) |
| `scripts/cs_rag_agent.py` | RAG 검색 서비스 (CLI + Pydantic AI Tool) |
| `scripts/manual-search.py` | 매뉴얼 벡터 검색 단독 스크립트 |
| `scripts/update_progress.py` | 진행 상황 JSON 업데이트 (생성 예정) |

### manual-embed.py 주요 옵션
```bash
py manual-embed.py                          # data/manuals/ 전체
py manual-embed.py --dir data/manuals/1_robot   # 카테고리별
py manual-embed.py --file path/to/file.pdf  # 단일 파일
py manual-embed.py --force                  # 변경 없어도 강제 재처리
py manual-embed.py --dry-run                # 추출만 (임베딩 안함)
```

---

## 10. 검색 서비스 사용법 (cs-agent)

```bash
# 통합 검색 (CS이력 + 매뉴얼)
py C:/MES/wta-agents/scripts/cs_rag_agent.py "서보 알람 조치" --json

# 매뉴얼만 검색
py C:/MES/wta-agents/scripts/cs_rag_agent.py "CSD5 게인 조정" --sources manual --json

# CS 이력만 검색
py C:/MES/wta-agents/scripts/cs_rag_agent.py "모터 과열" --sources cs_history --json
```

### 응답 구조 (CombinedSearchResult)
```json
{
  "query": "서보 알람 조치",
  "cs_history_count": 20,
  "manual_count": 20,
  "cs_history_items": [
    {
      "source_id": "4890",
      "similarity": 0.72,
      "project_name": "화루이 프레스",
      "customer": "화루이",
      "symptom_and_cause": "서보 드라이브 알람 발생",
      "action_result": "배터리 교체",
      "url": "https://cs-wta.com/cs/4890"
    }
  ],
  "manual_items": [
    {
      "source_id": "265",
      "similarity": 0.68,
      "reference": "CSD5-UM001C-Drive-KO p.265",
      "content": "서보 알람은 모터 제어를 ...",
      "page_url": "http://localhost:8000/storage/v1/.../CSD5.pdf#page=265"
    }
  ]
}
```

---

## 11. 작업 시작 체크리스트 (에이전트용)

세션 시작 시 반드시 확인:
- [ ] `cat C:/MES/wta-agents/data/manual_progress.json` — 진행 상황 확인
- [ ] Qwen3 임베딩 서버 상태: `curl -s http://182.224.6.147:11434/api/tags`
- [ ] DB 연결: `psql -h localhost -p 55432 -U postgres -d postgres -c "SELECT COUNT(*) FROM manual.documents"`
- [ ] 담당 카테고리 확인 후 미처리 파일부터 시작
- [ ] 처리 완료 파일은 즉시 `manual_progress.json` 업데이트

---

## 12. 에러 처리 가이드

| 에러 | 원인 | 조치 |
|------|------|------|
| Qwen3 임베딩 타임아웃 | 다른 에이전트 동시 사용 중 | 재시도 (--force), 배치 사이즈 축소 |
| `pdf_url` 비어있음 | SERVICE_ROLE_KEY 미설정 | `.env`에서 키 확인 |
| 텍스트 추출 0건 | 스캔 PDF (이미지만) | 스킵 처리 + 사유 기록 |
| 임베딩 차원 불일치 | Qwen3 모델 변경 | DB 재구축 필요, MAX에게 보고 |
