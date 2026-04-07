"""parse-docx-only.py — 미처리 .docx 149개 파싱 + DB 저장 (Supabase 업로드/임베딩 제외).

batch-parse.py의 docx 처리 로직을 경량화.
Supabase 업로드 완전 제외, 임베딩 제외, DB 저장만 수행.
"""

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from docx import Document as DocxDocument
import psycopg2
from psycopg2.extras import execute_values

# 설정
SOURCE_DIR = "C:/MES/wta-agents/data/wta-manuals-final"
DB_TABLE = "manual.wta_documents"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

CATEGORIES = [
    "CBN", "CVD", "Double_Side_Grinder", "Fujisanki_Grinding_Handler",
    "Honing", "Honing_Inspection", "Inspection", "Labeling",
    "Laser_Marking", "Macoho", "Mask_Auto", "PVD",
    "Packaging", "Press", "Repalleting", "Single_Side_Grinder",
    "Sintering_Sorter", "WBM_WVR_Daesung_Honing",
]


def load_db_password():
    with open("C:/MES/backend/.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                return line.strip().split("=", 1)[1]
    return None


def get_connection():
    return psycopg2.connect(
        host="localhost", port=55432, user="postgres",
        password=load_db_password(), dbname="postgres",
    )


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    paragraphs = re.split(r"\n{2,}", text)
    chunks, current = [], ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > size:
                for j in range(0, len(para), size - overlap):
                    chunks.append(para[j:j + size])
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


def upsert_chunks(conn, chunks_data):
    if not chunks_data:
        return
    sql = f"""INSERT INTO {DB_TABLE} (source_file, file_hash, category, chunk_index, chunk_type,
        page_number, content, image_url, pdf_url, metadata, updated_at) VALUES %s
        ON CONFLICT (source_file, chunk_index) DO UPDATE SET file_hash=EXCLUDED.file_hash,
        chunk_type=EXCLUDED.chunk_type, page_number=EXCLUDED.page_number, content=EXCLUDED.content,
        image_url=EXCLUDED.image_url, pdf_url=EXCLUDED.pdf_url, metadata=EXCLUDED.metadata,
        updated_at=now()"""
    template = ("(%(source_file)s, %(file_hash)s, %(category)s, %(chunk_index)s, %(chunk_type)s, "
                "%(page_number)s, %(content)s, %(image_url)s, %(pdf_url)s, %(metadata)s::jsonb, now())")
    with conn.cursor() as cur:
        execute_values(cur, sql, chunks_data, template=template, page_size=50)
    conn.commit()


def process_docx(file_path, category, conn):
    """단일 docx 파일 파싱 + DB 저장. 반환: 청크 수 또는 -1(에러)."""
    filename = Path(file_path).name
    standard_name = Path(file_path).stem

    # 파일 해시
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    file_hash = h.hexdigest()[:16]

    # DB 중복 확인
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {DB_TABLE} WHERE source_file=%s AND file_hash=%s LIMIT 1",
                    (filename, file_hash))
        if cur.fetchone():
            return 0  # 이미 처리됨

    # docx 열기
    try:
        doc = DocxDocument(file_path)
    except Exception as e:
        print(f"    ERROR opening: {filename} -- {e}", flush=True)
        return -1

    # 메타데이터
    parts = standard_name.split("_")
    manufacturer = parts[0] if parts else "Unknown"
    model = parts[1] if len(parts) > 1 else "Unknown"
    meta_base = {"manufacturer": manufacturer, "model": model,
                 "doc_type": "Manual", "language": "KO", "format": "docx"}

    # 본문 파싱
    all_chunks = []
    chunk_idx = 0
    page_num = 1

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            from docx.text.paragraph import Paragraph
            para = Paragraph(element, doc)
            text = para.text.strip()

            # 페이지 브레이크 감지
            xml_str = element.xml
            if "w:br" in xml_str and 'w:type="page"' in xml_str:
                page_num += 1

            if not text or len(text) < 20:
                continue

            # 텍스트 청크
            for tc in chunk_text(text):
                tc = tc.strip()
                if len(tc) < 20:
                    continue
                all_chunks.append({
                    "source_file": filename, "file_hash": file_hash, "category": category,
                    "chunk_index": chunk_idx, "chunk_type": "text", "page_number": page_num,
                    "content": tc, "image_url": "", "pdf_url": "",
                    "metadata": json.dumps({**meta_base, "page": page_num, "type": "text"},
                                           ensure_ascii=False),
                })
                chunk_idx += 1

        elif tag == "tbl":
            from docx.table import Table
            try:
                table = Table(element, doc)
                rows_md = []
                for row in table.rows:
                    cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
                    rows_md.append("| " + " | ".join(cells) + " |")
                if rows_md:
                    header = rows_md[0]
                    col_count = header.count("|") - 1
                    separator = "| " + " | ".join(["---"] * max(col_count, 1)) + " |"
                    table_md = "\n".join([rows_md[0], separator] + rows_md[1:])
                    all_chunks.append({
                        "source_file": filename, "file_hash": file_hash, "category": category,
                        "chunk_index": chunk_idx, "chunk_type": "table", "page_number": page_num,
                        "content": table_md, "image_url": "", "pdf_url": "",
                        "metadata": json.dumps({**meta_base, "page": page_num, "type": "table"},
                                               ensure_ascii=False),
                    })
                    chunk_idx += 1
            except Exception:
                pass

    if not all_chunks:
        print(f"    EMPTY: {filename}", flush=True)
        return 0

    # DB 저장
    for i in range(0, len(all_chunks), 50):
        upsert_chunks(conn, all_chunks[i:i + 50])

    return len(all_chunks)


def main():
    conn = get_connection()

    # 이미 처리된 파일 목록
    with conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT source_file FROM {DB_TABLE}")
        db_files = set(row[0] for row in cur.fetchall())

    # 미처리 파일 수집
    missing = []
    for cat in CATEGORIES:
        cat_dir = os.path.join(SOURCE_DIR, cat)
        if not os.path.isdir(cat_dir):
            continue
        for f in sorted(os.listdir(cat_dir)):
            if not f.lower().endswith(".docx"):
                continue
            if f not in db_files:
                missing.append((cat, f, os.path.join(cat_dir, f)))

    print(f"[parse-docx] {len(missing)} files to process", flush=True)

    total = len(missing)
    ok_count = 0
    err_count = 0
    skip_count = 0
    total_chunks = 0

    for i, (cat, filename, filepath) in enumerate(missing, 1):
        print(f"[{i}/{total}] {cat}/{filename}", end=" ", flush=True)
        start = time.time()
        try:
            n = process_docx(filepath, cat, conn)
        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            err_count += 1
            continue

        elapsed = time.time() - start
        if n > 0:
            print(f"OK ({n} chunks, {elapsed:.1f}s)", flush=True)
            ok_count += 1
            total_chunks += n
        elif n == 0:
            print(f"SKIP ({elapsed:.1f}s)", flush=True)
            skip_count += 1
        else:
            print(f"ERROR ({elapsed:.1f}s)", flush=True)
            err_count += 1

    conn.close()
    print(f"\n[DONE] OK={ok_count}, Skip={skip_count}, Error={err_count}, Total chunks={total_chunks}", flush=True)


if __name__ == "__main__":
    main()
