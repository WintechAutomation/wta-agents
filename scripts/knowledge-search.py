"""knowledge-search.py — 질문을 임베딩하여 pgvector 유사도 검색."""

import sys
import json
import requests
import psycopg2

EMBED_URL = "http://182.224.6.147:11434/api/embed"
TOP_K = 5

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}


def embed_query(text: str) -> list[float]:
    """질문을 Qwen3-Embedding-8B로 임베딩."""
    resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": [text]}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"][0][:2000]


def search(query_embedding: list[float], top_k: int = TOP_K) -> list[dict]:
    """pgvector 코사인 유사도 검색."""
    conn = psycopg2.connect(**DB_CONFIG)
    sql = """
        SELECT
            source_file,
            chunk_index,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM knowledge.documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    emb_str = str(query_embedding)
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str, emb_str, top_k))
        rows = cur.fetchall()
    conn.close()

    results = []
    for source_file, chunk_index, content, similarity in rows:
        results.append({
            "source_file": source_file,
            "chunk_index": chunk_index,
            "content": content,
            "similarity": round(float(similarity), 4),
        })
    return results


def main():
    if len(sys.argv) < 2:
        print("사용법: python knowledge-search.py \"질문\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"[search] 질문: {query}\n")

    embedding = embed_query(query)
    results = search(embedding)

    if not results:
        print("검색 결과 없음")
        return

    for i, r in enumerate(results, 1):
        print(f"── [{i}] 유사도: {r['similarity']} | 파일: {r['source_file']} (청크 {r['chunk_index']}) ──")
        # 내용을 200자로 잘라서 표시
        content = r["content"]
        if len(content) > 300:
            content = content[:300] + "..."
        print(content)
        print()


if __name__ == "__main__":
    main()
