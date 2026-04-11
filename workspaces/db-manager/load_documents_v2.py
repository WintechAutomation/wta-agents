"""
manual.documents_v2 JSONL bulk loader
docs-agent가 생성한 JSONL → manual.documents_v2 upsert.

입력 JSONL 1줄 스키마 (docs-agent 약속):
{
  "file_id": "1_robot_a3f8d21b9e04",
  "chunk_id": "0012_0003",
  "category": "1_robot",
  "mfr": "Mitsubishi",
  "model": "BFP-A8586-D",
  "doctype": "manual",
  "lang": "ko",
  "section_path": ["3. 보수", "3.1 정기 점검"],
  "page_start": 12, "page_end": 12,
  "content": "...",
  "tokens": 487,
  "source_hash": "e1a9...",
  "embedding": [0.123, -0.045, ...],   // 2000차원 float
  "figure_refs": [{"figure_id":"fig_012_01","page":12,"storage_path":"manual_images/...","caption":"..."}],
  "table_refs":  [],
  "inline_refs": []
}

사용:
    python load_documents_v2.py path/to/parsed.jsonl
    python load_documents_v2.py --dry-run path/to/parsed.jsonl
    python load_documents_v2.py --batch 500 file1.jsonl file2.jsonl
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Iterable, List, Dict, Any

import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

EMBED_DIM = 2000

UPSERT_SQL = """
INSERT INTO manual.documents_v2
    (file_id, chunk_id, category, mfr, model, doctype, lang,
     section_path, page_start, page_end, content, tokens, source_hash,
     embedding, figure_refs, table_refs, inline_refs)
VALUES %s
ON CONFLICT (file_id, chunk_id) DO UPDATE SET
    category     = EXCLUDED.category,
    mfr          = EXCLUDED.mfr,
    model        = EXCLUDED.model,
    doctype      = EXCLUDED.doctype,
    lang         = EXCLUDED.lang,
    section_path = EXCLUDED.section_path,
    page_start   = EXCLUDED.page_start,
    page_end     = EXCLUDED.page_end,
    content      = EXCLUDED.content,
    tokens       = EXCLUDED.tokens,
    source_hash  = EXCLUDED.source_hash,
    embedding    = EXCLUDED.embedding,
    figure_refs  = EXCLUDED.figure_refs,
    table_refs   = EXCLUDED.table_refs,
    inline_refs  = EXCLUDED.inline_refs
"""


def _vector_literal(vec: List[float]) -> str:
    """pgvector 리터럴 형식 '[v1,v2,...]'"""
    if len(vec) != EMBED_DIM:
        raise ValueError(f"embedding dim {len(vec)} != {EMBED_DIM}")
    # 부동소수점 낭비 줄이려 g 포맷
    return "[" + ",".join(format(float(x), ".6g") for x in vec) + "]"


def _row_tuple(rec: Dict[str, Any]) -> tuple:
    required = ["file_id", "chunk_id", "category", "content", "embedding"]
    for k in required:
        if k not in rec or rec[k] is None:
            raise ValueError(f"missing required field: {k}")

    return (
        rec["file_id"],
        rec["chunk_id"],
        rec["category"],
        rec.get("mfr"),
        rec.get("model"),
        rec.get("doctype"),
        rec.get("lang"),
        psycopg2.extras.Json(rec.get("section_path")) if rec.get("section_path") is not None else None,
        rec.get("page_start"),
        rec.get("page_end"),
        rec["content"],
        rec.get("tokens"),
        rec.get("source_hash"),
        _vector_literal(rec["embedding"]),
        psycopg2.extras.Json(rec.get("figure_refs")) if rec.get("figure_refs") is not None else None,
        psycopg2.extras.Json(rec.get("table_refs"))  if rec.get("table_refs")  is not None else None,
        psycopg2.extras.Json(rec.get("inline_refs")) if rec.get("inline_refs") is not None else None,
    )


def iter_jsonl(paths: List[str]) -> Iterable[Dict[str, Any]]:
    for p in paths:
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
        with open(p, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"[WARN] {p}:{lineno} JSON parse failed: {e}", file=sys.stderr)


def load(paths: List[str], batch_size: int = 500, dry_run: bool = False) -> Dict[str, Any]:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    total = 0
    batch: List[tuple] = []
    errors = 0
    t0 = time.time()

    try:
        for rec in iter_jsonl(paths):
            try:
                batch.append(_row_tuple(rec))
            except Exception as e:
                errors += 1
                print(f"[WARN] row skip: {e}", file=sys.stderr)
                continue

            if len(batch) >= batch_size:
                if not dry_run:
                    psycopg2.extras.execute_values(cur, UPSERT_SQL, batch, page_size=batch_size)
                    conn.commit()
                total += len(batch)
                print(f"[LOAD] committed {total} rows ({time.time()-t0:.1f}s)")
                batch.clear()

        if batch:
            if not dry_run:
                psycopg2.extras.execute_values(cur, UPSERT_SQL, batch, page_size=len(batch))
                conn.commit()
            total += len(batch)
            print(f"[LOAD] committed {total} rows ({time.time()-t0:.1f}s)")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {
        "loaded": total,
        "errors": errors,
        "elapsed_sec": round(time.time() - t0, 2),
        "dry_run": dry_run,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="JSONL files")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    result = load(args.paths, batch_size=args.batch, dry_run=args.dry_run)
    print("\n=== DONE ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
