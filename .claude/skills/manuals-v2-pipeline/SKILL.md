---
name: manuals-v2-pipeline
description: WTA 산업 매뉴얼 1,939건 RAG+GraphRAG 파이프라인 (2026-04-11 부서장 승인 확정판). 산업 매뉴얼 / manuals-v2 / Docling / 청킹 / Qwen3 임베딩 / GraphRAG / Neo4j / pgvector / manual.documents_v2 / Qwen2.5-VL / Qwen3-Reranker / chunks.jsonl / poc / 매뉴얼 파싱 / 매뉴얼 인덱싱 / 매뉴얼 검색 / vlm_description / Supabase manual-images / qwen3.5:35b-a3b 작업 시 자동 로드. 확정판과 상충하는 기술 결정 차단.
type: project-skill
version: 1.1
created: 2026-04-12
authority: 부서장 승인 (2026-04-11), MAX 지시 (2026-04-12)
---

# manuals-v2 RAG+GraphRAG 파이프라인 (확정판 강제)

> 본 스킬은 manuals-v2 파이프라인의 **단일 진실 소스(SSOT)** 다. 메모리·기존 문서·개인 기억과 충돌 시 본 스킬을 우선한다. 위반은 즉시 중단·MAX 에스컬레이션 대상이다.

---

## 1. 자동 로드 트리거 (이 스킬 적용 시점)

다음 키워드/맥락이 등장하면 **반드시 본 스킬을 먼저 정독**:
- "manuals-v2" / "manuals_v2" / "매뉴얼 v2" / "산업 매뉴얼 파이프라인"
- "Docling 파싱" / "512 청킹" / "chunks.jsonl"
- "manual.documents_v2" / "documents_v2" / "manual-images 버킷"
- "Qwen3-Embedding-8B" / "Qwen3-Reranker-4B" / "Qwen2.5-VL-7B" / "qwen3.5:35b-a3b" 와 매뉴얼 작업 결합
- "GraphRAG" + "manuals" / "manual.graphrag" / Neo4j 매뉴얼 노드
- `reports/manuals-v2/` 경로 작업
- `workspaces/docs-agent/manuals_v2_*.py` 스크립트 작업
- `/api/graphrag/*` 엔드포인트와 manuals 결합

해당 trigger 맥락에서 본 스킬을 읽지 않고 결정하면 **확정판 위반으로 간주**한다.

---

## 2. 필수 수행 기준 (MUST — 어기면 즉시 실패)

| # | 기준 | 비고 |
|---|------|------|
| M1 | **GraphRAG는 기존 Neo4j(bolt://localhost:7688) 직접 쓰기(Cypher MERGE) 방식**만 사용 | 1,553노드 PoC에 누적 |
| M2 | **엔티티 추출 LLM은 `qwen3.5:35b-a3b`** (Ollama 182.224.6.147:11434) | 변경 금지 |
| M3 | **임베딩은 `qwen3-embedding:8b`, 2000dim MRL 슬라이싱** | 4096 → 2000 |
| M4 | **리랭커는 `Qwen3-Reranker-4B` (vLLM 로컬)** | BGE-reranker 등 대체 금지 |
| M5 | **이미지 설명은 `Qwen2.5-VL-7B` (Ollama 로컬) `vlm_description`** | 텍스트와 동일 벡터 공간 통합 |
| M6 | **벡터 저장은 `manual.documents_v2` 테이블 (vector(2000))** | 기존 manual.documents/wta_documents 보존 |
| M7 | **이미지 저장은 Supabase Storage `manual-images` 버킷** | 경로 `{category}/{file_id}/page_{N}_{figure_id}.png` + 256px 썸네일 |
| M8 | **모든 산출물 경로는 `reports/manuals-v2/` 하위**, gitignored | 부피 파일 workspaces 금지 |
| M9 | **기존 `/api/graphrag/*` 엔드포인트 + 대시보드 지식그래프 페이지(@neo4j-nvl/react) 재활용** | 별도 UI/엔드포인트 신설 금지 |
| M10 | **manuals-v2 노드는 동일 Neo4j에 라벨/속성으로 구분** (`:ManualsV2Entity` 또는 `source='manuals_v2'`) | 별도 Neo4j 인스턴스 금지 |
| M11 | **청킹은 HierarchicalChunker 512 토큰 + 64 오버랩** | 1024로 회귀 금지 |
| M12 | **파서는 Docling 메인, MinerU 폴백(CJK)**, `generate_picture_images=True, images_scale=2.0` | OCR EasyOCR |
| M13 | **체크포인트(state.json) + 로그(.log) 2-파일 구조 의무**, 재개 가능 | 장시간 작업 필수 |
| M14 | **확정판과 어긋나는 기술 결정은 MAX 에스컬레이션 후 부서장 승인 필수** | 단독 변경 금지 |
| M15 | 보고는 **Cloudflare URL** (`https://agent.mes-wta.com/...`) + **3줄 요약** | 로컬 경로 보고 금지 |
| M16 | **GraphRAG 윈도우는 800자 + 200자 오버랩 슬라이딩**. 2,000자 단일 트런케이션 금지. | PoC 비교 결과 800자 다회 방식 월등 (v1.1) |
| M17 | **엔티티 추출 프롬프트는 §5B-4 MANUALS_V2_EXTRACT_PROMPT 사용**. cm-graphrag 프롬프트 사용 금지. | 매뉴얼 구조 관계 추출 불가 (v1.1) |
| M18 | **엔티티 12종 / 관계 12종 온톨로지(§5B-2)** 외 타입은 무시. 임의 타입 추가 금지. | 교차검증 재현성 확보 (v1.1) |
| M19 | **Neo4j 라벨은 `:ManualsV2Entity:{Type}`** 단일. 팀별/PoC별 전용 라벨 금지. `_run_id`/`_team` 속성으로 구분. | v1.1 §5B-1 |
| M20 | **LLM 호출 파라미터는 §5B-5 LLM_PARAMS 통일**. num_predict=4096, temperature=0, think=False. | 교차검증 재현성 (v1.1) |

---

## 3. 금지 사항 (MUST NOT)

| # | 금지 | 사유 |
|---|------|------|
| N1 | **LightRAG 라이브러리 사용 금지** (`from lightrag import LightRAG` 등) | 확정판 명시 — 미도입 |
| N2 | **별도 Neo4j 인스턴스/포트 신설 금지** | bolt://localhost:7688 단일화 |
| N3 | **`workspaces/{agent}/` 하위에 로그·체크포인트·청크 덤프·캐시 등 부피 파일 생성 금지** | git 용량, 부서장 정정 2026-04-12 |
| N4 | **OpenAI / Anthropic API를 엔티티 추출/임베딩/리랭킹에 사용 금지** | 모두 로컬 모델로 결정됨 |
| N5 | **Sonnet/Opus/Haiku를 LightRAG 또는 GraphRAG LLM으로 사용 금지** | qwen3.5:35b-a3b 단일 |
| N6 | **`manual.documents` / `manual.wta_documents` 테이블 수정·삭제 금지** | 보존 |
| N7 | **확정판 미대조 상태에서의 기술 결정 금지** — 본 스킬 / `memory/project_manuals_v2_pipeline.md` 직접 읽기 의무 | 재발 방지 |
| N8 | **PGPASSWORD 등 비밀 명령행 직접 입력 금지** | 글로벌 보안 룰 |
| N9 | **Step 3 청크 재처리는 일상 운영 실행 금지** — 알고리즘/모델 변경 시에만 | Step 2 산출물을 그대로 사용 |
| N10 | **dashboard/app.py, scripts/mcp-*.ts, jobs.json, start/stop-agents.bat 수정 금지** | 시스템 영역, MAX 전용 |
| N11 | **팀별 전용 Neo4j 라벨 생성 금지** (ManualsV2_PoC10_ISSUE, ManualsV2_PoC_xxx 등) | `:ManualsV2Entity` 단일 + 속성 (v1.1) |
| N12 | **cm-graphrag EXTRACT_PROMPT를 매뉴얼 GraphRAG에 사용 금지** | CS이력 기반으로 매뉴얼 부적합 (v1.1) |
| N13 | **2,000자 이상 단일 트런케이션 방식 금지** | 관계 추출 실패 (v1.1) |

---

## 4. 단계별 체크리스트 (Step 0 ~ Step 7)

> 모든 명령은 다음 환경변수 가정. 비밀은 환경변수에서만 읽는다.
> ```bash
> PY="/c/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
> ```

### Step 0 — 문서 수집 (원본 PDF)
- [ ] 카테고리 8종 풀 확보: `1_robot 2_sensor 3_hmi 4_servo 5_inverter 6_plc 7_pneumatic 8_etc`
- 담당: docs-agent
- 출력: 카테고리별 PDF 풀

### Step 1 — 분류 + 메타데이터 추출
- [ ] 7/8 카테고리 완료, 8_etc 잔여
- 담당: docs-agent
- 스크립트: `workspaces/docs-agent/manuals_v2_step1_extract.py`, 배치 러너 `manuals_v2_pipeline.py`
- 출력: `workspaces/docs-agent/manuals_v2_{N}_{category}_extract.jsonl` + `_classification.csv` + `_extract.ckpt`
```bash
cd "C:/MES/wta-agents/workspaces/docs-agent"
"$PY" manuals_v2_pipeline.py 8_etc       # 잔여
"$PY" manuals_v2_pipeline.py all         # 전체 재실행 (체크포인트 이어감)
```

### Step 2 — Docling 파싱 + 512 청킹
- [ ] 5/693 진행 중
- 담당: docs-agent
- 스크립트: `workspaces/docs-agent/manuals_v2_step2_parse.py` → `manuals_v2_parse_docling.py`
- 입력: Step 1 `_extract.jsonl`
- 출력:
  - `reports/manuals-v2/poc/{file_id}/document.json`
  - `reports/manuals-v2/poc/{file_id}/chunks.jsonl`
  - `reports/manuals-v2/poc/{file_id}/images/*.png` (Docling `generate_picture_images=True, images_scale=2.0`)
- 상태/로그: `reports/manuals-v2/state/manuals_v2_step2_state.json` / `manuals_v2_step2.log`
- 청킹: HierarchicalChunker 512+64
- 이미지 처리: Docling picture → Qwen2.5-VL-7B `vlm_description` 생성 → chunks.jsonl `figures[].vlm_description`에 보존
```bash
cd "C:/MES/wta-agents/workspaces/docs-agent"
"$PY" manuals_v2_step2_parse.py            # 이어서
"$PY" manuals_v2_step2_parse.py 1_robot    # 카테고리 한정
```

### Step 3 — 청크 후처리(병합/정규화) **PoC 한정**
- [ ] PoC 10건 완료 (2026-04-12 07:46~08:13). 8,879 → 6,173 청크. embed_failed=0
- **일상 운영 시 실행 금지** (N9). 알고리즘/임베딩 모델 변경 시에만 재실행.
- 담당: crafter (PoC) → issue-manager (인계 후)
- 스크립트: `workspaces/docs-agent/manuals_v2_reprocess.py` + `chunk_postprocess.py`
- 입력: `reports/manuals-v2/poc/{file_id}/chunks.jsonl`
- 출력: 같은 파일 덮어쓰기, `chunks.jsonl.bak` 자동 백업
- 로그/체크포인트: `reports/manuals-v2/legacy/manuals_v2_reprocess.log` / `manuals_v2_reprocess_state.json`
```bash
cd "C:/MES/wta-agents/workspaces/docs-agent"
"$PY" manuals_v2_reprocess.py                                      # PoC 전체
"$PY" manuals_v2_reprocess.py 1_robot_0b0c3108c6c9                # 단일
REPROCESS_SKIP_EMBED=1 "$PY" manuals_v2_reprocess.py 1_robot_*    # 청크만(검증)
```

### Step 4 — 임베딩 (Qwen3-Embedding-8B / 2000dim)
- [ ] 모델: `qwen3-embedding:8b`
- [ ] 엔드포인트: `http://182.224.6.147:11434/api/embed`
- [ ] dim: **EMBED_DIM=2000** (4096 → 2000 MRL 슬라이싱)
- 정상 운영: db-manager 적재 스크립트가 처리. 재처리: Step 3 스크립트가 처리.

### Step 5A — pgvector 적재 (`manual.documents_v2`)
- 담당: db-manager
- 스키마:
  ```sql
  CREATE TABLE manual.documents_v2 (
    id BIGSERIAL PRIMARY KEY,
    file_id TEXT,
    chunk_id TEXT,
    category TEXT,
    mfr TEXT,
    model TEXT,
    doctype TEXT,
    lang TEXT,
    section_path JSONB,
    page_start INT,
    page_end INT,
    content TEXT,
    embedding vector(2000),
    figure_refs JSONB,
    table_refs JSONB,
    inline_refs JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
  );
  ```
- 보존: `manual.documents` (218k), `manual.wta_documents` (67k)
- 적재 idempotent (UPSERT by `(file_id, chunk_id)`)
- 하이브리드 검색: BM25(pg_bm25 또는 앱 레벨 rank_bm25) + Dense RRF → **Qwen3-Reranker-4B** 후단

### Step 5B — GraphRAG 적재 (Neo4j 직접, **LightRAG 미도입**)
- 담당: docs-agent (엔티티 추출 트리거) + crafter (인프라 보조)
- Neo4j: bolt://localhost:7688 (기존)
- 엔티티 추출 LLM: `qwen3.5:35b-a3b` (Ollama 182.224.6.147:11434)
- 재활용: `dashboard/app.py` `/api/graphrag/*` (nodes/labels/search/expand/cypher) + 대시보드 지식그래프 페이지
- 참조 구현: `workspaces/research-agent/poc-index.py` (Ollama 호출 구조만 — **LightRAG import 추가 금지**)

#### 5B-1. Neo4j 라벨 규칙 (필수 — v1.1 확정)
모든 manuals-v2 노드는 **라벨 2개 + 속성 3개**로 반드시 구분:
- 라벨: `:ManualsV2Entity:{EntityType}` (예: `:ManualsV2Entity:Equipment`)
- 속성:
  - `source = 'manuals_v2'` (불변, 전체 corpus 식별)
  - `_run_id = 'run-YYYYMMDD-HHMMSS'` (실행 회차 구분, PoC/정식 구분에 사용)
  - `_file_id = '{file_id}'` (원본 파일 추적)
- **PoC 전용 라벨 금지**: `ManualsV2_PoC10_ISSUE`, `ManualsV2_PoC10_QA` 같은 팀별 라벨 사용하지 않음. `_run_id`와 `_team` 속성으로 구분.
- Cypher 패턴:
  ```cypher
  MERGE (n:ManualsV2Entity:{type} {_id: $id})
  SET n += $props, n.name = $name, n.source = 'manuals_v2',
      n._run_id = $run_id, n._file_id = $file_id, n._team = $team
  ```

#### 5B-2. 엔티티/관계 온톨로지 (필수 — v1.1 확정)

**엔티티 12종** (이 목록 외 타입은 LLM이 반환해도 무시):
| 타입 | 설명 | 예시 |
|------|------|------|
| `Equipment` | 장비/기기 | 로봇, 인버터, 서보드라이브, 센서 |
| `Component` | 부품/구성요소 | 모터, 엔코더, 퓨즈, 커넥터(CN5) |
| `Parameter` | 파라미터/설정값 코드 | C1-01, H4-02, Pr.7 |
| `Alarm` | 알람/에러코드 | oC, AL.16, E401 |
| `Process` | 절차/작업/공정 | 배선, 설치, 점검, 튜닝, 초기화 |
| `Section` | 문서 섹션/챕터 제목 | "제3장 배선", "5.2 파라미터 설정" |
| `Figure` | 그림/다이어그램 | 배선도, 회로도, 외형도 |
| `Table` | 표 | 파라미터 표, 사양 표, 알람 일람표 |
| `Diagram` | 도식/블록도 | 제어 블록도, 시퀀스 다이어그램 |
| `Specification` | 사양/규격 수치 | 정격전압 200V, 최대토크 47Nm |
| `Manual` | 매뉴얼 문서 자체 | YASKAWA V1000 사용설명서 |
| `SafetyRule` | 안전규정/경고 | "전원 차단 후 5분 대기", "접지 필수" |

**관계 12종** (이 목록 외 타입은 무시):
| 타입 | 방향 | 설명 |
|------|------|------|
| `PART_OF` | Component → Equipment | 부품이 장비에 속함 |
| `HAS_PARAMETER` | Equipment → Parameter | 장비가 파라미터를 가짐 |
| `SPECIFIES` | Specification → Equipment/Component | 사양이 장비/부품을 규정 |
| `CAUSES` | Alarm → Process | 알람 발생 시 복구 절차 유발 |
| `RESOLVES` | Process → Alarm | 절차가 알람을 해결 |
| `CONNECTS_TO` | Equipment ↔ Component | 장비-부품 간 물리 연결 |
| `REQUIRES` | Process → Component/Equipment | 절차에 필요한 장비/부품 |
| `BELONGS_TO` | Figure/Table → Section | 그림/표가 섹션에 속함 |
| `REFERENCES` | Section → Figure/Table | 섹션이 그림/표를 참조 |
| `DEPICTS` | Figure → Equipment/Component | 그림이 장비/부품을 도식 |
| `DOCUMENTS` | Manual → Equipment/Process | 매뉴얼이 장비/절차를 기술 |
| `WARNS` | SafetyRule → Process/Equipment | 안전규정이 절차/장비에 적용 |

#### 5B-3. 텍스트 윈도우 규격 (필수 — v1.1 확정)
- **윈도우 크기**: **800자** (PoC 비교 결과: 800자 다회 호출이 2,000자 단일 대비 관계 추출률 월등. docs-agent 평가 확인)
- **오버랩**: **200자** (엔티티가 윈도우 경계에 걸리는 것 방지)
- **슬라이딩 방식**: 청크를 순서대로 concat → 800자마다 잘라 윈도우 생성. 마지막 윈도우가 300자 미만이면 직전 윈도우에 병합.
- **구분자**: `\n\n` (청크 간 더블 뉴라인)
- **최소 텍스트 길이**: 50자 미만 윈도우는 LLM 호출 스킵
- 구현 패턴 (Python):
  ```python
  WINDOW_SIZE = 800
  WINDOW_OVERLAP = 200
  MIN_WINDOW_LEN = 50

  def build_windows(chunks: list[dict]) -> list[dict]:
      full_text_parts = []
      chunk_map = []  # (start_pos, chunk_id)
      pos = 0
      for ch in chunks:
          content = (ch.get('content') or '').strip()
          if not content:
              continue
          chunk_map.append((pos, ch.get('chunk_id', '')))
          full_text_parts.append(content)
          pos += len(content) + 2  # \n\n separator
      full_text = '\n\n'.join(full_text_parts)

      windows = []
      start = 0
      while start < len(full_text):
          end = start + WINDOW_SIZE
          win_text = full_text[start:end]
          if len(win_text) < MIN_WINDOW_LEN:
              break
          # 마지막 윈도우가 300자 미만이면 현재에 병합
          remaining = len(full_text) - end
          if 0 < remaining < 300:
              win_text = full_text[start:end + remaining]
              end = len(full_text)
          # 해당 윈도우에 걸리는 chunk_id 수집
          cids = [cid for (p, cid) in chunk_map
                  if p < end and p + 100 > start]  # 대략적 매핑
          windows.append({
              'idx': len(windows),
              'text': win_text,
              'chunk_ids': cids,
          })
          start = end - WINDOW_OVERLAP
      return windows
  ```

#### 5B-4. 엔티티 추출 프롬프트 (필수 — v1.1 확정, cm-graphrag 프롬프트 대체)
```
MANUALS_V2_EXTRACT_PROMPT = """다음 산업 장비 매뉴얼 텍스트에서 엔티티와 관계를 추출하세요.

## 엔티티 타입 (12종)
- Equipment: 장비/기기 (로봇, 인버터, 서보, 센서, PLC 등)
- Component: 부품/구성요소 (모터, 엔코더, 퓨즈, 커넥터, 단자대 등)
- Parameter: 파라미터/설정값 코드 (C1-01, H4-02, Pr.7 등 코드 반드시 포함)
- Alarm: 알람/에러코드 (oC, AL.16, E401, OV 등 코드 반드시 포함)
- Process: 절차/작업/공정 (배선, 설치, 점검, 튜닝, 초기화, 교체 등)
- Section: 문서 섹션/챕터 (제목 단위)
- Figure: 그림/다이어그램 (배선도, 회로도, 외형도 등)
- Table: 표 (파라미터 표, 사양 표, 알람 일람표 등)
- Diagram: 도식/블록도 (제어 블록도, 시퀀스 다이어그램 등)
- Specification: 사양/규격 수치 (정격전압 200V, 최대토크 47Nm 등)
- Manual: 매뉴얼 문서 자체
- SafetyRule: 안전규정/경고 ("전원 차단 후 5분 대기" 등)

## 관계 타입 (12종)
- PART_OF: Component가 Equipment의 부품 (예: 엔코더 → 서보모터)
- HAS_PARAMETER: Equipment가 Parameter를 가짐 (예: 인버터 → C1-01)
- SPECIFIES: Specification이 Equipment/Component를 규정 (예: 정격전압 → 인버터)
- CAUSES: Alarm 발생 시 Process 유발 (예: oC 알람 → 냉각 점검)
- RESOLVES: Process가 Alarm을 해결 (예: 냉각팬 교체 → oC 해소)
- CONNECTS_TO: Equipment/Component 간 물리적 연결 (예: 엔코더 → CN5 커넥터)
- REQUIRES: Process에 필요한 Equipment/Component (예: 배선작업 → 압착단자)
- BELONGS_TO: Figure/Table이 Section에 속함 (예: 그림3-1 → 제3장)
- REFERENCES: Section이 Figure/Table을 참조 (예: "그림 3-1 참조")
- DEPICTS: Figure가 Equipment/Component를 도식 (예: 배선도 → 서보드라이브)
- DOCUMENTS: Manual이 Equipment/Process를 기술
- WARNS: SafetyRule이 Process/Equipment에 적용 (예: "접지 필수" → 설치작업)

## 추출 규칙
1. 엔티티 id는 영문 snake_case (예: yaskawa_v1000, param_c1_01, alarm_oc)
2. name은 원문 표기 그대로 (한국어/영어/일어)
3. properties에 model, mfr(제조사), unit(단위), code(코드) 등 있으면 포함
4. 관계는 반드시 추출된 엔티티 id 사이에서만 생성
5. 텍스트에 명시적 근거가 없는 관계는 생성하지 않음
6. 엔티티가 0개여도 빈 배열로 응답, 에러 메시지 금지

## 응답 형식 (JSON만, 다른 텍스트 없이)
{
  "entities": [
    {"id": "eng_snake_case", "name": "표시명", "type": "Equipment", "properties": {"model": "V1000", "mfr": "Yaskawa"}}
  ],
  "relations": [
    {"source": "entity_id1", "target": "entity_id2", "type": "HAS_PARAMETER"}
  ]
}

텍스트:
"""
```

#### 5B-5. LLM 호출 파라미터 (필수 — v1.1 확정)
모든 팀이 동일한 파라미터 사용:
```python
LLM_PARAMS = {
    "model": "qwen3.5:35b-a3b",
    "stream": False,
    "think": False,
    "options": {
        "num_predict": 4096,
        "temperature": 0,
    },
}
# timeout: 300초
# endpoint: http://182.224.6.147:11434/api/generate
```

#### 5B-6. JSON 파싱 규칙
1. 응답에서 ````json ... ```  ` 코드블록 제거 후 파싱
2. 첫 번째 `{ ... }` 매칭 (`re.search(r'\{.*\}', raw, re.DOTALL)`)
3. JSON 파싱 실패(절단) 시 → 정규식으로 entities만 부분 파싱, relations=[]
4. 엔티티 type이 12종에 없으면 무시
5. 관계 type이 12종에 없으면 무시
6. source/target id가 현재 윈도우 추출 결과에 없으면 관계 무시

### Step 5 부속 — 이미지 적재
- Docling PNG → Supabase `manual-images` 버킷 업로드
- 경로: `{category}/{file_id}/page_{N}_{figure_id}.png` + 256px 썸네일

### Step 6 — 검증
- 담당: qa-agent (검증 전용, 적재는 하지 않음)
- docs-agent: 평가만 수행 (적재/코드 수정 금지)
- 표준: 필터 표준 v1.0 (출처 / 페이지 / 이미지 ref / 언어 / 카테고리 일치)
- 산출물: `reports/manuals-v2-qa-before.html`, `reports/manuals-v2-qa-after.html` + 지표 표
- 이상치 발견 시: docs-agent 피드백 → Step 2 또는 Step 3 재실행

#### Step 6 부속 — MRR 쿼리셋 표준 (v1.1 확정)
- **최소 쿼리 수**: 카테고리별 10건, 총 최소 30건 (PoC는 대상 file_id 수 × 3건)
- **쿼리 생성 방법**:
  1. 자동: 각 file_id의 상위 10% 청크에서 첫 문장 추출 → 쿼리화 (예: "V1000 인버터 C1-01 파라미터 설정 방법")
  2. 수동: 카테고리별 핵심 쿼리 5건 (장비명+작업, 알람코드+조치, 파라미터+설정값, 배선도+커넥터, 사양+수치)
- **평가 지표**: MRR@5, Hit@5, Precision@5
- **Ground Truth**: 쿼리별 정답 chunk_id 최소 1개 지정 (자동 생성 쿼리는 원본 청크가 정답)
- **쿼리셋 저장**: `reports/manuals-v2/eval/mrr_queryset_v1.jsonl` (JSONL, 필드: query, category, file_id, answer_chunk_ids[])
- **보고서 스키마**: `reports/manuals-v2/eval/mrr_report_v1.json` (필드: run_id, team, queryset_version, results[{query, mrr, hit, retrieved_ids}], summary{avg_mrr, avg_hit, avg_precision})

### Step 7 — 보고
- 담당: issue-manager (PoC 인계 후) / docs-agent (정상 운영)
- HTML: `reports/manuals-v2/manuals-v2-graphrag-*.html`
- 공유: `dashboard/uploads/` 업로드 → Cloudflare URL 생성
- 보고: MAX 경유, **본문 3줄 요약 + URL** (M15)

---

## 5. 역할 분담 매트릭스

| 역할 | 담당 에이전트 |
|------|--------------|
| 메인 (분류/파싱/청킹/PoC/품질) | **docs-agent** |
| 스키마/적재/인덱스 | **db-manager** |
| 인프라 보조 / Step 3 PoC | **crafter** |
| Ollama 모델 풀/관리 | **admin-agent** |
| 검증(QA) | **qa-agent** |
| 인수 후 GraphRAG 트래킹 (PoC 종료 후) | **issue-manager** |
| 조정/위임/에스컬레이션 | **MAX** |

---

## 6. 체크포인트 / 로그 의무 규격

| 단계 | state.json 경로 | log 경로 |
|------|----------------|----------|
| Step 1 | `workspaces/docs-agent/manuals_v2_{cat}_extract.ckpt` | (스크립트 stdout) |
| Step 2 | `reports/manuals-v2/state/manuals_v2_step2_state.json` | `reports/manuals-v2/state/manuals_v2_step2.log` |
| Step 3 | `reports/manuals-v2/legacy/manuals_v2_reprocess_state.json` | `reports/manuals-v2/legacy/manuals_v2_reprocess.log` |
| Step 5A 적재 | `reports/manuals-v2/state/documents_v2_load_state.json` | `reports/manuals-v2/state/documents_v2_load.log` |
| Step 5B GraphRAG | `reports/manuals-v2/state/graphrag_index_state.json` | `reports/manuals-v2/state/graphrag_index.log` |

state.json 최소 필드: `task_id`, `status`, `total`, `completed`, `current`, `items[]`, `last_update` (KST ISO).

---

## 7. 에스컬레이션

| 상황 | 1차 |
|------|-----|
| 청크 알고리즘/토크나이저 의문 | docs-agent |
| Postgres 적재/스키마 | db-manager |
| Neo4j 컨테이너/포트/볼륨 | admin-agent |
| Ollama 모델 풀/응답 | admin-agent |
| 임베딩 서버(182.224.6.147) 응답 없음 | admin-agent |
| 대시보드 `/api/graphrag/*` 변경 필요 | **MAX → crafter** |
| Phase 2 전체 적재 가/부 판단 | **MAX → 부서장** |
| 확정판과 어긋나는 기술 결정 검토 | **MAX 필수** |

---

## 8. FAQ

### Q1. LightRAG 안 쓰는 이유?
A. 2026-04-11 부서장 승인 확정판에서 **명시적으로 미도입** 결정. 기존 Neo4j(7688) + `/api/graphrag/*` + 대시보드 지식그래프 페이지(@neo4j-nvl/react, 1,553노드 PoC)가 이미 운영 중이라 그대로 확장한다. LightRAG 추가는 중복 인프라.

### Q2. 다른 임베딩(BGE-M3 등) 써도 되나?
A. 안 됨. M3 위반. Qwen3-Embedding-8B 2000dim 단일.

### Q3. 다른 리랭커(BGE-reranker-v2-m3)는?
A. 안 됨. M4 위반. 확정판은 Qwen3-Reranker-4B (BEIR +8.77, 패밀리 일관성 사유).

### Q4. 엔티티 추출에 Sonnet/Opus를 써도 되나? (예산 핑계 포함)
A. 안 됨. M2/N5 위반. `qwen3.5:35b-a3b` Ollama 로컬 단일. 로컬 모델 정책.

### Q5. 청크 크기를 1024로 늘려도 되나? (RAG 성능 핑계)
A. 안 됨. M11 위반. 512+64 확정. 변경하려면 부서장 승인.

### Q6. workspaces/docs-agent/v2_poc/ 와 reports/manuals-v2/poc/ 중 어디가 진짜?
A. **`reports/manuals-v2/poc/`** 가 진짜. 2026-04-12 정정 시점에 reports/로 이관 + `manuals_v2_parse_docling.py` `WORK_ROOT` 및 `manuals_v2_reprocess.py` `WORK_ROOT` 모두 reports 기준으로 통일.

### Q7. Step 3 청크 재처리를 신규 카테고리에도 돌려야 하나?
A. 아니오. **PoC 검증 한정**. 일상 운영(Step 2 → Step 4 → Step 5A/B) 흐름에서는 Step 3 스킵. 청킹 알고리즘 또는 임베딩 모델/차원이 바뀐 경우에만 재실행.

### Q8. Neo4j 컨테이너를 직접 재시작해도 되나?
A. 안 됨. 시스템 영역 → admin-agent에 위임 (`send_message(to="admin-agent", msg_type="request", ...)`).

### Q9. manual.documents_v2 인덱스는 어떻게 만드나?
A. db-manager 담당. 일반적으로 `embedding`에 IVFFlat 또는 HNSW (pgvector). `(file_id, chunk_id)` UNIQUE, `category`, `lang` BTREE. 본 스킬 작성 시점에는 미생성 상태일 수 있음 — db-manager에 확인 후 생성 요청.

### Q10. manuals-v2 노드와 기존 PoC(1,553노드)가 섞이지 않게 하려면?
A. §5B-1 라벨 규칙 준수: `:ManualsV2Entity:{Type}` (예: `:ManualsV2Entity:Equipment`). 속성 `_run_id`, `_team`, `_file_id`로 필터링. Cypher 예:
```cypher
MERGE (e:ManualsV2Entity:Equipment {_id: $id})
  ON CREATE SET e.name=$name, e._file_id=$file_id, e._run_id=$run_id, e._team=$team
```

### Q11. 임베딩 서버 다운 시?
A. Step 3 스크립트는 `REPROCESS_SKIP_EMBED=1`로 청크 후처리만 우선 종료. 정상 운영 적재는 db-manager가 batch 재시도. 외부 GPU(182.224.6.147)이므로 본인 권한 없음 → admin-agent 위임.

### Q12. 검색 API 신설해도 되나?
A. 기존 `/api/graphrag/*` (search/expand/cypher) 재활용이 원칙(M9). 신규 엔드포인트가 꼭 필요하면 MAX 승인 후 crafter가 추가.

---

## 9. 2026-04-11 확정판 원문 (인용, 변경 금지)

> 출처: `C:/Users/Administrator/.claude/projects/C--MES-wta-agents/memory/project_manuals_v2_pipeline.md`

```
**manuals-v2 파이프라인 확정 (2026-04-11)**

**Why**: 기존 manual.documents 218k 청킹/분류 품질 재검토. 부서장 핵심 우려 — 본문-이미지 관계성 보존. 리서치 결과 3가지 개선 반영.

**How to apply**: 파싱/임베딩/검색 관련 제안 시 이 파이프라인 기준으로 조언. 변경 시 여기 업데이트.

### 파이프라인 구성
- 파서: Docling (메인) + MinerU 폴백 (CJK). generate_picture_images=True, images_scale=2.0
- OCR: Docling 내장 EasyOCR, DOCX는 Docling DOCX 모드
- 청킹: 512 토큰 + 64 오버랩 (기존 1024 → 하향). HierarchicalChunker, 섹션/페이지 경계 준수, 표/코드 단일 청크 분리
- 임베딩: Qwen3-Embedding-8B, 2000dim MRL 슬라이싱, 로컬 Ollama 182.224.6.147:11434
- 리랭커: Qwen3-Reranker-4B (vLLM 로컬) — BGE-reranker-v2-m3 대신 (BEIR +8.77점, Qwen 패밀리 일관성)
- GraphRAG: 기존 Neo4j(bolt://localhost:7688) 직접 방식 유지 + qwen3.5:35b-a3b 로컬 엔티티 추출. LightRAG 미도입 — 이미 대시보드 지식그래프 페이지(@neo4j-nvl/react)와 /api/graphrag/* 엔드포인트가 구축되어 있어(1,553노드 PoC) 그대로 확장한다. manuals-v2 노드는 동일 Neo4j에 누적.
- 이미지 처리: Docling picture 노드 → Qwen2.5-VL-7B 로컬로 vlm_description 생성 → 텍스트와 동일 벡터 공간 통합 인덱싱
- 이미지 저장: Supabase Storage manual-images 버킷, {category}/{file_id}/page_{N}_{figure_id}.png + 썸네일 256px

### 저장 테이블: manual.documents_v2
id, file_id, chunk_id, category, mfr, model, doctype, lang,
section_path JSONB, page_start, page_end,
content, embedding vector(2000),
figure_refs JSONB, table_refs JSONB, inline_refs JSONB,
created_at

기존 manual.documents (218k) / manual.wta_documents (67k) 는 보존.

### 하이브리드 검색
- BM25 (pg_bm25 확장 또는 앱 레벨 rank_bm25) + Dense RRF → Qwen3-Reranker-4B 후단 재순위화

### GraphRAG 노드 타입
- 기본 + Figure/Table/Diagram 별도 엔티티
- (Figure)-[:BELONGS_TO]->(Section), (Chunk)-[:REFERENCES]->(Figure), (Figure)-[:DEPICTS]->(Component)

### 2차 확장 (차후 검토)
- ColQwen2 페이지 multi-vector (pgvector multi-vector 지원 확인 후)
- Jina-CLIP-v2 보조

### 실행 순서
1. db-manager — manual.documents_v2 + Supabase manual-images 버킷 생성
2. admin-agent — Qwen2.5-VL-7B Ollama pull
3. crafter/docs-agent — Qwen3-Reranker-4B vLLM 환경
4. docs-agent — batch-parse-docling.py 수정 (이미지 export + 청킹 512)
5. 1_robot 샘플 3건 PoC → 검증 → 1_robot 전체 → 나머지 카테고리 확장

### 주관 에이전트
- docs-agent (메인): 분류, 파싱, 청킹, PoC, 품질 검증
- db-manager: 스키마/적재/인덱스
- crafter (보조): 필요 시 인프라 지원
- admin-agent: Ollama 모델 관리
```

---

## 10. 변경 절차

본 스킬과 확정판을 변경하려면:
1. MAX에게 사유 + 대체안 보고 (`msg_type="report_blocked"` 또는 `request`)
2. MAX → 부서장 승인 획득
3. 승인 후 **본 스킬 + memory/project_manuals_v2_pipeline.md 동시 업데이트**
4. version 필드 증가, 변경 이력 본 섹션 하단에 append

### 변경 이력
- v1.0 (2026-04-12) — 초안 작성. 부서장 정정/MAX 지시 반영. LightRAG 미도입 명시.
- v1.1 (2026-04-12) — PoC 비교 결과 반영. §5B-1~6 신설: 라벨 규칙, 엔티티/관계 온톨로지 12/12종, 윈도우 800자+200 오버랩, 전용 EXTRACT_PROMPT, LLM 파라미터 통일, JSON 파싱 규칙, MRR 쿼리셋 표준. M16~M20/N11~N13 추가. docs-agent 평가 피드백 기반.
