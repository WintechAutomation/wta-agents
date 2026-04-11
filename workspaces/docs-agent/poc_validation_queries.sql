-- manuals-v2 PoC 검증 쿼리 5건
-- 목적: 본문 텍스트 + 이미지 관계성 보존 검증, 카테고리/제조사 필터링 동작 확인
-- 실행 방법: db-manager에게 전달 → 각 쿼리의 Top 5 결과 + figure_refs 샘플 회수

-- 공통 전제:
--   1) query_text를 Qwen3-Embedding-8B (2000d, MRL)로 임베딩 후 q_vec 파라미터로 전달
--   2) cosine 거리 기준 (embedding <=> q_vec)
--   3) category/lang 필터 선택적 적용

-- ============ Q1. 서보 결선도 (Yaskawa V1000 예상) ============
-- query: "V1000 서보 전원 결선도"
-- 기대: 5_inverter 카테고리 + Yaskawa + V1000 모델의 전원/결선 관련 청크 + figure_refs 포함
SELECT
  file_id, chunk_id, mfr, model, lang,
  section_path,
  LEFT(content, 200) AS preview,
  jsonb_array_length(COALESCE(figure_refs, '[]'::jsonb)) AS n_figs,
  1 - (embedding <=> %(q_vec)s) AS sim
FROM manual.documents_v2
WHERE category IN ('5_inverter','1_robot')
  AND (mfr = 'Yaskawa' OR content ILIKE '%V1000%')
ORDER BY embedding <=> %(q_vec)s
LIMIT 5;

-- ============ Q2. 에러코드 E401 ============
-- query: "에러코드 E401 원인과 복구 방법"
-- 기대: 1_robot 카테고리 Mitsubishi Troubleshooting/MaintenanceManual 계열 히트
SELECT
  file_id, chunk_id, mfr, model, lang, doctype,
  LEFT(content, 300) AS preview,
  jsonb_array_length(COALESCE(figure_refs, '[]'::jsonb)) AS n_figs,
  1 - (embedding <=> %(q_vec)s) AS sim
FROM manual.documents_v2
WHERE content ~* 'E\s*401|에러\s*401|E401'
ORDER BY embedding <=> %(q_vec)s
LIMIT 5;

-- ============ Q3. CR750 (또는 CR800) 로봇 셋업 절차 ============
-- query: "Mitsubishi CR 컨트롤러 초기 셋업 절차"
-- 기대: BFP-A8601-D SetupGuide 히트. figure_refs 내 storage_path 포함 (결선 이미지)
SELECT
  file_id, chunk_id, mfr, model, doctype,
  section_path,
  LEFT(content, 300) AS preview,
  figure_refs -> 0 ->> 'storage_path' AS first_fig_path,
  figure_refs -> 0 ->> 'vlm_description' AS first_fig_vlm,
  1 - (embedding <=> %(q_vec)s) AS sim
FROM manual.documents_v2
WHERE category = '1_robot'
  AND mfr = 'Mitsubishi'
  AND doctype ILIKE '%setup%'
ORDER BY embedding <=> %(q_vec)s
LIMIT 5;

-- ============ Q4. 로봇 가반중량 / payload (다국어) ============
-- query: "pick and place 로봇 최대 가반중량"
-- 기대: ABB IRB360, Sanyo SanmotionR, Mitsubishi 등 ProductSpec 문서 히트. 다국어 교차 확인.
SELECT
  file_id, chunk_id, mfr, model, lang,
  LEFT(content, 300) AS preview,
  jsonb_array_length(COALESCE(figure_refs, '[]'::jsonb)) AS n_figs,
  jsonb_array_length(COALESCE(table_refs, '[]'::jsonb)) AS n_tbls,
  1 - (embedding <=> %(q_vec)s) AS sim
FROM manual.documents_v2
WHERE category = '1_robot'
  AND doctype ILIKE '%spec%'
ORDER BY embedding <=> %(q_vec)s
LIMIT 5;

-- ============ Q5. CC-Link 통신 설정 (필드버스) ============
-- query: "CC-Link 국번 설정 방법"
-- 기대: BFP-A8615 CCLinkInterface 문서 상위 히트. figure_refs 내 VLM 설명에 '스위치' '국번' 키워드 등장.
SELECT
  file_id, chunk_id, mfr, model, doctype,
  LEFT(content, 300) AS preview,
  figure_refs -> 0 ->> 'vlm_description' AS vlm_desc,
  inline_refs,
  1 - (embedding <=> %(q_vec)s) AS sim
FROM manual.documents_v2
WHERE content ILIKE '%CC-Link%' OR content ILIKE '%CCLink%'
ORDER BY embedding <=> %(q_vec)s
LIMIT 5;

-- ============ 부가 검증 ============
-- V1. 카테고리별 청크/이미지 분포
SELECT category, COUNT(*) AS chunks,
       SUM(jsonb_array_length(COALESCE(figure_refs,'[]'::jsonb))) AS fig_refs,
       SUM(jsonb_array_length(COALESCE(table_refs,'[]'::jsonb))) AS tbl_refs
FROM manual.documents_v2
GROUP BY category
ORDER BY category;

-- V2. figure_refs 내 storage_path 비어있는 경우 (Storage 업로드 실패 흔적)
SELECT COUNT(*) AS chunks_with_missing_storage
FROM manual.documents_v2, jsonb_array_elements(figure_refs) AS fr
WHERE fr->>'storage_path' IS NULL OR fr->>'image_url' IS NULL;

-- V3. VLM 설명 누락 비율
SELECT
  SUM(CASE WHEN fr->>'vlm_description' IS NOT NULL AND fr->>'vlm_description' <> '' THEN 1 ELSE 0 END) AS with_vlm,
  COUNT(*) AS total_figs
FROM manual.documents_v2, jsonb_array_elements(figure_refs) AS fr;
