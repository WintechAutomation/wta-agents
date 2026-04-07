"""manual-search.py — 매뉴얼 벡터 검색 CLI.

임베딩된 매뉴얼에서 유사 청크를 검색.

실행:
  python manual-search.py "서보 파라미터 설정 방법"
  python manual-search.py "배선도 전원 연결" --category 1_robot
  python manual-search.py "에러코드 E-01" --top-k 5 --type table
"""

import argparse
import json
import sys

import psycopg2
import requests

EMBED_URL = "http://182.224.6.147:11434/api/embed"

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}


EMBED_DIM = 2000  # DB에 저장된 Matryoshka truncation 차원


def embed_query(query: str) -> list[float]:
    """쿼리 텍스트 임베딩 (DB 차원에 맞춰 truncate)."""
    resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": [query]}, timeout=30)
    resp.raise_for_status()
    vec = resp.json()["embeddings"][0]
    return vec[:EMBED_DIM]


def search(query: str, top_k: int = 5, category: str | None = None,
           chunk_type: str | None = None) -> list[dict]:
    """pgvector 코사인 유사도 검색."""
    embedding = embed_query(query)

    conditions = []
    params = [str(embedding)]

    if category:
        conditions.append("category = %s")
        params.append(category)
    if chunk_type:
        conditions.append("chunk_type = %s")
        params.append(chunk_type)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT source_file, category, chunk_type, page_number, content, image_url, metadata,
               1 - (embedding <=> %s::vector) AS similarity
        FROM manual.documents
        {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    params.append(str(embedding))
    params.append(top_k)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="매뉴얼 벡터 검색")
    parser.add_argument("query", help="검색 쿼리")
    parser.add_argument("--top-k", type=int, default=5, help="결과 수 (기본: 5)")
    parser.add_argument("--category", help="카테고리 필터 (예: 1_robot)")
    parser.add_argument("--type", dest="chunk_type", choices=["text", "table", "image_caption"],
                        help="청크 타입 필터")
    args = parser.parse_args()

    results = search(args.query, args.top_k, args.category, args.chunk_type)

    if not results:
        print("검색 결과 없음")
        return

    for i, r in enumerate(results, 1):
        sim = r["similarity"]
        print(f"\n{'='*60}")
        print(f"[{i}] {r['source_file']} (p.{r['page_number']}) — {r['chunk_type']} — 유사도: {sim:.4f}")
        print(f"    카테고리: {r['category']}")
        if r.get("image_url"):
            print(f"    이미지: {r['image_url']}")
        print(f"-" * 60)
        content = r["content"]
        if len(content) > 500:
            content = content[:500] + "..."
        print(content)


if __name__ == "__main__":
    main()
