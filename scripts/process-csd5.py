"""process-csd5.py -- CSD5 manual smart processing pipeline.

Page classification -> selective rendering -> text/table extraction -> Markdown -> embedding.

Usage:
  python process-csd5.py              # full processing
  python process-csd5.py --dry-run    # analysis only, no DB/upload
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("[csd5] pymupdf required: pip install pymupdf")

try:
    import pdfplumber
except ImportError:
    sys.exit("[csd5] pdfplumber required: pip install pdfplumber")

import psycopg2
from psycopg2.extras import execute_values
import requests

# -- Config --
# PDF path - find by glob to avoid encoding issues
_servo_dir = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "manuals-filtered", "4_servo"
))
PDF_PATH = ""
if os.path.isdir(_servo_dir):
    for f in os.listdir(_servo_dir):
        if f.startswith("CSD5-UM001C") and f.endswith(".pdf"):
            PDF_PATH = os.path.join(_servo_dir, f)
            break
STANDARD_NAME = "Samsung_CSD5_UserManual_KO"
SOURCE_FILE = f"{STANDARD_NAME}.pdf"
CATEGORY = "4_servo"

IMAGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "manual_images"))
PARSED_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "manual_parsed"))

EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_BATCH = 16
EMBED_DELAY = 0.5
RENDER_DPI = 150

SUPABASE_URL = "http://localhost:8000"
SUPABASE_BUCKET = "vector"
_env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))
SERVICE_ROLE_KEY = ""
SUPABASE_PUBLIC_URL = os.environ.get("SUPABASE_PUBLIC_URL", SUPABASE_URL)
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("SERVICE_ROLE_KEY="):
                SERVICE_ROLE_KEY = _line.split("=", 1)[1].strip()
            elif _line.startswith("SUPABASE_PUBLIC_URL="):
                SUPABASE_PUBLIC_URL = _line.split("=", 1)[1].strip()

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_VECTOR_DRAWINGS = 20

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

logging.basicConfig(
    level=logging.INFO,
    format="[csd5] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("csd5")


# -- Supabase --

def upload_to_supabase(local_path, storage_path):
    """Upload file to Supabase Storage, return public URL or None."""
    if not SERVICE_ROLE_KEY:
        return None
    ext = os.path.splitext(local_path)[1].lower()
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".pdf": "application/pdf", ".md": "text/markdown; charset=utf-8",
    }.get(ext, "application/octet-stream")

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": mime,
        "x-upsert": "true",
    }
    with open(local_path, "rb") as f:
        resp = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}",
            headers=headers, data=f, timeout=120,
        )
    if resp.status_code in (200, 201):
        return f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
    else:
        log.warning(f"Upload failed ({storage_path}): {resp.status_code}")
        return None


def ensure_bucket():
    if not SERVICE_ROLE_KEY:
        return
    headers = {"Authorization": f"Bearer {SERVICE_ROLE_KEY}", "apikey": SERVICE_ROLE_KEY}
    resp = requests.get(f"{SUPABASE_URL}/storage/v1/bucket/{SUPABASE_BUCKET}", headers=headers, timeout=10)
    if resp.status_code == 200:
        return
    requests.post(
        f"{SUPABASE_URL}/storage/v1/bucket",
        headers={**headers, "Content-Type": "application/json"},
        json={"id": SUPABASE_BUCKET, "name": SUPABASE_BUCKET, "public": True},
        timeout=10,
    )


# -- Page classification --

def classify_pages(doc, plumber):
    """Classify each page by content type."""
    results = []
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("text").replace("\x00", "").strip()
        text_len = len(text)

        try:
            draw_count = len(page.get_drawings())
        except Exception:
            draw_count = 0

        try:
            raster_count = len(page.get_images(full=True))
        except Exception:
            raster_count = 0

        try:
            tables = plumber.pages[i].extract_tables()
            table_count = len([t for t in tables if t and len(t) >= 2])
        except Exception:
            table_count = 0

        # Classification logic
        if text_len < 30 and draw_count < 5 and raster_count == 0:
            ptype = "empty"
        elif draw_count >= MIN_VECTOR_DRAWINGS and raster_count <= 1 and text_len < 3000:
            ptype = "diagram"
        elif draw_count >= MIN_VECTOR_DRAWINGS and text_len >= 3000:
            ptype = "diagram+text"
        elif table_count > 0 and draw_count >= 10:
            ptype = "table+diagram"
        elif table_count > 0:
            ptype = "table"
        elif raster_count > 0 and text_len > 100:
            ptype = "image+text"
        elif raster_count > 0:
            ptype = "image"
        elif text_len > 100:
            ptype = "text"
        else:
            ptype = "minimal"

        results.append({
            "page": i + 1,
            "type": ptype,
            "text_len": text_len,
            "drawings": draw_count,
            "rasters": raster_count,
            "tables": table_count,
        })
    return results


# -- Processing functions --

def render_page(doc, page_idx, suffix="full"):
    """Render page to PNG, upload to Supabase. Return (local_path, url)."""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=RENDER_DPI)

    img_filename = f"page_{page_idx + 1}_{suffix}.png"
    img_path = os.path.join(IMAGE_DIR, f"{STANDARD_NAME}_{img_filename}")
    pix.save(img_path)

    storage_path = f"images/{STANDARD_NAME}/{img_filename}"
    url = upload_to_supabase(img_path, storage_path)
    return img_path, url, pix.width, pix.height


def extract_raster_images(doc, page_idx):
    """Extract meaningful raster images from page. Return list of (path, url, w, h).

    Filters out:
    - Small icons (< 200x150)
    - Repeated 7-segment display images (same hash across pages)
    - Tiny file sizes (< 5KB after save)
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)
    page = doc[page_idx]
    results = []

    try:
        images = page.get_images(full=True)
    except Exception:
        return results

    for img_idx, img_info in enumerate(images):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            if not base_image or "image" not in base_image:
                continue
        except Exception:
            continue

        w = base_image.get("width", 0)
        h = base_image.get("height", 0)
        # Higher threshold: skip small icons and repeated UI elements
        if w < 200 or h < 150:
            continue
        # Skip very small image data (likely decorative)
        if len(base_image["image"]) < 5000:
            continue

        ext = base_image.get("ext", "png")
        img_filename = f"page_{page_idx + 1}_img{img_idx}.{ext}"
        img_path = os.path.join(IMAGE_DIR, f"{STANDARD_NAME}_{img_filename}")

        try:
            with open(img_path, "wb") as f:
                f.write(base_image["image"])
            storage_path = f"images/{STANDARD_NAME}/{img_filename}"
            url = upload_to_supabase(img_path, storage_path)
            results.append((img_path, url, w, h))
        except Exception:
            continue

    return results


def extract_tables_md(plumber, page_idx):
    """Extract tables from page as Markdown."""
    try:
        tables = plumber.pages[page_idx].extract_tables()
    except Exception:
        return []

    md_tables = []
    for table in tables:
        if not table or len(table) < 2:
            continue

        cleaned = []
        for row in table:
            cleaned.append([
                (cell or "").replace("\x00", "").replace("\n", " ").strip()
                for cell in row
            ])

        header = cleaned[0]
        col_count = len(header)
        lines = []
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * col_count) + " |")
        for row in cleaned[1:]:
            padded = row + [""] * (col_count - len(row)) if len(row) < col_count else row[:col_count]
            lines.append("| " + " | ".join(padded) + " |")

        md = "\n".join(lines)
        if len(md.strip()) >= 30:
            md_tables.append(md)

    return md_tables


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into chunks at paragraph boundaries."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    current = ""
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


# -- Embedding --

def embed_texts(texts):
    """Batch embed via Qwen3-Embedding-8B (Ollama)."""
    resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": texts}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"Embedding error: {data}")
    # Matryoshka: 4096차원 → 2000차원으로 잘라서 반환
    return [v[:2000] for v in data["embeddings"]]


# -- DB --

def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS manual")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual.documents (
                id SERIAL PRIMARY KEY,
                source_file TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                chunk_index INTEGER NOT NULL,
                chunk_type TEXT NOT NULL DEFAULT 'text',
                page_number INTEGER,
                content TEXT NOT NULL,
                image_url TEXT DEFAULT '',
                pdf_url TEXT DEFAULT '',
                metadata JSONB DEFAULT '{}',
                embedding vector(1024),
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE (source_file, chunk_index)
            )
        """)
        cur.execute("""
            DO $$ BEGIN
                ALTER TABLE manual.documents ADD COLUMN IF NOT EXISTS pdf_url TEXT DEFAULT '';
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_docs_embedding
                ON manual.documents USING hnsw (embedding vector_cosine_ops)
        """)
    conn.commit()


def delete_existing(conn, source_file):
    """Delete existing data for this source file."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM manual.documents WHERE source_file = %s", (source_file,))
        deleted = cur.rowcount
    conn.commit()
    return deleted


def upsert_chunks(conn, chunks_data):
    """Insert chunk records into DB."""
    if not chunks_data:
        return
    sql = """
        INSERT INTO manual.documents
            (source_file, file_hash, category, chunk_index, chunk_type, page_number,
             content, image_url, pdf_url, metadata, embedding, updated_at)
        VALUES %s
        ON CONFLICT (source_file, chunk_index)
        DO UPDATE SET
            file_hash = EXCLUDED.file_hash,
            chunk_type = EXCLUDED.chunk_type,
            page_number = EXCLUDED.page_number,
            content = EXCLUDED.content,
            image_url = EXCLUDED.image_url,
            pdf_url = EXCLUDED.pdf_url,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            updated_at = now()
    """
    template = (
        "(%(source_file)s, %(file_hash)s, %(category)s, %(chunk_index)s, %(chunk_type)s, "
        "%(page_number)s, %(content)s, %(image_url)s, %(pdf_url)s, %(metadata)s::jsonb, "
        "%(embedding)s::vector, now())"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, chunks_data, template=template, page_size=50)
    conn.commit()


# -- Main processing --

def process_all(dry_run=False):
    if not os.path.isfile(PDF_PATH):
        log.error(f"PDF not found: {PDF_PATH}")
        return

    log.info(f"Processing: {PDF_PATH}")
    log.info(f"Standard name: {STANDARD_NAME}")

    # File hash
    h = hashlib.sha256()
    with open(PDF_PATH, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    file_hash = h.hexdigest()[:16]

    # Open PDF
    doc = fitz.open(PDF_PATH)
    plumber = pdfplumber.open(PDF_PATH)
    total_pages = len(doc)
    log.info(f"Total pages: {total_pages}")

    # 1. Classify pages
    log.info("Step 1: Classifying pages...")
    classifications = classify_pages(doc, plumber)
    from collections import Counter
    type_counts = Counter(c["type"] for c in classifications)
    for ptype, cnt in type_counts.most_common():
        log.info(f"  {ptype}: {cnt}")

    # Need capture: diagram, diagram+text, table+diagram, image+text, image
    capture_types = {"diagram", "diagram+text", "table+diagram", "image+text", "image"}
    text_types = {"text", "table", "diagram+text", "table+diagram", "image+text"}
    skip_types = {"empty", "minimal"}

    # 2. Process pages
    log.info("Step 2: Processing pages...")
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(PARSED_DIR, exist_ok=True)

    all_chunks = []  # list of dicts ready for DB
    md_lines = []    # Markdown content
    chunk_idx = 0

    md_lines.append(f"# Samsung CSD5 UserManual KO")
    md_lines.append("")
    md_lines.append(f"- **Source**: {Path(PDF_PATH).name}")
    md_lines.append(f"- **Standard**: {SOURCE_FILE}")
    md_lines.append(f"- **Pages**: {total_pages}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # Upload PDF to Supabase
    pdf_url = ""
    if not dry_run:
        ensure_bucket()
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', SOURCE_FILE)
        pdf_url = upload_to_supabase(PDF_PATH, f"pdfs/{safe_name}") or ""
        if pdf_url:
            log.info(f"  PDF uploaded: pdfs/{safe_name}")

    rendered_count = 0
    raster_count = 0

    for ci in classifications:
        pg = ci["page"]
        ptype = ci["type"]
        page_idx = pg - 1

        if ptype in skip_types:
            continue

        md_lines.append(f"## Page {pg}")
        md_lines.append("")

        # Text extraction
        text = doc[page_idx].get_text("text").replace("\x00", "").strip()

        # Capture decision
        if ptype in capture_types and not dry_run:
            if ptype in ("diagram", "diagram+text"):
                # Full page render for vector diagrams
                img_path, img_url, w, h_ = render_page(doc, page_idx)
                rendered_count += 1

                caption = f"[Diagram: p.{pg}, {w}x{h_}px, vector render]"
                if img_url:
                    md_lines.append(f"![{caption}]({img_url})")
                else:
                    md_lines.append(caption)
                md_lines.append("")

                all_chunks.append({
                    "source_file": SOURCE_FILE, "file_hash": file_hash,
                    "category": CATEGORY, "chunk_index": chunk_idx,
                    "chunk_type": "image_caption", "page_number": pg,
                    "content": caption,
                    "image_url": img_url or "", "pdf_url": pdf_url,
                    "metadata": json.dumps({
                        "page": pg, "type": "image_caption",
                        "render_type": "vector_page", "width": w, "height": h_,
                        "manufacturer": "Samsung", "model": "CSD5",
                        "doc_type": "UserManual", "language": "KO",
                    }, ensure_ascii=False),
                })
                chunk_idx += 1

            elif ptype in ("table+diagram",):
                # Render full page + extract tables
                img_path, img_url, w, h_ = render_page(doc, page_idx)
                rendered_count += 1

                caption = f"[Table+Diagram: p.{pg}, {w}x{h_}px]"
                if img_url:
                    md_lines.append(f"![{caption}]({img_url})")
                else:
                    md_lines.append(caption)
                md_lines.append("")

                all_chunks.append({
                    "source_file": SOURCE_FILE, "file_hash": file_hash,
                    "category": CATEGORY, "chunk_index": chunk_idx,
                    "chunk_type": "image_caption", "page_number": pg,
                    "content": caption,
                    "image_url": img_url or "", "pdf_url": pdf_url,
                    "metadata": json.dumps({
                        "page": pg, "type": "image_caption",
                        "render_type": "table_diagram_page", "width": w, "height": h_,
                        "manufacturer": "Samsung", "model": "CSD5",
                        "doc_type": "UserManual", "language": "KO",
                    }, ensure_ascii=False),
                })
                chunk_idx += 1

            elif ptype in ("image+text", "image"):
                # Full page render (better quality than raster extraction)
                img_path, img_url, w, h_ = render_page(doc, page_idx)
                rendered_count += 1

                caption = f"[Image+Text: p.{pg}, {w}x{h_}px]"
                if img_url:
                    md_lines.append(f"![{caption}]({img_url})")
                else:
                    md_lines.append(caption)
                md_lines.append("")

                all_chunks.append({
                    "source_file": SOURCE_FILE, "file_hash": file_hash,
                    "category": CATEGORY, "chunk_index": chunk_idx,
                    "chunk_type": "image_caption", "page_number": pg,
                    "content": caption,
                    "image_url": img_url or "", "pdf_url": pdf_url,
                    "metadata": json.dumps({
                        "page": pg, "type": "image_caption",
                        "render_type": "page_with_images", "width": w, "height": h_,
                        "manufacturer": "Samsung", "model": "CSD5",
                        "doc_type": "UserManual", "language": "KO",
                    }, ensure_ascii=False),
                })
                chunk_idx += 1

        # Table extraction (for types with tables)
        if ptype in ("table", "table+diagram"):
            tables_md = extract_tables_md(plumber, page_idx)
            for tmd in tables_md:
                md_lines.append("### Table")
                md_lines.append("")
                md_lines.append(tmd)
                md_lines.append("")

                all_chunks.append({
                    "source_file": SOURCE_FILE, "file_hash": file_hash,
                    "category": CATEGORY, "chunk_index": chunk_idx,
                    "chunk_type": "table", "page_number": pg,
                    "content": tmd,
                    "image_url": "", "pdf_url": pdf_url,
                    "metadata": json.dumps({
                        "page": pg, "type": "table",
                        "manufacturer": "Samsung", "model": "CSD5",
                        "doc_type": "UserManual", "language": "KO",
                    }, ensure_ascii=False),
                })
                chunk_idx += 1

        # Text chunks
        if text and len(text) >= 20:
            text_chunks = chunk_text(text)
            for tc in text_chunks:
                tc = tc.strip()
                if len(tc) < 20:
                    continue

                md_lines.append(tc)
                md_lines.append("")

                all_chunks.append({
                    "source_file": SOURCE_FILE, "file_hash": file_hash,
                    "category": CATEGORY, "chunk_index": chunk_idx,
                    "chunk_type": "text", "page_number": pg,
                    "content": tc,
                    "image_url": "", "pdf_url": pdf_url,
                    "metadata": json.dumps({
                        "page": pg, "type": "text",
                        "manufacturer": "Samsung", "model": "CSD5",
                        "doc_type": "UserManual", "language": "KO",
                    }, ensure_ascii=False),
                })
                chunk_idx += 1

        md_lines.append("---")
        md_lines.append("")

    doc.close()
    plumber.close()

    log.info(f"  Rendered pages: {rendered_count}")
    log.info(f"  Raster images: {raster_count}")
    log.info(f"  Total chunks: {len(all_chunks)}")

    # 3. Save Markdown
    md_content = "\n".join(md_lines)
    md_path = os.path.join(PARSED_DIR, f"{STANDARD_NAME}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    log.info(f"  Markdown saved: {md_path} ({len(md_content)} chars)")

    if not dry_run:
        md_url = upload_to_supabase(md_path, f"parsed/{STANDARD_NAME}.md")
        if md_url:
            log.info(f"  Markdown uploaded")

    if dry_run:
        type_breakdown = Counter(c["chunk_type"] for c in all_chunks)
        log.info(f"  [DRY-RUN] Chunk breakdown: {dict(type_breakdown)}")
        return

    # 4. Embedding
    log.info("Step 3: Embedding...")
    embeddable = [c for c in all_chunks if c["content"] and len(c["content"].strip()) >= 20]
    log.info(f"  Embeddable chunks: {len(embeddable)}")

    all_embeddings = []
    for i in range(0, len(embeddable), EMBED_BATCH):
        batch = embeddable[i:i + EMBED_BATCH]
        texts = [c["content"] for c in batch]

        for attempt in range(3):
            try:
                batch_emb = embed_texts(texts)
                all_embeddings.extend(batch_emb)
                break
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    log.warning(f"  Retry {attempt+1}/3 (batch {i}, wait {wait}s): {e}")
                    time.sleep(wait)
                else:
                    log.error(f"  Embedding failed (batch {i}): {e}")
                    return

        if i + EMBED_BATCH < len(embeddable):
            time.sleep(EMBED_DELAY)

        if (i + EMBED_BATCH) % 100 < EMBED_BATCH:
            log.info(f"  Embedded: {min(i + EMBED_BATCH, len(embeddable))}/{len(embeddable)}")

    # 5. DB save
    log.info("Step 4: Saving to DB...")
    conn = psycopg2.connect(**DB_CONFIG)
    ensure_schema(conn)

    # Delete existing CSD5 data
    deleted = delete_existing(conn, SOURCE_FILE)
    # Also delete old source_file format (any CSD5 variants)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM manual.documents WHERE source_file LIKE '%CSD5%'")
        deleted2 = cur.rowcount
    conn.commit()
    log.info(f"  Deleted existing: {deleted + deleted2} rows")

    # Add embeddings to chunk data
    for chunk, emb in zip(embeddable, all_embeddings):
        chunk["embedding"] = str(emb)

    # Batch insert
    for i in range(0, len(embeddable), 50):
        batch = embeddable[i:i + 50]
        upsert_chunks(conn, batch)

    conn.close()
    log.info(f"  Saved: {len(embeddable)} chunks")
    log.info("Done!")


def main():
    parser = argparse.ArgumentParser(description="CSD5 manual smart processing")
    parser.add_argument("--dry-run", action="store_true", help="Analysis only, no DB/upload")
    args = parser.parse_args()
    process_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
