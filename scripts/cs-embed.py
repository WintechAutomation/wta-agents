"""cs-embed.py — CS 이력 데이터를 pgvector에 임베딩하여 저장.

실행:
  python cs-embed.py            # 전체 동기화 (신규/변경 건만 upsert)
  python cs-embed.py --full     # 전체 재임베딩
"""

import argparse
import json
import logging
import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values
import requests

# ── 설정 ──
EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000
EMBED_BATCH = 128
SOURCE_TYPE = "cs_history"

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

logging.basicConfig(
    level=logging.INFO,
    format="[cs-embed] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cs-embed")


def fetch_cs_records(conn, full: bool) -> list[dict]:
    """임베딩 대상 CS 이력 조회.

    증분 모드: vector_embeddings에 없는 레코드만 조회.
    전체 모드: 모든 레코드 조회.
    """
    if full:
        sql = """
            SELECT
                h.id::text,
                h.title,
                h.symptom_and_cause,
                h.action_result,
                h.handling_method,
                h.free_paid_type,
                s.project_name,
                s.customer,
                s.domestic_overseas
            FROM csagent.cs_history h
            LEFT JOIN shipment_table s ON s.id = h.shipment_id
            WHERE h.symptom_and_cause IS NOT NULL
              AND h.action_result IS NOT NULL
              AND trim(h.symptom_and_cause) != ''
              AND trim(h.action_result) != ''
            ORDER BY h.cs_received_at DESC
        """
    else:
        sql = """
            SELECT
                h.id::text,
                h.title,
                h.symptom_and_cause,
                h.action_result,
                h.handling_method,
                h.free_paid_type,
                s.project_name,
                s.customer,
                s.domestic_overseas
            FROM csagent.cs_history h
            LEFT JOIN shipment_table s ON s.id = h.shipment_id
            LEFT JOIN csagent.vector_embeddings ve
                ON ve.source_type = 'cs_history' AND ve.source_id = h.id::text
            WHERE h.symptom_and_cause IS NOT NULL
              AND h.action_result IS NOT NULL
              AND trim(h.symptom_and_cause) != ''
              AND trim(h.action_result) != ''
              AND ve.id IS NULL
            ORDER BY h.cs_received_at DESC
        """

    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def build_text(record: dict) -> str:
    """CS 이력 레코드를 검색용 텍스트로 변환."""
    parts = []

    if record.get("project_name"):
        parts.append(f"장비: {record['project_name']}")
    if record.get("customer"):
        parts.append(f"고객사: {record['customer']}")
    if record.get("title"):
        parts.append(f"건명: {record['title']}")
    if record.get("handling_method"):
        parts.append(f"조치방법: {record['handling_method']}")
    if record.get("free_paid_type"):
        type_label = {"free": "무상", "paid": "유상"}.get(record["free_paid_type"], record["free_paid_type"])
        parts.append(f"유무상: {type_label}")

    parts.append(f"증상 및 원인: {record['symptom_and_cause']}")
    parts.append(f"조치 결과: {record['action_result']}")

    return "\n".join(parts)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Ollama Qwen3 임베딩 서버에 배치 임베딩 요청."""
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(EMBED_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"임베딩 응답 오류: {data}")
    # Matryoshka: 4096차원 → 2000차원으로 잘라서 반환
    return [v[:EMBED_DIM] for v in data["embeddings"]]


def upsert_embeddings(conn, rows: list[dict]) -> None:
    """vector_embeddings 테이블에 upsert."""
    sql = """
        INSERT INTO csagent.vector_embeddings (id, source_type, source_id, text, metadata, embedding, created_at)
        VALUES %s
        ON CONFLICT (id)
        DO UPDATE SET
            text = EXCLUDED.text,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            created_at = now()
    """
    template = "(%(id)s, %(source_type)s, %(source_id)s, %(text)s, %(metadata)s::jsonb, %(embedding)s::vector, now())"
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, template=template, page_size=50)
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="CS 이력 임베딩 배치")
    parser.add_argument("--full", action="store_true", help="전체 재임베딩 (기존 upsert)")
    args = parser.parse_args()

    log.info(f"시작 (모드: {'전체' if args.full else '증분'})")

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        records = fetch_cs_records(conn, full=args.full)
        log.info(f"대상 레코드: {len(records)}건")

        if not records:
            log.info("임베딩 대상 없음 — 종료")
            return

        total = 0
        for i in range(0, len(records), EMBED_BATCH):
            batch = records[i:i + EMBED_BATCH]
            texts = [build_text(r) for r in batch]

            try:
                embeddings = embed_texts(texts)
            except Exception as e:
                log.error(f"임베딩 실패 (배치 {i}~{i+len(batch)}): {e}")
                continue

            rows = []
            for record, text, emb in zip(batch, texts, embeddings):
                rows.append({
                    "id": f"cs_history_{record['id']}",
                    "source_type": SOURCE_TYPE,
                    "source_id": record["id"],
                    "text": text,
                    "metadata": json.dumps({
                        "cs_id": record["id"],
                        "title": record.get("title", ""),
                        "project_name": record.get("project_name", ""),
                        "customer": record.get("customer", ""),
                        "handling_method": record.get("handling_method", ""),
                        "free_paid_type": record.get("free_paid_type", ""),
                    }, ensure_ascii=False),
                    "embedding": str(emb),
                })

            upsert_embeddings(conn, rows)
            total += len(rows)
            log.info(f"  {i + len(batch)}/{len(records)} 처리 완료")

        log.info(f"임베딩 완료: 총 {total}건")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
