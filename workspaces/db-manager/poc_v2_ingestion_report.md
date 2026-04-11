# manual.documents_v2 — PoC 10건 적재 검수 리포트

작성: db-manager
완료: 2026-04-12
협업: docs-agent (Docling 파싱 + VLM + Storage 업로드), db-manager (로더 + 검수)

## 1. 개요

| 항목 | 값 |
|---|---|
| 대상 | PoC 10건 (실제 9건 + 경로 정정 1건) |
| 총 rows | **10,215** |
| distinct file_id | 10 |
| distinct category | 3 (`1_robot`, `5_inverter`, `2_sensor`) |
| distinct mfr | 5 (Mitsubishi, Yaskawa, Sanyo, Cognex, ABB) |
| 언어 | ko / ja / en |
| 에러 (적재) | 0 |
| 적재 시간 (누적) | 약 101s (dry-run 포함) |

## 2. 파일별 요약

| # | file_id | cat | mfr | lang | rows | tok min/avg/max | w_figs | fig_refs | tbl_refs | dim2k |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 1_robot_2d70fa79608e | 1_robot | Yaskawa | ko | 7 | 2/98/184 | 3 | 5 | 14 | 7 |
| 2 | 1_robot_2d77a92d4066 | 1_robot | Mitsubishi | en | 68 | 5/553/1757 | 27 | 37 | 50 | 68 |
| 3 | 1_robot_3c1dcc39da41 | 1_robot | Mitsubishi | ko | 205 | 2/73/1412 | 132 | 267 | 175 | 205 |
| 4 | 1_robot_c7fe37c1ed98 | 1_robot | Mitsubishi | ko | 395 | 2/27/782 | 261 | 556 | 72 | 395 |
| 5 | 1_robot_54fdb56329f0 | 1_robot | ABB | en | 159 | 2/43/769 | 88 | 122 | 295 | 159 |
| 6 | 1_robot_0b0c3108c6c9 | 1_robot | Sanyo | en | 440 | 2/264/3827 | 348 | 1,153 | 826 | 440 |
| 7 | 1_robot_c5a220711bc5 | 1_robot | Mitsubishi | ja | 1,229 | 2/11.5/518 | 310 | 915 | 232 | 1,229 |
| 8 | 2_sensor_2e6136a51564 | 2_sensor | Cognex | ko | 175 | 2/77/1417 | 107 | 118 | 95 | 175 |
| 9 | 1_robot_314928a33268 | 1_robot | Mitsubishi | ko | 3,927 | 2/24/1668 | 1,183 | 2,425 | 1,193 | 3,927 |
| 10 | 5_inverter_c6f52f93cca5 | 5_inverter | Yaskawa | ko | 3,610 | 2/87/25,263 | 1,657 | 2,611 | 8,536 | 3,610 |

## 3. 핵심 KPI (PASS/FAIL)

| KPI | 결과 | 비고 |
|---|---|---|
| 임베딩 차원 2000 전수 | **PASS** 10,215/10,215 | |
| VLM description coverage | **PASS** 8,209/8,209 (100%) | figure_refs 전부 vlm_description 존재 |
| 적재 에러 | **PASS** 0/10,215 | dry-run/실적재 모두 0 |
| UPSERT 멱등성 | **PASS** | `(file_id, chunk_id)` UNIQUE, 재실행 안전 |
| HNSW 벡터 검색 sanity | **PASS** | self-distance 0.0, nearest cos_dist=0.14로 정상 |
| 이미지/테이블 매칭율 (청크) | 66.9% (w_any) | figs 40.3% + tbls 43.5% |

## 4. 토큰 분포 (전체 10,215 청크)

### 4.1 히스토그램

| 구간 | 청크 수 | 비율 |
|---|---:|---:|
| 0–10 | 5,206 | 51.0% |
| 11–50 | 3,829 | 37.5% |
| 51–100 | 496 | 4.9% |
| 101–200 | 253 | 2.5% |
| 201–500 | 171 | 1.7% |
| >500 | 260 | 2.5% |

- min = 2, **median = 10**, avg = 60.8, p95 = 152, max = 25,263

### 4.2 언어별 평균

| lang | rows | tok avg |
|---|---:|---:|
| ko | 8,319 | 53.7 |
| ja | 1,229 | **11.5** ⚠️ |
| en | 667 | 240.3 |

### 4.3 🚨 이슈 식별 — 청크 과분할 경향

- **88.5%의 청크가 50 토큰 이하** (0–10: 51% + 11–50: 37.5%)
- 특히 **일본어(ja)와 한국어(ko) 대형 매뉴얼**에서 두드러짐
  - 파일 7 (Mitsubishi JA): avg 11.5
  - 파일 9 (Mitsubishi KO, 3,927 rows): avg 23.9
  - 파일 4 (Mitsubishi KO SetupGuide): avg 27.1
- 영문(en) 파일은 정상 범위 (avg 240)

**원인 가설**
- Docling `HierarchicalChunker(max_tokens=512)`가 CJK 언어에서 tokenizer 오판으로 512 한도를 과도하게 엄격히 적용
- 또는 표/그림 경계에서 bullet/label 단편을 별도 청크로 분리
- VLM vlm_description은 figure_refs 내부에 있어 content tokens에는 미포함 → 실질 검색 대상 텍스트가 매우 짧음

**검색 품질 영향 추정**
- 짧은 청크는 dense 임베딩 표현력이 떨어지고 BM25 스코어도 불안정
- figure_refs 없는 짧은 청크(예: 1_robot_314928a33268의 2,744개 청크)는 사실상 meta-only 레코드
- 반대로 vlm_description이 붙은 청크는 이미지 맥락으로 검색 가능하므로 완전 손실은 아님

## 5. 고토큰 이상치 (상위 5건)

| file_id | chunk_id | tokens | content_len | figs | tbls |
|---|---|---:|---:|---:|---:|
| 5_inverter_c6f52f93cca5 | 0418_3467 | 25,263 | 63,578 | 0 | 2 |
| 5_inverter_c6f52f93cca5 | 0421_3600 | 12,577 | 28,744 | 0 | 1 |
| 5_inverter_c6f52f93cca5 | 0417_3465 | 7,406 | 17,101 | 0 | 1 |
| 5_inverter_c6f52f93cca5 | 0420_3469 | 7,169 | 16,544 | 0 | 1 |
| 5_inverter_c6f52f93cca5 | 0419_3468 | 6,523 | 15,667 | 0 | 1 |

- 모두 Yaskawa V1000 인버터 매뉴얼의 거대 테이블이 단일 청크로 들어간 경우
- content_len 63KB → **한 청크에 표 전체가 flatten된 상태**
- HNSW 임베딩 품질 저하 우려 (Qwen3-Embedding-8B도 context 제한 존재), 재파싱 시 테이블 분할 규칙 필요

## 6. 관찰 권고 (다음 단계 제안)

1. **청킹 재튜닝 (CJK)**
   - 현재 512/64 유지 가정에서 avg 11~24 → 지나치게 잘게 쪼개짐
   - 제안: `min_chunk_tokens=40` 필터 도입 + "이웃 청크 병합 (같은 page + 동일 section)" 후처리
   - 또는 Docling tokenizer를 char-based로 전환 검토 (docling-core config)

2. **대형 테이블 분할**
   - 파일 10의 25K 토큰 청크는 HNSW 임베딩 품질에 악영향
   - 제안: 행 기준으로 분할 (예: 50행 단위) + 표 제목을 각 파트 content 앞단에 반복 삽입

3. **VLM 의존 청크 식별**
   - figure_refs에만 의미가 있는 짧은 청크는 별도 flag로 마킹하거나 검색 가중치 분리
   - 스키마 확장 없이 `tokens<40 AND jsonb_array_length(figure_refs)>0` 쿼리로 필터 가능

4. **언어별 리포트**
   - 확장 시 `lang` 필터 조합 검증 필수 (현재는 ko/ja/en만 관찰)

## 7. DB 현황 (POST 검증 쿼리)

```sql
SELECT COUNT(*), COUNT(DISTINCT file_id), COUNT(DISTINCT category)
FROM manual.documents_v2;
-- (10215, 10, 3)

SELECT lang, COUNT(*), ROUND(AVG(tokens)::numeric,1)
FROM manual.documents_v2 GROUP BY lang;

SELECT SUM(CASE WHEN array_length(embedding::real[],1)=2000 THEN 1 ELSE 0 END), COUNT(*)
FROM manual.documents_v2;
-- (10215, 10215)  PASS
```

## 8. 다음 단계 (db-manager)

- [ ] Neo4j `:ManualV2` 노드/관계 적재 스크립트 작성 (JSONL → MERGE) — 진행 예정
- [ ] idempotent 재실행 검증 (1번 파일로 2회 적재 후 노드/관계 수 동일 확인)
- [ ] MAX/docs-agent와 청킹 재튜닝 여부 협의
- [ ] 전량 확장 시점에 토큰 히스토그램/매칭율 재측정 배치 스크립트 등록
