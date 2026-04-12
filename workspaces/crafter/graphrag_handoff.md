# manuals-v2 / GraphRAG 인수인계서 (crafter → issue-manager)

- 작성: 2026-04-12 KST, crafter
- 사유: crafter가 부서장과 별건 다수 처리 → GraphRAG 완료 시점까지 issue-manager가 단독 운영
- 인수 완료 조건: issue-manager가 본 문서 정독 후 "착수 가능" 사인

---

## 0. 한 줄 요약
manuals-v2 PoC 10건 재처리(청크 후처리 + Qwen3 임베딩 재생성)는 2026-04-12 07:46~08:13 KST 완료. 8,879→6,173 청크. embed_failed=0. 다음 단계는 GraphRAG(LightRAG/Neo4j) 인덱싱 → 검색 비교 → 부서장 보고. 인프라 변경 없음.

> 주: MAX 지시문에는 "08:25~26 재파싱"이라 기재됐으나 실제 로그상 재파싱 종료 시각은 08:13:36 KST 입니다(`reports/manuals-v2/legacy/manuals_v2_reprocess.log`). 시각 차이는 메모 오기 추정.

---

## 1. crafter가 담당했던 범위
| 영역 | 산출물 위치 |
|------|------------|
| 청크 후처리 + 재임베딩 스크립트 | `workspaces/docs-agent/manuals_v2_reprocess.py` |
| 청크 분할 알고리즘 | `workspaces/docs-agent/chunk_postprocess.py` (Qwen3 토크나이저 기반, target 150~300 tokens) |
| 재처리 PoC 10건 실행 로그 | `reports/manuals-v2/legacy/manuals_v2_reprocess.log` |
| 재처리 체크포인트 | `reports/manuals-v2/legacy/manuals_v2_reprocess_state.json` |
| 청크 통계 스냅샷 | `reports/manuals-v2/legacy/chunk_postprocess_batch_*.json` (10건 + summary) |
| QA 페이지(Before/After) | `reports/manuals-v2-qa-before.html`, `reports/manuals-v2-qa-after.html` |
| Qwen3-Embedding-8B 인프라 | http://182.224.6.147:11434 (외부 GPU, 별도 운영, 본인 변경 권한 없음) |
| pgvector 스키마 통일 | manual.documents / manual.wta_documents / csagent.vector_embeddings 모두 2000차원 |
| MCP agent-channel msg_type 개선 | `scripts/mcp-agent-channel.ts` + `dashboard/app.py` (8/8 항목 점검 완료, MAX 보고됨) |
| LightRAG/Neo4j 인덱싱 | **미착수** — issue-manager 인수 후 진행 |

본 인수인계 대상: **재처리(완료) + LightRAG/Neo4j(미착수)** 두 블록.

---

## 2. 진행 중 / 대기 중 작업 목록
| # | 상태 | 작업 | 비고 |
|---|------|------|------|
| 1 | 완료 | PoC 10건 재처리(청크 후처리 + 임베딩) | state.json status=done |
| 2 | 대기 | LightRAG로 PoC 10건 그래프 인덱싱 | research-agent의 `poc-index.py` 패턴 참고 |
| 3 | 대기 | Neo4j 적재 결과 검증(노드/엣지 카운트, 샘플 쿼리) | bolt://localhost:7688 |
| 4 | 대기 | 하이브리드 검색 비교(벡터 only vs LightRAG) | 대시보드 비교 페이지 기존 구현 활용 |
| 5 | 대기 | manuals-v2 GraphRAG 결과 보고서 작성 | reports/manuals-v2/ 하위 HTML, Cloudflare URL로 보고 |
| 6 | 대기 | 부서장 최종 승인 후 본격 적재(전체 manuals-v2) | Phase 2, 완화책 확정 후 |

부서장 지시(2026-04-11): **1단계는 즉시, 2단계는 완화책 확정 후 진행**(memory: feedback_graphrag_reporting.md).

---

## 3. 작업공간 경계 (반드시 준수)

### 3.1 핵심 규칙 — 경로 정책 (2026-04-12 부서장 지시)
**용량 사유**: `workspaces/`는 git 커밋 대상이라 부피 파일이 쌓이면 저장소가 비대해진다. 따라서:

| 종류 | 위치 | git |
|------|------|-----|
| `.py` 스크립트 (실행 가능 코드) | `workspaces/{agent}/` | 커밋 |
| 로그 / 체크포인트 / 상태파일 | `reports/manuals-v2/legacy/` | gitignored |
| 청크 통계/덤프/캐시/중간 산출물 | `reports/manuals-v2/legacy/` 또는 `reports/manuals-v2/` | gitignored |
| 부서장 보고용 HTML | `reports/manuals-v2/` | gitignored |
| 이슈 트래킹/분석/리포트(issue-manager 자체 산출물) | `reports/manuals-v2/` | gitignored |

**금지**: workspaces/{agent}/에 로그·JSON 덤프·캐시 생성 금지. 신규 산출물은 무조건 `reports/manuals-v2/` 하위.

### 3.2 기존 파일 — 이미 정리 완료 (crafter, 2026-04-12)
crafter가 본 문서 작성 시점에 다음을 이동:
- `workspaces/crafter/manuals_v2_reprocess.log` → `reports/manuals-v2/legacy/`
- `workspaces/crafter/manuals_v2_reprocess_state.json` → `reports/manuals-v2/legacy/`
- `workspaces/crafter/chunk_postprocess_batch_*.json` (10건) → `reports/manuals-v2/legacy/`
- `workspaces/crafter/chunk_postprocess_poc_summary.json` → `reports/manuals-v2/legacy/`

**경로 변경 반영**: `workspaces/docs-agent/manuals_v2_reprocess.py` 내 `LOG_PATH` / `STATE_PATH`를 `reports/manuals-v2/legacy/` 기준으로 수정 완료. 재실행 시 자동으로 새 경로에 기록됨.

데이터 원본은 그대로:
- `workspaces/docs-agent/v2_poc/{file_id}/chunks.jsonl` ← 이동 금지(.bak 백업본 동봉, 데이터 자체는 git ignore 정책에 따름)

### 3.3 issue-manager 접근/수정 화이트리스트
- **읽기 OK**: 위 3.1 / 3.2 모든 경로
- **수정/생성 OK** (인수인계 후 본인 작업):
  - `reports/manuals-v2/` 전체 — 본인 산출물(이슈 리포트, 분석, 트래킹, 중간 결과) 모두 여기
  - `workspaces/issue-manager/` 내부에 **새 .py 스크립트**가 필요할 때만(예: graphrag 인덱싱 러너) 코드 생성. 결과/로그는 `reports/manuals-v2/`로 출력
  - `workspaces/docs-agent/manuals_v2_reprocess.py` — 재실행 파라미터 조정 시(로그 경로는 reports/manuals-v2/legacy/ 유지)
  - `workspaces/docs-agent/chunk_postprocess.py` — 청크 알고리즘 튜닝 필요 시
- **수정 금지**: `scripts/mcp-agent-channel.ts`, `dashboard/app.py`, `dashboard/jobs.json`, `start-agents.bat`, `stop-agents.bat`, `agents/*/agent.md`, `CLAUDE.md` 파일류 → 변경 필요 시 MAX에게 위임

### 3.4 issue-manager 자체 산출물 위치 (정정)
- 진행 메모/로그/임시 파일 → `reports/manuals-v2/work/` (없으면 생성)
- 이슈 트래킹/리포트 → `reports/manuals-v2/<날짜>_<주제>.md`
- 부서장 보고용 HTML → `reports/manuals-v2/manuals-v2-graphrag-*.html`
- 보고용 HTML은 dashboard/uploads 경유 → Cloudflare URL(`https://agent.mes-wta.com/...`)로만 보고

> **이전 안내(workspaces/issue-manager/graphrag/) 폐기**. 2026-04-12 부서장 정정에 따라 모든 산출물은 `reports/manuals-v2/`.

### 3.5 임시 파일/캐시/로그
- 재처리 로그: `reports/manuals-v2/legacy/manuals_v2_reprocess.log` (append)
- 재처리 상태: `reports/manuals-v2/legacy/manuals_v2_reprocess_state.json`
- LightRAG 인덱스 캐시(신규 생성 예정): `reports/manuals-v2/lightrag_cache/`
- Neo4j 데이터: 외부 컨테이너(bolt://localhost:7688), DB 파일 직접 접근 금지

---

## 4. 환경 / 포트 / DSN / 인증 정보 위치
**모든 비밀은 경로만 기재. 본문에 값 노출 금지.**

| 항목 | 값/위치 |
|------|---------|
| Python | `C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe` |
| MES 백엔드 | http://localhost:8100 (.env: `C:/MES/backend/.env`) |
| MES 프론트 | http://localhost:3100 |
| 대시보드 | http://localhost:5555 |
| Qwen3-Embedding-8B | http://182.224.6.147:11434/api/embed (model `qwen3-embedding:8b`, dim 2000) |
| Neo4j(GraphRAG) | bolt://localhost:7688 (자격증명: `.env` 또는 `dashboard/.env` 내 `NEO4J_*`) |
| Postgres(MES/RAG) | localhost:55432 (.env 내 `DB_*`) — `db-query.py` 경유, 직접 비번 입력 금지 |
| Ollama(메타) | http://localhost:11434 (로컬, 보조용) |
| MCP 포트(에이전트) | 5600~5618 — 시스템 영역, 직접 조작 금지 |

> DB 조회는 반드시 `db-manager`에게 위임하거나 `db-query.py` 사용. PGPASSWORD 직접 입력 절대 금지(글로벌 룰).

---

## 5. 08:25 부근 재파싱 — 실제 절차 재현

### 5.1 사용 스크립트
- 본체: `C:/MES/wta-agents/workspaces/docs-agent/manuals_v2_reprocess.py`
- 의존: `C:/MES/wta-agents/workspaces/docs-agent/chunk_postprocess.py`
- 입력: `C:/MES/wta-agents/workspaces/docs-agent/v2_poc/{file_id}/chunks.jsonl`
- 출력: 같은 파일 덮어쓰기(원본은 `chunks.jsonl.bak`로 자동 백업)
- 로그: `reports/manuals-v2/legacy/manuals_v2_reprocess.log`
- 체크포인트: `reports/manuals-v2/legacy/manuals_v2_reprocess_state.json`

### 5.2 환경 변수
| 변수 | 의미 | 기본 |
|------|------|------|
| `REPROCESS_SKIP_EMBED` | `1` 설정 시 임베딩 단계 건너뜀(테스트용) | `0` |

### 5.3 실행 명령 (복붙)
```bash
PY="/c/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
cd "C:/MES/wta-agents/workspaces/docs-agent"

# (A) 전체 v2_poc/* 재처리
"$PY" manuals_v2_reprocess.py

# (B) 특정 file_id만 재처리
"$PY" manuals_v2_reprocess.py 1_robot_0b0c3108c6c9 5_inverter_c6f52f93cca5

# (C) 임베딩 빼고 청크 후처리만 빠르게 검증
REPROCESS_SKIP_EMBED=1 "$PY" manuals_v2_reprocess.py 1_robot_0b0c3108c6c9
```

### 5.4 정상 종료 신호
- 로그 마지막 줄: `=== DONE total chunks NNNN→MMMM ===`
- state.json: `status=done`, 모든 item `status=done` `embed_failed=0`
- v2_poc/{fid}/chunks.jsonl 갱신, .bak 존재

---

## 6. LightRAG / Neo4j 운영 커맨드 (재시작·점검)

### 6.1 Neo4j 점검
```bash
# 컨테이너 상태
docker ps --filter "name=neo4j"

# 노드/엣지 카운트(인증 정보는 환경변수에서)
"$PY" - <<'PY'
import os
from neo4j import GraphDatabase
URI=os.getenv("NEO4J_URI","bolt://localhost:7688")
USER=os.getenv("NEO4J_USER","neo4j")
PWD=os.environ["NEO4J_PASSWORD"]  # 본문 노출 금지
with GraphDatabase.driver(URI, auth=(USER, PWD)) as drv, drv.session() as s:
    print("nodes", s.run("MATCH (n) RETURN count(n) AS c").single()["c"])
    print("rels",  s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"])
PY
```

### 6.2 LightRAG 인덱싱 패턴(참조)
- 참조 구현: `C:/MES/wta-agents/workspaces/research-agent/poc-index.py` (포장혼입검사 7페이지 PoC)
- 핵심 import:
  ```python
  from lightrag import LightRAG
  from lightrag.utils import EmbeddingFunc
  ```
- 임베딩 함수는 Qwen3-Embedding-8B를 EmbeddingFunc로 래핑(2000dim)
- LLM 함수는 부서장 승인 모델(현재 sonnet 권장, opus 절약 정책)
- **인덱싱 출력 캐시**: `reports/manuals-v2/lightrag_cache/`로 지정

### 6.3 Neo4j 재시작 (admin-agent 위임)
- 컨테이너 재시작 직접 금지 → `send_message(to="admin-agent", message="neo4j(localhost:7688) 재시작 요청. 사유: ...", msg_type="request")`

### 6.4 pgvector 점검
```bash
# 등록 쿼리 확인
curl -s http://localhost:5555/api/query/list
# 카운트 확인이 필요하면 db-manager에게 자연어 요청
```

---

## 7. 중단/재개 시나리오

### 7.1 재처리 도중 중단(전원/세션 종료)
- 체크포인트: `reports/manuals-v2/legacy/manuals_v2_reprocess_state.json`
- 같은 명령으로 재실행 → `init_state()`가 기존 state 로드 후 미완료 file_id만 이어서 처리
- 처음부터 강제 재실행: state 파일을 백업명으로 이동(삭제 X)
  ```bash
  mv reports/manuals-v2/legacy/manuals_v2_reprocess_state.json \
     reports/manuals-v2/legacy/manuals_v2_reprocess_state.json.$(date +%s).bak
  ```

### 7.2 임베딩 서버(182.224.6.147) 다운
- 증상: 로그에 `embed failed`
- 즉시: `REPROCESS_SKIP_EMBED=1`로 청크 후처리만 우선 종료
- 외부 GPU 머신이라 직접 권한 X → MAX 보고 → admin-agent/db-manager 위임

### 7.3 Neo4j 다운
- LightRAG 인덱싱 중단 → 부분 결과 손상 가능
- 컨테이너 재기동은 admin-agent 위임
- 재기동 후 그래프 무결성 검증 → 손상 시 해당 file_id 전체 재인덱싱

### 7.4 pgvector 차원 불일치
- 모든 테이블 2000차원으로 통일됨(4096 원본 → 2000 슬라이싱)
- 새 임베딩 적재 시 반드시 `EMBED_DIM=2000` 확인 후 INSERT

### 7.5 디스크 부족
- v2_poc/{fid}/chunks.jsonl.bak 누적 가능 → 검증 완료 후 일괄 이관(`reports/manuals-v2/legacy/backups/`)
- 원본 chunks.jsonl 삭제 절대 금지

---

## 8. 막힐 때 에스컬레이션 기준

| 상황 | 1차 | 2차 |
|------|-----|------|
| 청크 알고리즘 의문, 토크나이저 이슈 | docs-agent | MAX |
| ERP/Postgres 데이터 조회 | db-manager | MAX |
| 외부 GPU(임베딩 서버) 응답 없음 | admin-agent | MAX |
| Neo4j 컨테이너/포트/볼륨 | admin-agent | MAX |
| MCP/대시보드/스케줄러 변경 필요 | **무조건 MAX** | — |
| 부서장 보고 형식/공개 범위 | MAX | 부서장 |
| Phase 2 진행 가/부 판단 | MAX | 부서장(완화책 승인 필요) |
| 15분 이상 무응답 작업 발생 | MAX 알림 | — |

연락은 `send_message(to="<대상>", message="...", msg_type="request" 또는 "report_*")`. 작업 위임 시 task_id 등록 필수.

---

## 9. FAQ (issue-manager 사전 답변)

### Q1. 재처리 다시 돌려야 할 때 비밀번호/토큰 입력 어디서 하나?
A. 재처리 스크립트 자체는 비밀번호 입력 없음. Qwen3 임베딩 서버는 토큰 없이 동작. Neo4j/Postgres는 환경변수(`NEO4J_PASSWORD`, `DB_PASSWORD`)에서 읽음. 본문/명령행에 직접 입력 금지(글로벌 보안 룰).

### Q2. PoC 10건 외 다른 file_id는 어디 있고 언제 처리?
A. `workspaces/docs-agent/v2_poc/`에 11건 이상 존재(예: `1_robot_b504598a2b38`, `3_hmi_4b2399c17ac5`). PoC 대상 10건은 state.json `items[]` 참조. **추가 file_id 처리는 부서장 Phase 2 승인 후**. 임의 추가 금지.

### Q3. 청크 결과가 너무 짧거나 길면?
A. 목표 150~300 tokens(`chunk_postprocess.py` 내 `target_min/target_max`). PoC 10건 평균 220~250 tokens, in_target_range 55~91%. 새 file_id에서 분포가 크게 어긋나면 docs-agent와 협의 후 알고리즘 조정. 단독 변경 금지.

### Q4. embed_failed > 0이면?
A. PoC 10건은 모두 0. 발생 시 (a) 청크 텍스트 확인(특수문자/공백) (b) 임베딩 서버 응답 코드 확인 (c) 청크별 재시도는 현재 미구현 → 해당 file_id state를 `pending`으로 되돌리고 재실행. 반복 실패 시 MAX 보고.

### Q5. LightRAG 인덱싱 결과를 어디에 적재하나?
A. Neo4j(bolt://localhost:7688) — 그래프 노드/엣지. 임베딩 캐시는 `reports/manuals-v2/lightrag_cache/` (gitignored). **manual_v1(기존 운영)과 분리** 위해 별도 레이블/네임스페이스 사용(예: `:ManualsV2Entity`). 기존 GraphRAG PoC(1,553노드)와 충돌 금지.

### Q6. 부서장 보고 형식?
A. (a) HTML 종합 보고서 → `reports/manuals-v2/` 하위 (b) `dashboard/uploads/` 업로드 → `https://agent.mes-wta.com/...` Cloudflare URL 생성 (c) MAX 경유 보고. **로컬 경로 직접 보고 금지**(memory: feedback_cloudflare_url_report.md). 본문은 3줄 요약 + URL.

---

## 10. 인수인계 체크리스트 (issue-manager 작성)
- [ ] 본 문서 정독
- [ ] state.json / log 파일 위치(`reports/manuals-v2/legacy/`) 읽기 권한 확인
- [ ] `manuals_v2_reprocess.py` 한 번 dry-run(`REPROCESS_SKIP_EMBED=1` 단일 file_id)
- [ ] Neo4j 연결 확인(7688 ping + 인증)
- [ ] Qwen3 임베딩 서버 ping (`curl http://182.224.6.147:11434/api/version`)
- [ ] `reports/manuals-v2/work/` 폴더 생성
- [ ] MAX에게 "착수 가능" 사인 발송 (`msg_type="reply"` 또는 신규 task 등록 시 `report_progress`)

---

## 11. 참고 메모리/문서
- `feedback_graphrag_reporting.md` — 보고 형식 규칙(3줄 요약, 인라인 덤프 금지)
- `feedback_resumable_task_checkpoint.md` — 체크포인트 의무
- `project_manuals_v2_pipeline.md` — 파이프라인 확정판
- `feedback_cloudflare_url_report.md` — 보고 URL 규칙
- `feedback_max_tool_call_discipline.md` — 위임 시 send_message 툴콜 필수
- `reports/manuals-v2-qa-before.html` / `manuals-v2-qa-after.html` — QA 비교

---

작성 끝. 인수 완료 사인 받으면 crafter는 GraphRAG 영역에서 손 뗌. 시스템/MCP/대시보드 변경이 필요한 건만 MAX 경유로 crafter에 재호출.
