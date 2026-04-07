-- 핵심기술개발 전용 벡터 테이블
-- 부서장 승인 완료 (2026-04-04)
-- 보안 등급: confidential (부서장 요청 시에만 접근)

CREATE TABLE manual.core_tech_documents (
    id             SERIAL PRIMARY KEY,
    title          TEXT NOT NULL DEFAULT '',
    source_file    TEXT NOT NULL,
    file_hash      TEXT NOT NULL,
    category       TEXT NOT NULL DEFAULT '',
    project_code   TEXT,
    chunk_index    INTEGER NOT NULL,
    chunk_type     TEXT NOT NULL DEFAULT 'text',
    page_number    INTEGER,
    content        TEXT NOT NULL,
    embedding      vector(2000),
    metadata       JSONB DEFAULT '{}',
    security_level TEXT NOT NULL DEFAULT 'confidential',
    created_by     TEXT NOT NULL DEFAULT 'system',
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT core_tech_docs_source_chunk_key UNIQUE (source_file, chunk_index),
    CONSTRAINT core_tech_docs_security_level_check CHECK (security_level IN ('confidential', 'top_secret'))
);

-- 벡터 유사도 검색 (HNSW, cosine)
CREATE INDEX idx_core_tech_docs_embedding
    ON manual.core_tech_documents
    USING hnsw (embedding vector_cosine_ops);

-- 파일/카테고리/보안등급 필터링
CREATE INDEX idx_core_tech_docs_source_file
    ON manual.core_tech_documents (source_file);

CREATE INDEX idx_core_tech_docs_category
    ON manual.core_tech_documents (category);

CREATE INDEX idx_core_tech_docs_security_level
    ON manual.core_tech_documents (security_level);

-- updated_at 자동 갱신 함수
CREATE OR REPLACE FUNCTION manual.update_core_tech_docs_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- updated_at 자동 갱신 트리거
CREATE TRIGGER trg_core_tech_docs_updated_at
    BEFORE UPDATE ON manual.core_tech_documents
    FOR EACH ROW EXECUTE FUNCTION manual.update_core_tech_docs_updated_at();
