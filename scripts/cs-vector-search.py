"""cs-vector-search.py — CS 벡터 유사도 검색 (cs-agent 스킬 보조 스크립트).

사용법:
  py cs-vector-search.py "모터 과열 발생 시 조치 방법"
  py cs-vector-search.py "모터 과열 발생 시 조치 방법" --top 10
"""

import argparse
import json
import sys

import psycopg2
import requests

EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_DIM = 2000  # Matryoshka: 4096 → 2000 차원 축소 (cs-embed.py와 동일)
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}


def embed_query(text: str) -> list[float]:
    resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": [text]}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embeddings"][0][:EMBED_DIM]


def search(query_embedding: list[float], top_k: int) -> list[dict]:
    conn = psycopg2.connect(**DB_CONFIG)
    sql = """
        SELECT
            source_id,
            text,
            metadata,
            1 - (embedding <=> %s::vector) AS similarity
        FROM csagent.vector_embeddings
        WHERE source_type = 'cs_history'
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    emb_str = str(query_embedding)
    with conn.cursor() as cur:
        cur.execute(sql, (emb_str, emb_str, top_k))
        rows = cur.fetchall()
    conn.close()

    return [
        {
            "source_id": row[0],
            "text": row[1],
            "metadata": row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
            "similarity": round(float(row[3]), 4),
        }
        for row in rows
    ]


def main():
    parser = argparse.ArgumentParser(description="CS 벡터 검색")
    parser.add_argument("query", help="검색 질문")
    parser.add_argument("--top", type=int, default=20, help="반환 건수 (기본 20)")
    args = parser.parse_args()

    embedding = embed_query(args.query)
    results = search(embedding, args.top)

    if not results:
        print("검색 결과 없음")
        return

    print(f"[검색 결과: {len(results)}건]\n")
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        device = meta.get("project_name", "")
        customer = meta.get("customer", "")
        header = f"{device} | {customer}" if device or customer else f"CS #{r['source_id']}"
        print(f"── [{i}] 유사도: {r['similarity']} | {header} ──")
        print(r["text"])
        print()


if __name__ == "__main__":
    main()
