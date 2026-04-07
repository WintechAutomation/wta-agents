"""qc-embed.py — 출하검사 체크리스트 항목 임베딩 파이프라인.

JSON으로 추출된 장비별 체크리스트 항목을 임베딩하여 manual.qc_documents에 저장.

실행:
  python qc-embed.py            # 전체 임베딩 (신규만)
  python qc-embed.py --full     # 전체 재임베딩
  python qc-embed.py --dry-run  # 텍스트 생성만 확인 (임베딩 X)
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
EMBED_BATCH = 32
SOURCE_JSON = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "qc_checklists", "checklist_items_full.json")
)

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

logging.basicConfig(
    level=logging.INFO,
    format="[qc-embed] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("qc-embed")


# 폴더명 → 표준 장비명 매핑
MACHINE_NAME_MAP = {
    "1. Press Handler": "Press Handler",
    "2. Sintering Machine": "Sintering Machine",
    "3. Grinding Handler": "Grinding Handler",
    "4. Honing Handler": "Honing Handler",
    "5. CVD Machine": "CVD Machine",
    "6. PVD Machine": "PVD Machine",
    "7. Insert Inspection": "Insert Inspection",
    "8. 호닝형상 검사기": "호닝형상 검사기",
    "9. Packing Machine": "Packing Machine",
    "10. Labelling Machine": "Labelling Machine",
    "11. Lazer Marking Machine": "Laser Marking Machine",
    "12. Repalleting": "Repalleting",
    "13. 마스크 자동기": "마스크 자동기",
    "14. CBN Machine": "CBN Machine",
}


def load_checklist_records() -> list[dict]:
    """JSON 파일에서 체크리스트 항목을 로드하여 레코드 목록 반환."""
    with open(SOURCE_JSON, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for folder_name, items in data.items():
        if not items:
            continue
        machine_type = MACHINE_NAME_MAP.get(folder_name, folder_name)
        for item in items:
            if not item.get("item_name"):
                continue
            records.append({
                "machine_type": machine_type,
                "category": item.get("category", ""),
                "item_name": item["item_name"],
                "specification": item.get("specification", ""),
                "remark": item.get("remark", ""),
                "source_file": item.get("source_file", ""),
            })
    return records


def build_text(record: dict) -> str:
    """체크리스트 항목을 검색용 텍스트로 변환."""
    parts = [
        f"장비: {record['machine_type']}",
        f"검사 분류: {record['category']}" if record.get("category") else "",
        f"검사 항목: {record['item_name']}",
        f"검사 기준: {record['specification']}" if record.get("specification") else "",
        f"비고: {record['remark']}" if record.get("remark") else "",
    ]
    return "\n".join(p for p in parts if p)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Ollama Qwen3 임베딩 서버에 배치 임베딩 요청."""
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(EMBED_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"임베딩 응답 오류: {data}")
    return [v[:EMBED_DIM] for v in data["embeddings"]]


def fetch_existing_items(conn) -> set[str]:
    """이미 임베딩된 항목의 고유키 집합 반환 (source_file|chunk_index)."""
    with conn.cursor() as cur:
        cur.execute("SELECT source_file, chunk_index FROM manual.qc_documents WHERE source_file IS NOT NULL")
        return {f"{r[0]}|{r[1]}" for r in cur.fetchall()}


def upsert_records(conn, rows: list[dict]) -> None:
    """manual.qc_documents 테이블에 INSERT."""
    sql = """
        INSERT INTO manual.qc_documents
            (machine_type, category, item_name, specification, source_file, chunk_index,
             content, metadata, embedding, created_at)
        VALUES %s
    """
    template = (
        "(%(machine_type)s, %(category)s, %(item_name)s, %(specification)s, %(source_file)s, "
        "%(chunk_index)s, %(content)s, %(metadata)s::jsonb, %(embedding)s::vector, now())"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, template=template, page_size=50)
    conn.commit()


def truncate_table(conn) -> None:
    """전체 재임베딩 전 테이블 비우기."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE manual.qc_documents")
    conn.commit()
    log.info("테이블 비우기 완료")


def main():
    parser = argparse.ArgumentParser(description="출하검사 체크리스트 임베딩")
    parser.add_argument("--full", action="store_true", help="전체 재임베딩")
    parser.add_argument("--dry-run", action="store_true", help="텍스트 생성만 확인")
    args = parser.parse_args()

    log.info(f"시작 (모드: {'전체' if args.full else ('dry-run' if args.dry_run else '증분')})")

    records = load_checklist_records()
    log.info(f"JSON 로드: {len(records)}개 항목")

    if args.dry_run:
        for r in records[:5]:
            print(f"--- {r['machine_type']} / {r['item_name']} ---")
            print(build_text(r))
            print()
        log.info("dry-run 완료")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        # 각 레코드에 chunk_index 부여 (machine_type 기준 순번)
        machine_counters: dict[str, int] = {}
        for r in records:
            mt = r["machine_type"]
            machine_counters[mt] = machine_counters.get(mt, 0) + 1
            r["chunk_index"] = machine_counters[mt]
            r["source_file"] = r.get("source_file") or f"checklist_{mt}"

        # 전체 모드: 테이블 비우고 재삽입 / 증분 모드: 이미 임베딩된 항목 제외
        if args.full:
            truncate_table(conn)
        else:
            existing = fetch_existing_items(conn)
            records = [r for r in records if f"{r['source_file']}|{r['chunk_index']}" not in existing]
            log.info(f"신규 항목: {len(records)}개 (기존 {len(existing)}개 제외)")

        if not records:
            log.info("임베딩할 항목 없음. 종료.")
            return

        # 배치 임베딩
        total = len(records)
        done = 0
        for i in range(0, total, EMBED_BATCH):
            batch = records[i:i + EMBED_BATCH]
            texts = [build_text(r) for r in batch]

            try:
                embeddings = embed_texts(texts)
            except Exception as e:
                log.error(f"임베딩 실패 (배치 {i}~{i+len(batch)}): {e}")
                continue

            rows = []
            for r, emb in zip(batch, embeddings):
                rows.append({
                    **r,
                    "content": build_text(r),
                    "metadata": json.dumps({"remark": r.get("remark", "")}, ensure_ascii=False),
                    "embedding": emb,
                })

            upsert_records(conn, rows)
            done += len(batch)
            log.info(f"진행: {done}/{total} ({done*100//total}%)")
            time.sleep(0.3)

        log.info(f"완료: {done}개 임베딩 저장")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
