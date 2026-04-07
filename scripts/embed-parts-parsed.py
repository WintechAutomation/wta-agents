"""parts-parsed/ MD 파일을 smart_chunk_markdown으로 청킹 + 임베딩하는 스크립트.

사용법:
  python embed-parts-parsed.py [--limit N] [--dry-run]
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import hashlib
import time
import re
import logging
import argparse
from pathlib import Path
from collections import Counter

import signal
import traceback
import requests
import psycopg2

def _signal_handler(signum, frame):
    logging.getLogger(__name__).error(f"Signal {signum} received! Traceback:\n{''.join(traceback.format_stack(frame))}")
    sys.exit(1)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# -- 설정 --
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARTS_PARSED_DIR = os.path.join(BASE_DIR, "data", "parts-parsed")
DB_TABLE = "manual.documents"

# Ollama 임베딩
OLLAMA_URL = "http://182.224.6.147:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000
EMBED_BATCH = 8
EMBED_DELAY = 0.3

# 청킹 설정
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TABLE_MAX_SIZE = 2000
MIN_CHUNK_LEN = 50

# DB 설정 (batch-parse-docling.py와 동일)
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

# 로깅
logging.basicConfig(
    format="[parts-embed] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# -- 청킹 함수 (batch-parse-docling.py에서 복사) --
def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        chunks.append(chunk)
        start += size - overlap
    return chunks


def _split_large_table(table_md, max_size=TABLE_MAX_SIZE):
    lines = table_md.split("\n")
    if len(lines) < 3:
        return [table_md]
    header = lines[0]
    separator = lines[1]
    data_lines = lines[2:]
    header_block = f"{header}\n{separator}"
    header_len = len(header_block) + 1
    sub_tables = []
    current_lines = []
    current_len = header_len
    for line in data_lines:
        line_len = len(line) + 1
        if current_len + line_len > max_size and current_lines:
            sub_tables.append(header_block + "\n" + "\n".join(current_lines))
            current_lines = []
            current_len = header_len
        current_lines.append(line)
        current_len += line_len
    if current_lines:
        sub_tables.append(header_block + "\n" + "\n".join(current_lines))
    return sub_tables if sub_tables else [table_md]


def _merge_short_chunks(chunks, min_len=MIN_CHUNK_LEN, max_len=CHUNK_SIZE):
    if not chunks:
        return chunks
    merged = []
    buffer = ""
    for c in chunks:
        if len(c) < min_len:
            buffer = (buffer + "\n\n" + c).strip() if buffer else c
        else:
            if buffer:
                combined = (buffer + "\n\n" + c).strip()
                if len(combined) <= max_len:
                    merged.append(combined)
                    buffer = ""
                else:
                    merged.append(buffer)
                    merged.append(c)
                    buffer = ""
            else:
                merged.append(c)
    if buffer:
        if merged:
            combined = (merged[-1] + "\n\n" + buffer).strip()
            if len(combined) <= max_len:
                merged[-1] = combined
            else:
                merged.append(buffer)
        else:
            merged.append(buffer)
    return merged


def smart_chunk_markdown(md_text, source_file=""):
    chunks = []
    current_heading = ""
    sections = re.split(r"(?=^#{1,4}\s)", md_text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines = section.split("\n")
        first_line = lines[0].strip()
        heading_match = re.match(r"^#{1,4}\s+(.+)", first_line)
        if heading_match:
            current_heading = heading_match.group(1).strip()

        text_buffer = []
        table_buffer = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            is_table_line = stripped.startswith("|") and stripped.endswith("|")
            if is_table_line:
                if text_buffer and not in_table:
                    text_block = "\n".join(text_buffer).strip()
                    if text_block:
                        for tc in chunk_text(text_block):
                            chunks.append({"content": tc.strip(), "chunk_type": "text", "heading": current_heading, "page_number": None})
                    text_buffer = []
                table_buffer.append(line)
                in_table = True
            else:
                if in_table and table_buffer:
                    table_md = "\n".join(table_buffer).strip()
                    if len(table_md) > TABLE_MAX_SIZE:
                        for sub in _split_large_table(table_md):
                            chunks.append({"content": sub, "chunk_type": "table", "heading": current_heading, "page_number": None})
                    elif table_md:
                        chunks.append({"content": table_md, "chunk_type": "table", "heading": current_heading, "page_number": None})
                    table_buffer = []
                    in_table = False
                text_buffer.append(line)

        if table_buffer:
            table_md = "\n".join(table_buffer).strip()
            if len(table_md) > TABLE_MAX_SIZE:
                for sub in _split_large_table(table_md):
                    chunks.append({"content": sub, "chunk_type": "table", "heading": current_heading, "page_number": None})
            elif table_md:
                chunks.append({"content": table_md, "chunk_type": "table", "heading": current_heading, "page_number": None})
        if text_buffer:
            text_block = "\n".join(text_buffer).strip()
            if text_block:
                for tc in chunk_text(text_block):
                    chunks.append({"content": tc.strip(), "chunk_type": "text", "heading": current_heading, "page_number": None})

    # 짧은 텍스트 청크 병합
    text_chunks = [c for c in chunks if c["chunk_type"] == "text"]
    table_chunks = [c for c in chunks if c["chunk_type"] != "text"]
    text_contents = [c["content"] for c in text_chunks]
    merged_contents = _merge_short_chunks(text_contents)

    merged_text_chunks = []
    heading_map = {c["content"]: c["heading"] for c in text_chunks}
    for mc in merged_contents:
        heading = heading_map.get(mc, "")
        if not heading:
            for tc in text_chunks:
                if tc["content"] in mc:
                    heading = tc["heading"]
                    break
        merged_text_chunks.append({"content": mc, "chunk_type": "text", "heading": heading, "page_number": None})

    final_chunks = []
    text_iter = iter(merged_text_chunks)
    table_iter = iter(table_chunks)
    next_text = next(text_iter, None)
    next_table = next(table_iter, None)
    for orig in chunks:
        if orig["chunk_type"] == "text" and next_text:
            final_chunks.append(next_text)
            next_text = next(text_iter, None)
        elif orig["chunk_type"] != "text" and next_table:
            final_chunks.append(next_table)
            next_table = next(table_iter, None)
    while next_text:
        final_chunks.append(next_text)
        next_text = next(text_iter, None)
    while next_table:
        final_chunks.append(next_table)
        next_table = next(table_iter, None)

    # Contextual prefix + 필터
    doc_name = os.path.splitext(os.path.basename(source_file))[0] if source_file else ""
    result = []
    for c in final_chunks:
        content = c["content"].strip()
        if not content or len(content) < MIN_CHUNK_LEN:
            continue
        prefix_parts = []
        if doc_name:
            prefix_parts.append(f"문서: {doc_name}")
        if c["heading"]:
            prefix_parts.append(f"섹션: {c['heading']}")
        if prefix_parts:
            content = " > ".join(prefix_parts) + "\n\n" + content
        c["content"] = content
        result.append(c)
    return result


# -- 임베딩 --
def embed_texts(texts):
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"임베딩 응답 오류: {data}")
    return [v[:EMBED_DIM] for v in data["embeddings"]]


# -- DB --
def ensure_schema(conn, table_name):
    schema = table_name.split(".")[0] if "." in table_name else "public"
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            source_file TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            category TEXT DEFAULT '',
            chunk_index INTEGER DEFAULT 0,
            chunk_type TEXT DEFAULT 'text',
            page_number INTEGER,
            content TEXT NOT NULL,
            image_url TEXT DEFAULT '',
            pdf_url TEXT DEFAULT '',
            metadata JSONB DEFAULT '{{}}'::jsonb,
            embedding vector({EMBED_DIM})
        )""")
        cur.execute(f"""CREATE INDEX IF NOT EXISTS idx_{table_name.replace('.','_')}_embedding
            ON {table_name} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)""")
    conn.commit()


def upsert_chunks(conn, chunks, table_name):
    with conn.cursor() as cur:
        for c in chunks:
            cur.execute(f"""INSERT INTO {table_name}
                (source_file, file_hash, category, chunk_index, chunk_type,
                 page_number, content, image_url, pdf_url, metadata, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                ON CONFLICT (source_file, chunk_index) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    file_hash = EXCLUDED.file_hash,
                    category = EXCLUDED.category,
                    metadata = EXCLUDED.metadata""",
                (c["source_file"], c["file_hash"], c["category"],
                 c["chunk_index"], c["chunk_type"], c.get("page_number"),
                 c["content"], c.get("image_url",""), c.get("pdf_url",""),
                 c.get("metadata","{}"), c.get("embedding")))
    conn.commit()


# -- Main --
def main():
    parser = argparse.ArgumentParser(description="부품매뉴얼 MD 임베딩 파이프라인")
    parser.add_argument("--limit", type=int, help="처리할 파일 수 제한")
    parser.add_argument("--dry-run", action="store_true", help="분석만 (DB 저장 안 ���)")
    parser.add_argument("--category", help="특정 카테고리만 처리")
    parser.add_argument("--skip-existing", action="store_true", help="DB에 이미 있는 파일 건너뛰기")
    parser.add_argument("--reverse", action="store_true", help="파일 역순 처리 (병렬 실행 시 충돌 최소화)")
    args = parser.parse_args()

    # MD 파일 수집
    md_files = []
    for cat_dir in sorted(Path(PARTS_PARSED_DIR).iterdir()):
        if not cat_dir.is_dir():
            continue
        if args.category and cat_dir.name != args.category:
            continue
        for md_file in sorted(cat_dir.glob("*.md")):
            md_files.append((str(md_file), cat_dir.name))

    if args.reverse:
        md_files.reverse()

    if args.limit:
        md_files = md_files[:args.limit]

    log.info(f"대상: {len(md_files)}개 MD 파일 → {DB_TABLE}")

    if args.dry_run:
        total_chunks = 0
        for i, (md_path, category) in enumerate(md_files):
            filename = os.path.basename(md_path)
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            chunks = smart_chunk_markdown(md_content, filename)
            types = Counter(c["chunk_type"] for c in chunks)
            log.info(f"  [{i+1}/{len(md_files)}] {filename}: {len(chunks)} chunks {dict(types)}")
            total_chunks += len(chunks)
        log.info(f"DRY-RUN 완료: {len(md_files)}개 파일, {total_chunks}개 청크")
        return

    # DB 연결
    conn = psycopg2.connect(**DB_CONFIG)
    ensure_schema(conn, DB_TABLE)

    processed = 0
    total_embedded = 0
    errors = 0

    for i, (md_path, category) in enumerate(md_files):
        filename = os.path.basename(md_path)
        source_file = filename.replace(".md", ".pdf")

        log.info(f"  [{i+1}/{len(md_files)}] {filename}")

        try:
            # DB 연결 상태 확인/재연결
            try:
                conn.cursor().execute("SELECT 1")
            except Exception:
                log.warning("    DB reconnect...")
                try:
                    conn.close()
                except Exception:
                    pass
                conn = psycopg2.connect(**DB_CONFIG)

            # --skip-existing: DB에 이미 레코드가 있으면 건너뛰기
            if args.skip_existing:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {DB_TABLE} WHERE source_file=%s", (source_file,))
                    cnt = cur.fetchone()[0]
                    if cnt > 0:
                        log.info(f"    Skip (exists: {cnt} records)")
                        processed += 1
                        continue

            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()

            if not md_content or len(md_content) < 50:
                log.warning(f"    Skip (too short): {filename}")
                continue

            file_hash = hashlib.sha256(md_content.encode()).hexdigest()[:16]

            # 기존 레코드 삭제
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {DB_TABLE} WHERE source_file=%s", (source_file,))
                if cur.rowcount > 0:
                    log.info(f"    Deleted {cur.rowcount} old records")
            conn.commit()

            # 청킹
            smart_chunks = smart_chunk_markdown(md_content, source_file)
            if not smart_chunks:
                log.warning(f"    No chunks: {filename}")
                errors += 1
                continue

            chunks_data = []
            for chunk_idx, sc in enumerate(smart_chunks):
                chunks_data.append({
                    "source_file": source_file,
                    "file_hash": file_hash,
                    "category": category,
                    "chunk_index": chunk_idx,
                    "chunk_type": sc["chunk_type"],
                    "page_number": sc.get("page_number"),
                    "content": sc["content"],
                    "image_url": "",
                    "pdf_url": "",
                    "metadata": json.dumps({
                        "category": category,
                        "type": sc["chunk_type"],
                        "heading": sc.get("heading", ""),
                    }, ensure_ascii=False),
                })

            # 임베딩
            embeddable = [c for c in chunks_data if c["content"] and len(c["content"].strip()) >= 20]
            log.info(f"    Chunks: {len(embeddable)} embeddable")
            all_embeddings = []
            embed_ok = True

            for bi in range(0, len(embeddable), EMBED_BATCH):
                batch = embeddable[bi:bi + EMBED_BATCH]
                texts = [c["content"] for c in batch]
                for attempt in range(3):
                    try:
                        all_embeddings.extend(embed_texts(texts))
                        break
                    except Exception as e:
                        if attempt < 2:
                            log.warning(f"    Embed retry {attempt+1}: {e}")
                            time.sleep((attempt + 1) * 5)
                        else:
                            log.error(f"    Embedding failed: {filename} batch {bi}: {e}")
                            embed_ok = False
                if not embed_ok:
                    break
                if bi + EMBED_BATCH < len(embeddable):
                    time.sleep(EMBED_DELAY)

            if not embed_ok:
                errors += 1
                continue

            for chunk, emb in zip(embeddable, all_embeddings):
                chunk["embedding"] = str(emb)

            # DB 저장
            for bi in range(0, len(embeddable), 50):
                upsert_chunks(conn, embeddable[bi:bi + 50], DB_TABLE)
            total_embedded += len(embeddable)
            processed += 1
            log.info(f"    OK: {len(embeddable)} chunks embedded")

        except Exception as e:
            log.error(f"    FATAL error on {filename}: {e}")
            errors += 1
            try:
                conn.rollback()
            except Exception:
                pass

    conn.close()
    log.info(f"\n완료: {processed}개 파일, {total_embedded}개 청크, {errors}��� 에러")


if __name__ == "__main__":
    main()
