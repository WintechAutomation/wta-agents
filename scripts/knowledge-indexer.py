"""knowledge-indexer.py — sales-agent knowledge 폴더의 .md 파일을 청크 분할 후 pgvector에 저장."""

import os
import glob
import json
import re
import sys
import requests
import psycopg2
from psycopg2.extras import execute_values

# ── 설정 ──
KNOWLEDGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "agents", "sales-agent", "knowledge"))
EMBED_URL = "http://182.224.6.147:11434/api/embed"
CHUNK_SIZE = 500  # 글자 수 기준
CHUNK_OVERLAP = 50

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}


def read_md_files(directory: str) -> list[dict]:
    """knowledge 폴더의 모든 .md 파일을 읽어 반환."""
    files = []
    for path in sorted(glob.glob(os.path.join(directory, "**", "*.md"), recursive=True)):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            continue
        # source_file: knowledge/ 기준 상대경로
        rel = os.path.relpath(path, directory).replace("\\", "/")
        files.append({"source_file": rel, "content": content})
    return files


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 size 글자 내외로 분할. 문단/문장 경계 우선."""
    # 문단 단위로 먼저 분리
    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 현재 청크 + 문단이 size 이내면 합침
        if len(current) + len(para) + 1 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # 문단 자체가 size 초과면 강제 분할
            if len(para) > size:
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
            else:
                current = para
                continue
            current = ""

    if current:
        chunks.append(current)

    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Qwen3-Embedding-8B 임베딩 서버에 텍스트 배치 요청."""
    resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": texts}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return [v[:2000] for v in data["embeddings"]]


def upsert_chunks(conn, rows: list[tuple]):
    """source_file + chunk_index 기준 upsert."""
    sql = """
        INSERT INTO knowledge.documents (source_file, chunk_index, content, metadata, embedding)
        VALUES %s
        ON CONFLICT (source_file, chunk_index)
        DO UPDATE SET
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            updated_at = now()
    """
    # psycopg2 execute_values 용 템플릿
    template = "(%(source_file)s, %(chunk_index)s, %(content)s, %(metadata)s::jsonb, %(embedding)s::vector)"
    with conn.cursor() as cur:
        execute_values(
            cur, sql, rows,
            template=template,
            page_size=50,
        )
    conn.commit()


def cleanup_stale(conn, source_file: str, max_chunk_index: int):
    """파일 내용이 줄었을 때 이전 청크 삭제."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM knowledge.documents WHERE source_file = %s AND chunk_index > %s",
            (source_file, max_chunk_index),
        )
    conn.commit()


def main():
    print(f"[indexer] knowledge 디렉토리: {KNOWLEDGE_DIR}")
    files = read_md_files(KNOWLEDGE_DIR)
    print(f"[indexer] {len(files)}개 파일 발견")

    if not files:
        print("[indexer] 인덱싱할 파일 없음")
        return

    conn = psycopg2.connect(**DB_CONFIG)

    total_chunks = 0
    for file_info in files:
        source = file_info["source_file"]
        chunks = chunk_text(file_info["content"])
        if not chunks:
            continue

        print(f"  {source}: {len(chunks)}개 청크", end=" ... ")

        # 임베딩
        embeddings = embed_texts(chunks)

        # upsert 행 구성
        rows = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            rows.append({
                "source_file": source,
                "chunk_index": i,
                "content": chunk,
                "metadata": json.dumps({"source_file": source, "chunk_index": i}, ensure_ascii=False),
                "embedding": str(emb),
            })

        upsert_chunks(conn, rows)
        cleanup_stale(conn, source, len(chunks) - 1)
        total_chunks += len(chunks)
        print("완료")

    conn.close()
    print(f"\n[indexer] 총 {total_chunks}개 청크 인덱싱 완료")


if __name__ == "__main__":
    main()
