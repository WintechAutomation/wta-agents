"""embed-remaining.py — 임베딩 미완료 청크에 대해 임베딩만 수행.

manual.wta_documents에서 embedding IS NULL인 청크를 배치로 임베딩 후 업데이트.
"""

import sys
import time
import requests
import psycopg2

EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000  # Matryoshka: 4096 -> 2000
BATCH_SIZE = 64
EMBED_DELAY = 0.3  # 배치 간 딜레이


def load_db_password():
    with open("C:/MES/backend/.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                return line.strip().split("=", 1)[1]
    return None


def embed_texts(texts):
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(EMBED_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"Embedding error: {data}")
    return [v[:EMBED_DIM] for v in data["embeddings"]]


def main():
    conn = psycopg2.connect(
        host="localhost", port=55432, user="postgres",
        password=load_db_password(), dbname="postgres",
    )

    # 임베딩 미완료 청크 조회
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, content FROM manual.wta_documents
            WHERE embedding IS NULL AND content IS NOT NULL AND LENGTH(content) >= 20
            ORDER BY id
        """)
        rows = cur.fetchall()

    total = len(rows)
    print(f"[embed] {total} chunks to embed", flush=True)

    if total == 0:
        print("[embed] Nothing to do.", flush=True)
        conn.close()
        return

    embedded = 0
    errors = 0
    start_time = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]

        for attempt in range(3):
            try:
                embeddings = embed_texts(texts)
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  Retry {attempt+1} for batch {i}: {e}", flush=True)
                    time.sleep((attempt + 1) * 5)
                else:
                    print(f"  FAILED batch {i}: {e}", flush=True)
                    errors += len(batch)
                    embeddings = None

        if embeddings:
            with conn.cursor() as cur:
                for row_id, emb in zip(ids, embeddings):
                    cur.execute(
                        "UPDATE manual.wta_documents SET embedding = %s::vector, updated_at = now() WHERE id = %s",
                        (str(emb), row_id)
                    )
            conn.commit()
            embedded += len(batch)

        # 진행 상황 출력
        elapsed = time.time() - start_time
        pct = (i + len(batch)) / total * 100
        rate = embedded / elapsed if elapsed > 0 else 0
        remaining = (total - i - len(batch)) / rate if rate > 0 else 0
        print(f"  [{i + len(batch)}/{total}] {pct:.0f}% | {rate:.1f} chunks/s | ETA {remaining:.0f}s", flush=True)

        if i + BATCH_SIZE < total:
            time.sleep(EMBED_DELAY)

    elapsed_total = time.time() - start_time
    conn.close()
    print(f"\n[DONE] Embedded={embedded}, Errors={errors}, Time={elapsed_total:.0f}s", flush=True)


if __name__ == "__main__":
    main()
