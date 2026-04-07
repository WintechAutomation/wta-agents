# WTA 사용자매뉴얼 파싱 스킬

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

| 에이전트 | 카테고리 | 예상 파일 수 |
|---------|---------|------------|
| dev-agent | 프레스 | ~190개 |
| qa-agent | PVD | ~86개 |
| sales-agent | 검사기 | ~82개 |
| issue-manager | CVD, 소결취출기 | ~92개 |
| nc-manager | 포장기, 호닝기, WBM_WVR_대성호닝 | ~99개 |
| cs-agent | 후지산기연삭핸들러 + 기타 소규모 | ~41개 |

### 2. 파싱 실행

**정확히 이 명령어를 실행한다 (포그라운드, Bash timeout: 600000 필수):**

```bash
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category {할당된_카테고리} --no-embed
```

**예시:**
```bash
# dev-agent
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category 프레스 --no-embed

# qa-agent
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category PVD --no-embed

# issue-manager (2개 순차)
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category CVD --no-embed
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category 소결취출기 --no-embed

# nc-manager (3개 순차)
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category 포장기 --no-embed
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category 호닝기 --no-embed
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category WBM_WVR_대성호닝 --no-embed

# 테스트 (소수 파일만)
py C:/MES/wta-agents/scripts/batch-parse-docling.py --source-dir data/wta-manuals-final --category 프레스 --no-embed --limit 3
```

**실행 시 중요 사항:**
- **Bash 도구 사용 시 timeout: 600000 (10분) 반드시 설정** — PDF당 1~5분 소요
- 완료될 때까지 모니터링 (중간 중단 X)
- 오류 발생 파일은 자동 스킵하고 계속 진행
- **재시작 안전**: 중단 후 같은 명령 재실행하면 완료 파일 자동 스킵

### 3. 완료 보고

실행 완료 후 MAX에게 보고:

```
send_message(to="MAX", message="WTA 매뉴얼 파싱 완료 보고
- 담당 카테고리: {카테고리}
- 처리 완료: {N}개
- 스킵: {N}개
- 오류: {N}개
- 총 청크: {N}개")
```

## 생성되는 파일

**로컬 (부품 매뉴얼과 분리됨):**
- `data/wta_parsed/{파일명}.md` — 텍스트/표 파싱 결과 (Markdown)
- `data/wta_images/{파일명}/` — 이미지 (챕터+캡션 태깅 파일명)

**Supabase Storage (vector 버킷):**
- `vector/images/wta/{파일명}/` — 이미지

**DB:**
- `manual.wta_documents` — 임베딩 데이터 (임베딩은 별도 단계)

## 오류 처리

| 오류 | 조치 |
|------|------|
| 파일 열기 실패 | 자동 스킵 + 계속 진행 |
| OCR 메모리 부족 (bad_alloc) | --no-ocr 옵션 추가하여 재실행 |
| 텍스트 0건 추출 | 자동 스킵 |
| Supabase 업로드 실패 | 로컬 파일은 유지, 계속 진행 |
| 기타 예외 | 해당 파일 스킵 + 계속 진행 |

## 참조

- 원본 파일: `C:/MES/wta-agents/data/wta-manuals-final/{카테고리}/`
- 파싱 스크립트: `C:/MES/wta-agents/scripts/batch-parse-docling.py`
- DB 테이블: `manual.wta_documents`
- 부품 매뉴얼 스킬: `skills/manual-parse.md` (참고용, 별도 파이프라인)
