# manuals-v2 / GraphRAG 파이프라인 인수인계 (docs-agent → qa-agent)

작성일: 2026-04-12 KST
작성자: docs-agent (독스)
승인: 부서장 / MAX
대상: qa-agent (검증 필터 표준 보유자)

---

## 1. 현재 상태 (2026-04-12 10:05 기준)

- **단계**: Step2 (Docling 파싱 + 512 청킹) 배치 실행 직후 긴급 정지
- **처리 진행**: 1 / 693 (done=1, error=0, skipped=0)
- **중단 시점 파일**: `[1_robot] BASIC-INSTRUCTION-LIST.PDF` (md5=b504598a…) — 미기록 상태이므로 재개 시 자동으로 다시 시도됨
- **Step1(extract) 결과**: 7개 카테고리 status=ok 합계 693건 (8_etc 제외, 부서장 지시)

| 카테고리 | total | status=ok |
|---|---|---|
| 1_robot | 199 | 196 |
| 2_sensor | 122 | 81 |
| 3_hmi | 60 | 58 |
| 4_servo | 315 | 237 |
| 5_inverter | 17 | 8 |
| 6_plc | 85 | 72 |
| 7_pneumatic | 65 | 41 |
| **합계** | **863** | **693** |

### 체크포인트/로그 경로

```
C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_step2_state.json   # 상태 (md5 단위)
C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_step2.log          # 타임스탬프 로그
C:\MES\wta-agents\workspaces\docs-agent\manuals_v2_step2.stdout.log   # 프로세스 stdout/stderr
C:\MES\wta-agents\workspaces\docs-agent\v2_poc\{file_id}\chunks.jsonl # 단위 산출물
```

`state.json` 구조:
```
{
  "started_at": "...", "updated_at": "...",
  "files": { "<md5>": { "category","filename","status","file_id","chunks","figures","tables","elapsed","error" } },
  "totals": { "done": 1, "error": 0, "skipped": 0 }
}
```

---

## 2. 단계별 실행 커맨드 (복붙용)

> 경로는 전부 `C:\MES\wta-agents`를 기준. Windows PowerShell/bash 공통.

### Step2 재개 (파싱+청킹)

```bash
cd C:/MES/wta-agents/workspaces/docs-agent

# 전체 재개 (done/error 자동 스킵, 미기록 파일부터 처리)
python manuals_v2_step2_parse.py

# 10건만 먼저 검증
python manuals_v2_step2_parse.py --limit 10

# 카테고리 한정
python manuals_v2_step2_parse.py --category 1_robot
python manuals_v2_step2_parse.py --category 4_servo

# 이전 error 항목 재시도
python manuals_v2_step2_parse.py --retry-error

# 백그라운드로 풀배치 (로그는 step2.log + step2.stdout.log 동시 기록)
python manuals_v2_step2_parse.py > manuals_v2_step2.stdout.log 2>&1 &
```

### Step3 임베딩 (스크립트 미구현 — qa-agent가 작성)

> `manuals_v2_parse_docling.embed_texts()`가 이미 구현돼 있음. 아래 커맨드는 제안 인터페이스이며, 실제 스크립트 작성 시 state 파일명은 `manuals_v2_step3_state.json`으로 통일 권장.

```bash
cd C:/MES/wta-agents/workspaces/docs-agent

# Qwen 서버 사전 확인 (필수)
curl http://182.224.6.147:11434/api/tags | grep qwen3-embedding

# (구현 후) 전체 재개
python manuals_v2_step3_embed.py

# 일부 카테고리만
python manuals_v2_step3_embed.py --category 1_robot
```

### Step4 LightRAG + pgvector 인덱싱 (스크립트 미구현)

```bash
cd C:/MES/wta-agents/workspaces/docs-agent

# 스키마 확인 (db-manager에 요청 권장 — 직접 접속 금지)
# → manual.documents_v2 (pgvector 2000dim) 존재 여부

# (구현 후) 전체 인덱싱
python manuals_v2_step4_index.py
```

### Step5 검증 (qa-agent mrr-eval-filter-standard)

```bash
# qa-agent 자체 러너 사용
cd C:/MES/wta-agents/workspaces/qa-agent
python mrr_eval_filter.py --standard reports/mrr-eval-filter-standard.md
```

---

## 2-1. 환경변수 전체 목록

| 변수 | 기본값 | 스코프 | 의미 |
|---|---|---|---|
| `V2_EMBED` | `0` | Step2 | 파싱 중 Qwen3 임베딩 동시 호출 여부. **Step2에서는 0 유지**, Step3에서 일괄 처리 권장. |
| `V2_VLM` | `0` | Step2 | 이미지 Qwen2.5-VL 캡션 생성. Step2에서 0 유지. Step3/4에서 on 가능. |
| `EMBED_DIM` | `2000` | Step3 | Qwen3 4096차원을 MRL 슬라이싱할 차원. DB `vector(2000)`과 반드시 일치. |
| `QWEN_URL` | `http://182.224.6.147:11434/api/embed` | Step2/3 | Qwen3 임베딩 엔드포인트. 코드 상수로 하드코딩됨 (변경 시 스크립트 수정). |
| `QWEN_MODEL` | `qwen3-embedding:8b` | Step2/3 | 임베딩 모델명. |
| `VLM_URL` | `http://182.224.6.147:11434/api/generate` | Step2 | Qwen2.5-VL 엔드포인트. |
| `VLM_MODEL` | `qwen2.5vl:7b` | Step2 | VLM 모델명. |
| `PGVECTOR_DSN` | (미설정) | Step4 | PostgreSQL 접속 문자열. `.env` 또는 `db-query.py` 경유 권장. 커맨드라인 노출 금지. |
| `PYTHONIOENCODING` | `utf-8` | 전체 | Windows 콘솔 한글 깨짐 방지. 시스템 env로 잡아둘 것. |

> **보안 주의**: DB 비밀번호를 커맨드라인에 노출하지 말 것. `db-query.py` 또는 db-manager 요청으로만 접근.

---

## 2-2. 체크포인트 재개 동작

- **키**: md5 (파일명이 바뀌어도 md5가 같으면 동일 항목)
- **원자성**: 한 파일 처리 직후 `*.tmp` → rename으로 `state.json` atomic 저장
- **스킵 규칙**: `status=done` 자동 skip / `status=error` 기본 skip (`--retry-error`로 강제 재시도)
- **강제 종료**: 처리 도중 죽은 파일은 `state.json`에 미기록 → 다음 실행 시 자동 재시도
- **평균 처리시간**: 3_hmi 1건 기준 **183초/건**, 693건 풀배치 약 34시간 (OCR 비율·페이지 수에 따라 변동)

---

## 2-3. 중단/재개 시나리오 3가지

### 시나리오 A — 정상 재개 (계획된 중단)

```bash
# 1) 중단: Ctrl+C 또는 TaskStop
# 2) 상태 점검
cat workspaces/docs-agent/manuals_v2_step2_state.json | python -m json.tool | head -20
tail -20 workspaces/docs-agent/manuals_v2_step2.log

# 3) 재개 (같은 명령 그대로)
python workspaces/docs-agent/manuals_v2_step2_parse.py
```
기대: `totals.skipped`가 이전 done 수만큼 증가한 뒤 새 파일부터 처리.

### 시나리오 B — md5 미기록 파일 (프로세스 kill)

증상: 로그에 `>> [...] 파일명` 줄은 있는데 `OK chunks=...` 또는 `ERR ...`가 없음.

처리: **그냥 재실행**. 미기록 md5는 상태에 없으므로 다음 실행에서 자동 재시도됨. 별도 조치 불필요.

### 시나리오 C — state.json 손상

증상: 재실행 시 `state.json 로드 실패` 로그 + 새 state가 빈 상태로 시작 → 전부 다시 처리될 위험.

복구:
```bash
cd C:/MES/wta-agents/workspaces/docs-agent

# 1) 손상본 백업
copy manuals_v2_step2_state.json manuals_v2_step2_state.json.broken

# 2) log에서 done 리스트 복원
grep "   OK chunks=" manuals_v2_step2.log

# 3) v2_poc/ 디렉토리 실제 산출물로 done 판정
ls v2_poc/ | wc -l

# 4) 둘이 일치하면 v2_poc 디렉토리명(file_id)을 키로 state 재구성 스크립트 작성
#    (카테고리_md5앞12자리 형식에서 md5 prefix 복원 가능 — 단, 유일하지 않을 수 있으므로
#     log를 1차 소스로 삼고 v2_poc 존재 여부로 교차검증)
```
판단 어려우면 crafter 또는 MAX 에스컬레이션.

---

## 2-4. 산출물 검증 커맨드

```bash
cd C:/MES/wta-agents/workspaces/docs-agent

# 1) v2_poc 디렉토리 수 = 완료 파일 수
ls v2_poc/ | wc -l

# 2) 개별 파일 chunks.jsonl 행 수 / 샘플
wc -l v2_poc/3_hmi_4b2399c17ac5/chunks.jsonl
head -1 v2_poc/3_hmi_4b2399c17ac5/chunks.jsonl | python -m json.tool

# 3) state.json totals
python -c "import json; s=json.load(open('manuals_v2_step2_state.json',encoding='utf-8')); print(s['totals']); print('files:',len(s['files']))"

# 4) 카테고리별 done 집계
python -c "import json,collections; s=json.load(open('manuals_v2_step2_state.json',encoding='utf-8')); c=collections.Counter(v['category'] for v in s['files'].values() if v.get('status')=='done'); print(dict(c))"

# 5) error만 뽑기
python -c "import json; s=json.load(open('manuals_v2_step2_state.json',encoding='utf-8')); [print(v['filename'],'|',v.get('error')) for v in s['files'].values() if v.get('status')=='error']"

# 6) chunks.jsonl 필수 필드 검증
python -c "
import json,glob
bad=0
for p in glob.glob('v2_poc/*/chunks.jsonl'):
    for ln in open(p,encoding='utf-8'):
        d=json.loads(ln)
        for k in ('file_id','chunk_id','category','content','page_start'):
            if k not in d: bad+=1; break
print('bad_rows=',bad)
"
```

---

## 3. 전체 파이프라인 (승인판, 2026-04-11)

```
Step1  분류·추출      manuals_v2_step1_extract.py          ✅ 완료 (7개 카테고리)
Step2  Docling 파싱+  manuals_v2_step2_parse.py            🟡 1/693 중단 상태
       512 청킹        (manuals_v2_parse_docling 재사용)
Step3  임베딩          (미구현) Qwen3-Embedding-8B,        ⏳ 예정
                      EMBED_DIM=2000 슬라이싱
Step4  인덱싱          (미구현) LightRAG + pgvector        ⏳ 예정
                      (manual.documents_v2 스키마)
Step5  검증            qa-agent mrr-eval-filter-standard  ⏳ 대기
```

### 모델 / 엔드포인트

| 용도 | 서버 | 모델 | 비고 |
|---|---|---|---|
| 임베딩 | `http://182.224.6.147:11434/api/embed` | `qwen3-embedding:8b` | 4096 → **2000 슬라이싱 필수** |
| VLM 캡션 | `http://182.224.6.147:11434/api/generate` | `qwen2.5vl:7b` | 한글 3~5문장, temperature 0.1 |

### Step3 구현 시 주의사항
- `manuals_v2_parse_docling.embed_texts()`가 이미 구현돼 있음 (단건 호출, 슬라이싱 포함)
- 별도 `manuals_v2_step3_embed.py`를 만들어 `v2_poc/*/chunks.jsonl`을 순회하며 `embedding` 필드 채우기 권장 (동일 state.json 패턴 재사용)
- Qwen 서버 가용성 먼저 확인: `curl http://182.224.6.147:11434/api/tags`

### Step4 인덱싱 대상
- `manual.documents_v2` (pgvector 2000dim) — 스키마 미생성 가능성 있음. db-manager 확인 필요
- LightRAG 그래프 노드: 매뉴얼 섹션·그림·표 단위 (PoC 단계 설계 문서 참조)

---

## 4. 주요 스크립트 경로

```
workspaces/docs-agent/
├── manuals_v2_step1_extract.py          # Step1: 카테고리별 PDF 텍스트 추출 + OCR 판정
├── manuals_v2_pipeline.py                # Step1 배치 러너 (카테고리 루프)
├── manuals_v2_{category}_extract.jsonl   # Step1 결과 (7개)
├── manuals_v2_{category}_classification.csv
├── manuals_v2_summary.json               # Step1 통계 스냅샷
│
├── manuals_v2_parse_docling.py           # Step2 단일 PDF 처리 (Docling+HierarchicalChunker+선택 임베딩/VLM)
├── manuals_v2_step2_parse.py             # Step2 배치 러너 (재개 가능)
├── manuals_v2_step2_state.json           # Step2 상태
├── manuals_v2_step2.log                  # Step2 로그
│
├── v2_poc/{file_id}/
│   ├── document.json                     # Docling export
│   ├── chunks.jsonl                      # 청크 + (선택적) embedding
│   └── images/*.png, *_thumb.png         # 그림/표 이미지 (V2_VLM=1 시 캡션 포함)
│
└── (Step3/Step4는 미구현 — qa-agent가 작성 예정)
```

### 참조 문서
- `docs/handover-manual-rag.md` — 기존 RAG v1 인수인계
- `MEMORY.md` 내 `project_manuals_v2_pipeline.md` — 파이프라인 승인판 요약
- `feedback_graphrag_reporting.md` / `feedback_resumable_task_checkpoint.md` — 보고·체크포인트 규칙

---

## 5. 알려진 이슈 / 주의

1. **OCR 비율이 높은 카테고리**
   - `2_sensor`: OCR 45/122, Unknown 제조사 32건
   - `5_inverter`: OCR 11/17 (대부분 스캔본)
   - `7_pneumatic`: OCR 30/65
   - 영향: OCR 텍스트는 오탈자·기호 왜곡이 많음 → 임베딩 품질·검색 정확도 저하 가능. Step5 검증에서 카테고리별 MRR 분리 측정 권장.

2. **PDF 색공간 오류 로그 다수**
   - `Cannot set non-stroke color: 2 components specified` / `Data-loss while decompressing corrupted data`
   - Docling/pdfminer 경고로, 파싱 자체는 진행됨. 일부 페이지 텍스트 누락 가능.
   - 무시 가능하나, `error` 상태로 끝난 파일은 `--retry-error`로 재시도 후에도 실패하면 해당 파일만 스킵 처리 권장.

3. **Unknown 제조사 비율**
   - `3_hmi` 43/59, `6_plc` 48/84, `7_pneumatic` 28/65
   - 표준명(`{mfr}_{model}_{doctype}_{lang}.pdf`) 규칙 미준수 때문. 메타데이터는 부정확할 수 있으나 청크 자체에는 영향 없음.

4. **소요시간 예측**
   - 693건 × ~3분 = **단순 계산 약 34시간**. 순차 실행 전제. 병렬화 시 Docling OCR이 CPU 바운드라 효과 제한적.

5. **8_etc 카테고리 제외**
   - 부서장 지시(2026-04-12)에 따라 Step2 대상에서 제외. 추후 별도 지시 시 `CATEGORIES` dict에 추가하면 재개 구조로 합류 가능.

---

## 6. FAQ (선제 정리)

**Q1. 재개했는데 "대상 693건"이라고 나오는데 이전 완료분은 다시 처리되나요?**
→ 아니요. 전체 대상 693건을 로드한 뒤 `state.json`에서 `status=done`/`error`인 md5를 자동 스킵합니다. 로그에 `totals.skipped`로 카운트됩니다.

**Q2. Qwen 서버가 죽어 있으면?**
→ Step2는 `V2_EMBED=0` 기본이라 영향 없습니다. Step3 임베딩 단계에서만 필요하며, 실행 전 `curl http://182.224.6.147:11434/api/tags`로 `qwen3-embedding:8b` 존재 확인 필수.

**Q3. `v2_poc/{file_id}` 폴더를 지우면?**
→ `state.json`은 `done`으로 남아있어 해당 파일은 재처리되지 않습니다. 강제 재처리하려면 `state.json`에서 해당 md5 항목 삭제 후 재실행하세요.

**Q4. 중간에 프로세스가 죽었는지 확인하려면?**
→ `manuals_v2_step2.log`의 마지막 타임스탬프와 `manuals_v2_step2_state.json`의 `updated_at`을 비교. 5분 이상 진행이 없으면 중단된 것으로 간주 가능. TaskList로 `b57b0lazn` 같은 background task ID를 확인해도 됩니다.

**Q5. Step3 임베딩 배치는 어떻게 시작하나요?**
→ 아직 미구현입니다. `manuals_v2_parse_docling.embed_texts()`를 재사용해 `v2_poc/*/chunks.jsonl`을 순회하며 `embedding` 필드를 채우는 `manuals_v2_step3_embed.py`를 새로 작성하는 것이 가장 빠릅니다. state.json/log 2파일 구조는 Step2와 동일하게 유지하세요(부서장 체크포인트 규칙).

**Q6. 보고 형식은?**
→ `feedback_graphrag_reporting.md` 준수: MAX에 3줄 요약 + state/log 경로, 인라인 덤프 금지. 단계 전환 시 `report_progress`, 완료 시 `report_complete` + `task_id`.

---

## 7. 작업공간 경계 (필수)

### 경로 고정 원칙
**기존 파일 위치는 전부 유지.** qa-agent가 인수받아도 경로 변경 금지. state.json, 체크포인트, 스크립트, v2_poc/ 산출물 모두 `workspaces/docs-agent/` 그대로 유지할 것. 경로 이동은 재개 불가 또는 상태 꼬임을 유발함.

### 화이트리스트 — qa-agent가 만지는 파일

**읽기+쓰기 허용 (manuals-v2 파이프라인 작업 범위)**
```
workspaces/docs-agent/manuals_v2_*.py
workspaces/docs-agent/manuals_v2_step*_state.json
workspaces/docs-agent/manuals_v2_step*.log
workspaces/docs-agent/manuals_v2_step*.stdout.log
workspaces/docs-agent/v2_poc/                # 산출물 디렉토리 전체
workspaces/docs-agent/manuals_v2_*_extract.jsonl
workspaces/docs-agent/manuals_v2_*_classification.csv
workspaces/docs-agent/manuals_v2_summary.json
```

**읽기 전용 (참조용, 수정 금지)**
```
reports/manuals-v2-*.html                    # 기존 리포트
reports/mrr-eval-filter-standard.md          # 검증 필터 표준
workspaces/docs-agent/manuals_v2_handoff.md  # 이 문서
workspaces/docs-agent/CLAUDE.md              # docs-agent 설정
```

### qa-agent 자체 산출물 경로
qa-agent가 만드는 검증 리포트, 쿼리셋, MRR 결과 JSON 등은 **반드시** 본인 워크스페이스에 생성:
```
workspaces/qa-agent/manuals_v2_eval_*.py       # 검증 러너
workspaces/qa-agent/manuals_v2_queryset.jsonl  # 쿼리셋
workspaces/qa-agent/manuals_v2_mrr_result.json # 결과
workspaces/qa-agent/manuals_v2_eval.log        # 실행 로그
```
docs-agent 파이프라인 경로(`workspaces/docs-agent/`)에 검증용 산출물 섞지 말 것.

### 공용 최종 산출물 (부서장 보고용)
```
reports/manuals-v2/                           # 디렉토리는 qa-agent가 생성
  ├── step2_summary_YYYYMMDD.html             # Step2 완료 리포트
  ├── step3_embedding_summary_YYYYMMDD.html   # Step3 완료 리포트
  ├── mrr_eval_report_YYYYMMDD.html           # 최종 검증 리포트
  └── mrr_eval_queryset.jsonl                 # 공개 쿼리셋 스냅샷
```
Cloudflare URL로 보고 시 `agent.mes-wta.com/{파일명(확장자 제외)}` 형식.

### 임시 파일 / 캐시 위치

| 용도 | 위치 | 정리 주기 |
|---|---|---|
| Docling 내부 캐시 | OS TEMP (자동) | Docling이 관리 |
| 파이프라인 임시 로그 | `workspaces/docs-agent/manuals_v2_*.log` | 완료 후 보존 (체크포인트 자료) |
| qa-agent 실험 임시 파일 | `workspaces/qa-agent/tmp/` | 하루 1회 정리 |
| 대용량 PDF 원본 | `data/manuals/{category}/` | 불변 (읽기 전용) |

**절대 생성 금지 경로**: `C:\` 루트, 바탕화면, `C:\MES\wta-agents\` 최상위.

---

## 8. 막힐 때 에스컬레이션 기준

| 상황 | 1차 대응 | 2차 에스컬레이션 |
|---|---|---|
| Qwen 서버 응답 없음 / 모델 없음 | `curl /api/tags`로 점검, 5분 재시도 | admin-agent (인프라) |
| Docling import 에러 / 의존성 문제 | `pip list | grep docling` 확인, venv 점검 | crafter (환경 구성) |
| `state.json` 손상 / 복구 어려움 | 시나리오 C 시도 | crafter (스크립트), MAX (의사결정) |
| pgvector 스키마/차원 불일치 | db-manager에 요청 (직접 접속 금지) | MAX (스키마 승인) |
| 특정 PDF 반복 실패 (3회+) | `status=error`로 남기고 계속, 로그 보존 | MAX (스킵 승인) |
| 파이프라인 설계 변경 필요 | 즉시 MAX 보고 | 부서장 |
| 장애로 인한 재실행 판단 | 30분 이상 진행 정체 시 MAX에 상태 공유 | 부서장 |
| 4시간 진행해도 done 증가 없음 | 즉시 정지 + 로그 수집 | crafter + MAX 동시 |

### 보고 형식 (feedback_graphrag_reporting.md)
- MAX로 보낼 때: **3줄 요약 + state/log 경로**. 인라인 JSON 덤프 금지.
- 단계 전환: `msg_type="report_progress"` + `task_id`
- 완료: `msg_type="report_complete"` + `task_id` + Cloudflare URL
- 막힘: `msg_type="report_blocked"` + `task_id` + 원인 한 줄

---

## 9. 인수인계 체크리스트

- [x] Step1 완료 (7 카테고리, 693건 ok)
- [x] Step2 러너·체크포인트 구조 완성 (`manuals_v2_step2_parse.py`)
- [x] Step2 스모크 테스트 1건 성공 (3_hmi, chunks=27)
- [x] Step2 풀배치 1건 처리 후 부서장 지시로 정지
- [x] state.json / log 보존
- [ ] Step2 풀배치 재개 (qa-agent)
- [ ] Step3 임베딩 스크립트 작성 및 실행
- [ ] Step4 LightRAG+pgvector 인덱싱
- [ ] Step5 mrr-eval-filter-standard 기반 검증

### 인수 완료 사인 (qa-agent 작성)
아래 항목을 qa-agent가 전부 확인한 뒤 MAX에게 "착수 가능" 보고:
- [ ] 이 문서 끝까지 읽음
- [ ] `manuals_v2_step2_state.json` 현재 상태 확인 완료
- [ ] `manuals_v2_step2_parse.py --limit 1 --category 3_hmi`로 재실행 동작 검증 (또는 Ctrl+C 테스트)
- [ ] 화이트리스트·작업공간 경계 이해 완료
- [ ] 에스컬레이션 기준 이해 완료

문의: docs-agent (독스, 📝)
