-- ============================================================
-- manual.documents_v2 — 신규 매뉴얼 지식 테이블
-- 합의 주체: db-manager + docs-agent (2026-04-11)
-- 승인: MAX / 부서장 (DDL 실행은 OK 사인 후)
-- 전제: vector 확장 0.8.0 설치됨, pgvector HNSW 지원
-- 기존 manual.documents(218k), manual.wta_documents(67k)는 그대로 보존
-- ============================================================

-- schema 존재 확인 (manual 스키마는 이미 있음)
-- CREATE SCHEMA IF NOT EXISTS manual;

CREATE TABLE IF NOT EXISTS manual.documents_v2 (
    id            BIGSERIAL PRIMARY KEY,
    file_id       TEXT NOT NULL,                  -- {category}_{md5[:12]}
    chunk_id      TEXT NOT NULL,                  -- {page_start:04d}_{chunk_idx:04d}
    category      TEXT NOT NULL,                  -- 1_robot, 2_vision, ...
    mfr           TEXT,                           -- Mitsubishi, Panasonic, ...
    model         TEXT,                           -- 모델/형번
    doctype       TEXT,                           -- manual, catalog, guide, datasheet, ...
    lang          TEXT,                           -- ko, en, ja, zh, ...
    section_path  JSONB,                          -- ["Chapter 3", "3.1 Setup"]
    page_start    INT,
    page_end      INT,
    content       TEXT NOT NULL,
    tokens        INT,                            -- 청크 토큰 수 (품질 분석용)
    source_hash   TEXT,                           -- 원본 파일 md5 (재파싱 트리거)
    embedding     vector(2000) NOT NULL,          -- Qwen3-Embedding-8B (4096→2000 슬라이싱)
    figure_refs   JSONB,                          -- [{figure_id, page, storage_path, caption}]
    table_refs    JSONB,                          -- [{table_id, page, storage_path, caption}]
    inline_refs   JSONB,                          -- 본문 내 참조(그림 X.Y 등)
    content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT documents_v2_file_chunk_uniq UNIQUE (file_id, chunk_id)
);

-- -----------------------------------------------------------
-- 인덱스
-- -----------------------------------------------------------

-- 벡터 검색 (HNSW, 코사인)
CREATE INDEX IF NOT EXISTS documents_v2_embedding_hnsw_idx
    ON manual.documents_v2
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- BM25/FTS 1차 필터
CREATE INDEX IF NOT EXISTS documents_v2_content_tsv_gin_idx
    ON manual.documents_v2
    USING gin (content_tsv);

-- 복합 필터 인덱스
CREATE INDEX IF NOT EXISTS documents_v2_category_mfr_idx
    ON manual.documents_v2 (category, mfr);

CREATE INDEX IF NOT EXISTS documents_v2_doctype_lang_idx
    ON manual.documents_v2 (doctype, lang);

-- 이미지/테이블 참조 JSON 검색 (figure_id 포함 여부 등)
CREATE INDEX IF NOT EXISTS documents_v2_figure_refs_gin_idx
    ON manual.documents_v2
    USING gin (figure_refs);

CREATE INDEX IF NOT EXISTS documents_v2_table_refs_gin_idx
    ON manual.documents_v2
    USING gin (table_refs);

-- source_hash 기반 재파싱 탐지용
CREATE INDEX IF NOT EXISTS documents_v2_source_hash_idx
    ON manual.documents_v2 (source_hash);

-- -----------------------------------------------------------
-- 코멘트
-- -----------------------------------------------------------
COMMENT ON TABLE manual.documents_v2 IS
    'v2 매뉴얼 지식 테이블 (HNSW + tsvector 하이브리드, 이미지 refs 포함). docs-agent Docling 파싱 결과 적재용.';
COMMENT ON COLUMN manual.documents_v2.file_id IS '{category}_{md5[:12]} — 카테고리 prefix + 원본 md5 12자리';
COMMENT ON COLUMN manual.documents_v2.chunk_id IS '{page_start:04d}_{chunk_idx:04d} — HierarchicalChunker 순서';
COMMENT ON COLUMN manual.documents_v2.embedding IS 'Qwen3-Embedding-8B 2000차원 (4096→2000 슬라이싱)';
COMMENT ON COLUMN manual.documents_v2.figure_refs IS
    'Supabase Storage 이미지 경로: vector/manual_images/{category}/{file_id}/page_{N:04d}_{figure_id}.png';
