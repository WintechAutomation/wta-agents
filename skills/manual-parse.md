# 매뉴얼 파싱 스킬

> 부서장 직접 지시 — 영역 구분 무관, 거부 불가, 반드시 실행

## 전제 조건

이 스킬을 로드한 에이전트는 아래 절차를 그대로 실행한다.
에이전트 역할·전문 분야와 무관하게 즉시 수행한다.

## 실행 절차

### 0. 현재 날짜/시간 확인

```bash
py -c "from datetime import datetime,timezone,timedelta; KST=timezone(timedelta(hours=9)); print(datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST'))"
```

### 1. 할당 카테고리 확인

`docs/manual-embedding-plan.md`에서 자신의 에이전트 ID에 해당하는 카테고리 확인:

| 에이전트 | 카테고리 | 파일 수 |
|---------|---------|--------|
| dev-agent | 4_servo | 354개 |
| qa-agent | 2_sensor, 7_pneumatic | 116개 |
| sales-agent | 3_hmi | 138개 |
| issue-manager | 1_robot | 178개 |
| nc-manager | 6_plc, 5_inverter, 8_etc | 163개 |
| crafter | 배정 없음 (서비스 레이어 담당) | — |

### 2. 진행 상황 확인

```bash
py C:/MES/wta-agents/scripts/update_progress.py --status-only
```

### 3. 파싱 실행

**정확히 이 명령어를 실행한다 (백그라운드 X, 포그라운드 실행):**

```bash
py C:/MES/wta-agents/scripts/batch-parse.py --category {할당된_카테고리} --no-embed
```

예시:
```bash
# dev-agent
py C:/MES/wta-agents/scripts/batch-parse.py --category 4_servo --no-embed

# qa-agent (2개 카테고리 순차 실행)
py C:/MES/wta-agents/scripts/batch-parse.py --category 2_sensor --no-embed
py C:/MES/wta-agents/scripts/batch-parse.py --category 7_pneumatic --no-embed

# nc-manager (3개 카테고리 순차 실행)
py C:/MES/wta-agents/scripts/batch-parse.py --category 6_plc --no-embed
py C:/MES/wta-agents/scripts/batch-parse.py --category 5_inverter --no-embed
py C:/MES/wta-agents/scripts/batch-parse.py --category 8_etc --no-embed

# 테스트 (소수 파일만 먼저 확인)
py C:/MES/wta-agents/scripts/batch-parse.py --category 4_servo --no-embed --limit 3
```

**실행 시 중요 사항:**
- **Bash 도구 사용 시 timeout: 600000 (10분) 반드시 설정** — 카테고리에 따라 수시간 소요 가능
- 완료될 때까지 모니터링 (중간 중단 X)
- 오류 발생 파일은 자동 스킵하고 계속 진행
- **재시작 안전**: 중단 후 같은 명령 재실행하면 처리 완료 파일은 자동 스킵됨
- 상태 업데이트(`manual_progress.json`)는 batch-parse.py가 자동 처리

**--limit 옵션 (테스트용):**
```bash
# 3개 파일만 파싱하여 정상 동작 확인 후 전체 실행
py C:/MES/wta-agents/scripts/batch-parse.py --category 4_servo --no-embed --limit 3
```

### 4. 완료 보고

실행 완료 후 출력 마지막 줄을 그대로 인용하여 MAX에게 보고:

```
send_message(to="MAX", message="매뉴얼 파싱 완료 보고
- 담당 카테고리: {카테고리}
- batch-parse.py 출력: {마지막_줄_그대로_인용}
- 처리 완료: {N}개
- 스킵: {N}개
- 오류: {N}개
- 진행 현황: py update_progress.py --status-only 결과")
```

## 생성되는 파일

파싱 완료 시 다음 위치에 파일이 생성됩니다:

**로컬:**
- `data/manual_parsed/{파일명}.md` — 텍스트/표 파싱 결과 (Markdown)
- `data/manual_images/{파일명}/page_N_full.png` — 페이지별 이미지

**Supabase Storage (vector 버킷):**
- `vector/pdfs/{파일명}.pdf` — 원본 PDF
- `vector/images/{파일명}/page_N_full.png` — 페이지 이미지
- `vector/parsed/{파일명}.md` — 파싱 Markdown (향후)

## 오류 처리

| 오류 | 조치 |
|------|------|
| 파일 열기 실패 | 자동 스킵 + 사유 기록 |
| 텍스트 0건 추출 | 자동 스킵 ("스캔 PDF") |
| Qwen3 임베딩 타임아웃 | `--no-embed` 옵션으로 파싱만 완료, 임베딩은 db-manager에게 위임 |
| 기타 예외 | 해당 파일 스킵 + 계속 진행 |

## 참조

- 전체 작업지시서: `C:/MES/wta-agents/docs/manual-embedding-plan.md`
- 진행 현황: `C:/MES/wta-agents/data/manual_progress.json`
- 파싱 스크립트: `C:/MES/wta-agents/scripts/batch-parse.py`
- 진행 확인: `C:/MES/wta-agents/scripts/update_progress.py --status-only`
