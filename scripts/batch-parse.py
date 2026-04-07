"""batch-parse.py -- Batch PDF parsing pipeline for manuals-ready/.

Processes classified PDFs: page classification -> selective rendering ->
text/table extraction -> Markdown -> Supabase upload -> embedding -> DB save.

Usage:
  python batch-parse.py --category 4_servo           # process category
  python batch-parse.py --category 4_servo --limit 10 # first 10 files
  python batch-parse.py --file path/to/file.pdf       # single file
  python batch-parse.py --category 4_servo --dry-run   # analysis only
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("[batch] pymupdf required")

try:
    import pdfplumber
except ImportError:
    sys.exit("[batch] pdfplumber required")

try:
    from docx import Document as DocxDocument
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

import psycopg2
from psycopg2.extras import execute_values
import requests

# -- Config --
BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
READY_DIR = os.path.join(BASE_DIR, "data", "manuals-ready")
IMAGE_DIR = os.path.join(BASE_DIR, "data", "manual_images")
PARSED_DIR = os.path.join(BASE_DIR, "data", "manual_parsed")
PROGRESS_FILE = os.path.join(BASE_DIR, "data", "manual_progress.json")

EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_BATCH = 16
EMBED_DELAY = 0.5
RENDER_DPI = 150
MIN_VECTOR_DRAWINGS = 20
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
DB_TABLE = "manual.documents"  # --table 옵션으로 변경 가능

SUPABASE_URL = "http://localhost:8000"
SUPABASE_BUCKET = "vector"
_env_path = os.path.join(BASE_DIR, "..", "backend", ".env")
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

DB_CONFIG = {
    "host": "localhost", "port": 55432, "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password", "dbname": "postgres",
}

logging.basicConfig(level=logging.INFO, format="[batch] %(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("batch")


# -- Supabase --
def upload_to_supabase(local_path, storage_path):
    if not SERVICE_ROLE_KEY:
        return None
    ext = os.path.splitext(local_path)[1].lower()
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".pdf": "application/pdf", ".md": "text/markdown; charset=utf-8",
    }.get(ext, "application/octet-stream")
    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}", "apikey": SERVICE_ROLE_KEY,
        "Content-Type": mime, "x-upsert": "true",
    }
    with open(local_path, "rb") as f:
        resp = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}",
            headers=headers, data=f, timeout=120,
        )
    if resp.status_code in (200, 201):
        return f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
    return None


def ensure_bucket():
    if not SERVICE_ROLE_KEY:
        return
    headers = {"Authorization": f"Bearer {SERVICE_ROLE_KEY}", "apikey": SERVICE_ROLE_KEY}
    resp = requests.get(f"{SUPABASE_URL}/storage/v1/bucket/{SUPABASE_BUCKET}", headers=headers, timeout=10)
    if resp.status_code != 200:
        requests.post(f"{SUPABASE_URL}/storage/v1/bucket",
            headers={**headers, "Content-Type": "application/json"},
            json={"id": SUPABASE_BUCKET, "name": SUPABASE_BUCKET, "public": True}, timeout=10)


# -- Page classification --
def classify_pages(doc, plumber):
    results = []
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("text").replace("\x00", "").strip()
        text_len = len(text)
        try: draw_count = len(page.get_drawings())
        except: draw_count = 0
        try: raster_count = len(page.get_images(full=True))
        except: raster_count = 0
        try:
            tables = plumber.pages[i].extract_tables()
            table_count = len([t for t in tables if t and len(t) >= 2])
        except: table_count = 0

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
        results.append({"page": i + 1, "type": ptype, "text_len": text_len,
                        "drawings": draw_count, "rasters": raster_count, "tables": table_count})
    return results


# -- Processing helpers --
MAX_RENDER_PIXELS = 4000 * 4000  # 16MP 상한 (메모리 보호)


def render_page(doc, page_idx, standard_name):
    sub_dir = os.path.join(IMAGE_DIR, standard_name)
    os.makedirs(sub_dir, exist_ok=True)
    page = doc[page_idx]
    # 페이지 크기 확인 후 DPI 조정 (메모리 보호)
    rect = page.rect
    scale = RENDER_DPI / 72.0
    est_w, est_h = int(rect.width * scale), int(rect.height * scale)
    if est_w * est_h > MAX_RENDER_PIXELS:
        ratio = (MAX_RENDER_PIXELS / (est_w * est_h)) ** 0.5
        actual_dpi = int(RENDER_DPI * ratio)
        log.info(f"    Page {page_idx+1}: {est_w}x{est_h} too large, reducing DPI {RENDER_DPI}->{actual_dpi}")
    else:
        actual_dpi = RENDER_DPI
    pix = page.get_pixmap(dpi=actual_dpi)
    img_filename = f"page_{page_idx + 1}_full.png"
    img_path = os.path.join(sub_dir, img_filename)
    pix.save(img_path)
    url = upload_to_supabase(img_path, f"images/{standard_name}/{img_filename}")
    return img_path, url, pix.width, pix.height


def extract_tables_md(plumber, page_idx):
    try: tables = plumber.pages[page_idx].extract_tables()
    except: return []
    md_tables = []
    for table in tables:
        if not table or len(table) < 2: continue
        cleaned = [[(cell or "").replace("\x00", "").replace("\n", " ").strip() for cell in row] for row in table]
        header = cleaned[0]
        col_count = len(header)
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * col_count) + " |"]
        for row in cleaned[1:]:
            padded = row + [""] * (col_count - len(row)) if len(row) < col_count else row[:col_count]
            lines.append("| " + " | ".join(padded) + " |")
        md = "\n".join(lines)
        if len(md.strip()) >= 30: md_tables.append(md)
    return md_tables


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    paragraphs = re.split(r"\n{2,}", text)
    chunks, current = [], ""
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        if len(current) + len(para) + 1 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            if current: chunks.append(current)
            if len(para) > size:
                for j in range(0, len(para), size - overlap): chunks.append(para[j:j + size])
                current = ""
            else: current = para
    if current: chunks.append(current)
    return chunks


def embed_texts(texts, embed_url=None):
    url = embed_url or EMBED_URL
    payload = {"model": "qwen3-embedding:8b", "input": texts}
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data: raise ValueError(f"Embedding error: {data}")
    # Matryoshka: 4096차원 → 2000차원으로 잘라서 반환
    return [v[:2000] for v in data["embeddings"]]


# -- DB --
def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS manual")
        cur.execute("""CREATE TABLE IF NOT EXISTS manual.documents (
            id SERIAL PRIMARY KEY, source_file TEXT NOT NULL, file_hash TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '', chunk_index INTEGER NOT NULL,
            chunk_type TEXT NOT NULL DEFAULT 'text', page_number INTEGER,
            content TEXT NOT NULL, image_url TEXT DEFAULT '', pdf_url TEXT DEFAULT '',
            metadata JSONB DEFAULT '{}', embedding vector(2000),
            created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (source_file, chunk_index))""")
        cur.execute("""DO $$ BEGIN ALTER TABLE manual.documents ADD COLUMN IF NOT EXISTS pdf_url TEXT DEFAULT '';
            EXCEPTION WHEN duplicate_column THEN NULL; END $$;""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_manual_docs_embedding
            ON manual.documents USING hnsw (embedding vector_cosine_ops)""")
    conn.commit()


def upsert_chunks(conn, chunks_data):
    if not chunks_data: return
    sql = f"""INSERT INTO {DB_TABLE} (source_file, file_hash, category, chunk_index, chunk_type,
        page_number, content, image_url, pdf_url, metadata, embedding, updated_at) VALUES %s
        ON CONFLICT (source_file, chunk_index) DO UPDATE SET file_hash=EXCLUDED.file_hash,
        chunk_type=EXCLUDED.chunk_type, page_number=EXCLUDED.page_number, content=EXCLUDED.content,
        image_url=EXCLUDED.image_url, pdf_url=EXCLUDED.pdf_url, metadata=EXCLUDED.metadata,
        embedding=EXCLUDED.embedding, updated_at=now()"""
    template = ("(%(source_file)s, %(file_hash)s, %(category)s, %(chunk_index)s, %(chunk_type)s, "
        "%(page_number)s, %(content)s, %(image_url)s, %(pdf_url)s, %(metadata)s::jsonb, %(embedding)s::vector, now())")
    with conn.cursor() as cur:
        execute_values(cur, sql, chunks_data, template=template, page_size=50)
    conn.commit()


# -- Progress tracking (file-lock safe) --
LOCK_FILE = PROGRESS_FILE + ".lock"


def _acquire_lock(lock_fd, timeout=10):
    """파일 락 획득 (Windows msvcrt / Unix fcntl)."""
    import msvcrt
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (IOError, OSError):
            time.sleep(0.1)
    return False


def _release_lock(lock_fd):
    import msvcrt
    try:
        lock_fd.seek(0)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
    except (IOError, OSError):
        pass


def load_progress():
    if os.path.isfile(PROGRESS_FILE):
        for attempt in range(3):
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                time.sleep(0.2)
    return {"files": {}}


def save_progress(progress):
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS_FILE)


def update_file_progress(rel_path, status, chunks=0, agent="dev-agent"):
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    lock_fd = open(LOCK_FILE, "a+")
    try:
        if not _acquire_lock(lock_fd):
            log.warning(f"  Progress lock timeout, skipping update for {rel_path}")
            return
        progress = load_progress()
        progress["files"][rel_path] = {
            "status": status,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent": agent,
            "chunks": chunks,
        }
        save_progress(progress)
    finally:
        _release_lock(lock_fd)
        lock_fd.close()


# -- Main processing per file --
def process_single_pdf(file_path, category, conn, dry_run=False, no_embed=False, embed_url=None, embed_batch=None):
    """Process a single PDF. Returns chunk count or -1 for skip."""
    filename = Path(file_path).name
    standard_name = Path(file_path).stem  # already standardized from classify step
    source_file = filename

    # Check progress (skip already parsed/embedded)
    rel_path = f"{category}/{filename}"
    progress = load_progress()
    file_status = progress.get("files", {}).get(rel_path, {}).get("status", "")
    if file_status in ("parsed", "embedded"):
        log.info(f"  Skip (already {file_status}): {filename}")
        return 0

    # File size check (skip > 50MB to avoid memory issues)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 50:
        log.warning(f"  Skip (too large: {file_size_mb:.0f}MB): {filename}")
        update_file_progress(rel_path, "skipped", agent="dev-agent")
        return -1

    # File hash
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""): h.update(block)
    file_hash = h.hexdigest()[:16]

    # Check if already indexed in DB
    if not dry_run and not no_embed:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {DB_TABLE} WHERE source_file=%s AND file_hash=%s LIMIT 1",
                        (source_file, file_hash))
            if cur.fetchone():
                log.info(f"  Skip (already indexed): {filename}")
                return 0

    # Open PDF
    try:
        doc = fitz.open(file_path)
        plumber_pdf = pdfplumber.open(file_path)
    except Exception as e:
        log.warning(f"  Cannot open: {filename} -- {e}")
        return -1

    total_pages = len(doc)
    if total_pages == 0:
        doc.close(); plumber_pdf.close()
        return -1

    # Classify pages
    classifications = classify_pages(doc, plumber_pdf)
    skip_types = {"empty", "minimal"}
    capture_types = {"diagram", "diagram+text", "table+diagram", "image+text", "image"}

    # Extract metadata from filename (already standardized)
    parts = standard_name.split("_")
    manufacturer = parts[0] if len(parts) > 0 else "Unknown"
    model = parts[1] if len(parts) > 1 else "Unknown"
    doc_type = parts[2] if len(parts) > 2 else "Manual"
    language = parts[3] if len(parts) > 3 else "KO"

    # Upload PDF
    pdf_url = ""
    if not dry_run:
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        pdf_url = upload_to_supabase(file_path, f"pdfs/{safe_name}") or ""

    # Process pages
    all_chunks = []
    md_lines = [f"# {manufacturer} {model} -- {doc_type}", "",
                f"- **File**: {filename}", f"- **Pages**: {total_pages}", "", "---", ""]
    chunk_idx = 0
    rendered = 0

    for ci in classifications:
        pg = ci["page"]
        ptype = ci["type"]
        page_idx = pg - 1

        if ptype in skip_types:
            continue

        md_lines.extend([f"## Page {pg}", ""])
        text = doc[page_idx].get_text("text").replace("\x00", "").strip()
        meta_base = {"page": pg, "manufacturer": manufacturer, "model": model,
                     "doc_type": doc_type, "language": language}

        # Capture decision
        if ptype in capture_types and not dry_run:
            img_path, img_url, w, h_ = render_page(doc, page_idx, standard_name)
            rendered += 1
            caption = f"[{ptype}: p.{pg}, {w}x{h_}px]"
            if img_url: md_lines.append(f"![{caption}]({img_url})")
            else: md_lines.append(caption)
            md_lines.append("")
            all_chunks.append({
                "source_file": source_file, "file_hash": file_hash, "category": category,
                "chunk_index": chunk_idx, "chunk_type": "image_caption", "page_number": pg,
                "content": caption, "image_url": img_url or "", "pdf_url": pdf_url,
                "metadata": json.dumps({**meta_base, "type": "image_caption",
                    "render_type": ptype, "width": w, "height": h_}, ensure_ascii=False),
            })
            chunk_idx += 1

        # Tables
        if ptype in ("table", "table+diagram"):
            for tmd in extract_tables_md(plumber_pdf, page_idx):
                md_lines.extend(["### Table", "", tmd, ""])
                all_chunks.append({
                    "source_file": source_file, "file_hash": file_hash, "category": category,
                    "chunk_index": chunk_idx, "chunk_type": "table", "page_number": pg,
                    "content": tmd, "image_url": "", "pdf_url": pdf_url,
                    "metadata": json.dumps({**meta_base, "type": "table"}, ensure_ascii=False),
                })
                chunk_idx += 1

        # Text chunks
        if text and len(text) >= 20:
            for tc in chunk_text(text):
                tc = tc.strip()
                if len(tc) < 20: continue
                md_lines.extend([tc, ""])
                all_chunks.append({
                    "source_file": source_file, "file_hash": file_hash, "category": category,
                    "chunk_index": chunk_idx, "chunk_type": "text", "page_number": pg,
                    "content": tc, "image_url": "", "pdf_url": pdf_url,
                    "metadata": json.dumps({**meta_base, "type": "text"}, ensure_ascii=False),
                })
                chunk_idx += 1

        md_lines.extend(["---", ""])

    doc.close()
    plumber_pdf.close()

    if not all_chunks:
        return 0

    # Save Markdown
    os.makedirs(PARSED_DIR, exist_ok=True)
    md_path = os.path.join(PARSED_DIR, f"{standard_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    if not dry_run:
        upload_to_supabase(md_path, f"parsed/{standard_name}.md")

    if dry_run:
        types = Counter(c["chunk_type"] for c in all_chunks)
        log.info(f"  [DRY] {filename}: {total_pages}p, {len(all_chunks)} chunks {dict(types)}, {rendered} rendered")
        return len(all_chunks)

    if no_embed:
        log.info(f"  PARSED: {filename} -- {len(all_chunks)} chunks, {rendered} rendered (no embed)")
        return len(all_chunks)

    # Embedding
    batch_size = embed_batch or EMBED_BATCH
    embeddable = [c for c in all_chunks if c["content"] and len(c["content"].strip()) >= 20]
    all_embeddings = []
    for i in range(0, len(embeddable), batch_size):
        batch = embeddable[i:i + batch_size]
        texts = [c["content"] for c in batch]
        for attempt in range(3):
            try:
                all_embeddings.extend(embed_texts(texts, embed_url=embed_url))
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep((attempt + 1) * 3)
                else:
                    log.error(f"  Embedding failed: {filename} batch {i}: {e}")
                    return -1
        if i + batch_size < len(embeddable):
            time.sleep(EMBED_DELAY)

    # Add embeddings
    for chunk, emb in zip(embeddable, all_embeddings):
        chunk["embedding"] = str(emb)

    # DB save
    for i in range(0, len(embeddable), 50):
        upsert_chunks(conn, embeddable[i:i + 50])

    log.info(f"  OK: {filename} -- {len(embeddable)} chunks, {rendered} rendered, {total_pages}p")
    return len(embeddable)


def process_single_docx(file_path, category, conn, dry_run=False, no_embed=False, embed_url=None, embed_batch=None):
    """Process a single DOCX file. Returns chunk count or -1 for skip."""
    if not HAS_DOCX:
        log.error("python-docx required for DOCX processing")
        return -1

    filename = Path(file_path).name
    standard_name = Path(file_path).stem
    source_file = filename

    # 진행 상태 확인
    rel_path = f"{category}/{filename}"
    progress = load_progress()
    file_status = progress.get("files", {}).get(rel_path, {}).get("status", "")
    if file_status in ("parsed", "embedded"):
        log.info(f"  Skip (already {file_status}): {filename}")
        return 0

    # 파일 크기 제한
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 80:
        log.warning(f"  Skip (too large: {file_size_mb:.0f}MB): {filename}")
        update_file_progress(rel_path, "skipped", agent="dev-agent")
        return -1

    # 파일 해시
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""): h.update(block)
    file_hash = h.hexdigest()[:16]

    # DB 중복 확인
    if not dry_run and not no_embed:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {DB_TABLE} WHERE source_file=%s AND file_hash=%s LIMIT 1",
                        (source_file, file_hash))
            if cur.fetchone():
                log.info(f"  Skip (already indexed): {filename}")
                return 0

    # DOCX 열기
    try:
        doc = DocxDocument(file_path)
    except Exception as e:
        log.warning(f"  Cannot open DOCX: {filename} -- {e}")
        update_file_progress(rel_path, "error", agent="dev-agent")
        return -1

    # 이미지 추출
    sub_dir = os.path.join(IMAGE_DIR, standard_name)
    os.makedirs(sub_dir, exist_ok=True)
    img_idx = 0
    image_urls = {}  # rId → url

    if not dry_run:
        for rel in doc.part.rels.values():
            if "image" in rel.reltype:
                try:
                    img_data = rel.target_part.blob
                    ext = os.path.splitext(rel.target_part.partname)[1] or ".png"
                    img_idx += 1
                    img_filename = f"img_{img_idx:03d}{ext}"
                    img_path = os.path.join(sub_dir, img_filename)
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    url = upload_to_supabase(img_path, f"images/{standard_name}/{img_filename}")
                    image_urls[rel.rId] = url or ""
                except Exception:
                    pass

    # 파일명에서 메타데이터 추출
    parts = standard_name.split("_")
    manufacturer = parts[0] if len(parts) > 0 else "Unknown"
    model = parts[1] if len(parts) > 1 else "Unknown"
    doc_type = "Manual"
    language = "KO"

    # PDF 업로드 (DOCX도 원본 업로드)
    pdf_url = ""
    if not dry_run:
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        pdf_url = upload_to_supabase(file_path, f"pdfs/{safe_name}") or ""

    # 본문 처리
    all_chunks = []
    md_lines = [f"# {standard_name}", "",
                f"- **File**: {filename}", f"- **Type**: DOCX", "", "---", ""]
    chunk_idx = 0
    current_section = ""
    page_num = 1

    meta_base = {"manufacturer": manufacturer, "model": model,
                 "doc_type": doc_type, "language": language, "format": "docx"}

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            # 단락 처리
            from docx.text.paragraph import Paragraph
            para = Paragraph(element, doc)
            text = para.text.strip()

            # 페이지 구분 (페이지 브레이크 감지)
            xml_str = element.xml
            if "w:br" in xml_str and 'w:type="page"' in xml_str:
                page_num += 1
                md_lines.extend(["---", f"## Page {page_num}", ""])

            if not text:
                continue

            # 제목 스타일 감지
            style_name = (para.style.name or "").lower() if para.style else ""
            if "heading" in style_name or "제목" in style_name:
                level = 2
                if "1" in style_name: level = 2
                elif "2" in style_name: level = 3
                elif "3" in style_name: level = 4
                md_lines.append(f"{'#' * level} {text}")
                md_lines.append("")
                current_section = text
                continue

            # 이미지 포함 단락
            if "w:drawing" in xml_str or "w:pict" in xml_str:
                # 이미지 참조 찾기
                import lxml.etree as ET
                ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                      "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
                blips = element.findall(".//a:blip", ns)
                for blip in blips:
                    r_embed = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                    if r_embed and r_embed in image_urls:
                        caption = f"[image: p.{page_num}]"
                        url = image_urls[r_embed]
                        if url:
                            md_lines.append(f"![{caption}]({url})")
                        else:
                            md_lines.append(caption)
                        md_lines.append("")
                        all_chunks.append({
                            "source_file": source_file, "file_hash": file_hash, "category": category,
                            "chunk_index": chunk_idx, "chunk_type": "image_caption", "page_number": page_num,
                            "content": caption + (f" {text}" if text else ""),
                            "image_url": url, "pdf_url": pdf_url,
                            "metadata": json.dumps({**meta_base, "page": page_num, "type": "image_caption"},
                                                   ensure_ascii=False),
                        })
                        chunk_idx += 1

            # 텍스트 청크
            if text and len(text) >= 20:
                for tc in chunk_text(text):
                    tc = tc.strip()
                    if len(tc) < 20:
                        continue
                    md_lines.extend([tc, ""])
                    all_chunks.append({
                        "source_file": source_file, "file_hash": file_hash, "category": category,
                        "chunk_index": chunk_idx, "chunk_type": "text", "page_number": page_num,
                        "content": tc, "image_url": "", "pdf_url": pdf_url,
                        "metadata": json.dumps({**meta_base, "page": page_num, "type": "text"},
                                               ensure_ascii=False),
                    })
                    chunk_idx += 1

        elif tag == "tbl":
            # 표 처리
            from docx.table import Table
            try:
                table = Table(element, doc)
                rows_md = []
                for row in table.rows:
                    cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
                    rows_md.append("| " + " | ".join(cells) + " |")
                if rows_md:
                    # 헤더 구분선 추가
                    header = rows_md[0]
                    col_count = header.count("|") - 1
                    separator = "| " + " | ".join(["---"] * max(col_count, 1)) + " |"
                    table_md = "\n".join([rows_md[0], separator] + rows_md[1:])
                    md_lines.extend(["### Table", "", table_md, ""])
                    all_chunks.append({
                        "source_file": source_file, "file_hash": file_hash, "category": category,
                        "chunk_index": chunk_idx, "chunk_type": "table", "page_number": page_num,
                        "content": table_md, "image_url": "", "pdf_url": pdf_url,
                        "metadata": json.dumps({**meta_base, "page": page_num, "type": "table"},
                                               ensure_ascii=False),
                    })
                    chunk_idx += 1
            except Exception:
                pass

    if not all_chunks:
        log.warning(f"  No content: {filename}")
        update_file_progress(rel_path, "skipped", agent="dev-agent")
        return 0

    # Markdown 저장
    os.makedirs(PARSED_DIR, exist_ok=True)
    md_path = os.path.join(PARSED_DIR, f"{standard_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    if not dry_run:
        upload_to_supabase(md_path, f"parsed/{standard_name}.md")

    if dry_run:
        types = Counter(c["chunk_type"] for c in all_chunks)
        log.info(f"  [DRY] {filename}: {len(all_chunks)} chunks {dict(types)}, {img_idx} images")
        return len(all_chunks)

    # 진행 상태 업데이트
    update_file_progress(rel_path, "parsed", chunks=len(all_chunks), agent="dev-agent")

    if no_embed:
        log.info(f"  PARSED: {filename} -- {len(all_chunks)} chunks, {img_idx} images (no embed)")
        return len(all_chunks)

    # 임베딩
    batch_size = embed_batch or EMBED_BATCH
    embeddable = [c for c in all_chunks if c["content"] and len(c["content"].strip()) >= 20]
    all_embeddings = []
    for i in range(0, len(embeddable), batch_size):
        batch = embeddable[i:i + batch_size]
        texts = [c["content"] for c in batch]
        for attempt in range(3):
            try:
                all_embeddings.extend(embed_texts(texts, embed_url=embed_url))
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep((attempt + 1) * 3)
                else:
                    log.error(f"  Embedding failed: {filename} batch {i}: {e}")
                    return -1
        if i + batch_size < len(embeddable):
            time.sleep(EMBED_DELAY)

    for chunk, emb in zip(embeddable, all_embeddings):
        chunk["embedding"] = str(emb)

    for i in range(0, len(embeddable), 50):
        upsert_chunks(conn, embeddable[i:i + 50])

    update_file_progress(rel_path, "embedded", chunks=len(embeddable), agent="dev-agent")
    log.info(f"  OK: {filename} -- {len(embeddable)} chunks, {img_idx} images")
    return len(embeddable)


def embed_only_from_parsed(category, conn, embed_url=None, embed_batch=None, limit=None):
    """이미 파싱된 MD 파일을 읽어서 임베딩 + DB 저장만 수행."""
    batch_size = embed_batch or EMBED_BATCH
    md_files = sorted([f for f in os.listdir(PARSED_DIR) if f.endswith(".md")])

    # 카테고리 필터: manuals-ready/{category}/ 에 있는 PDF 이름과 매칭
    if category:
        cat_dir = os.path.join(READY_DIR, category)
        if os.path.isdir(cat_dir):
            pdf_stems = set(Path(f).stem for f in os.listdir(cat_dir) if f.lower().endswith(".pdf"))
            md_files = [f for f in md_files if f.replace(".md", "") in pdf_stems]

    if limit:
        md_files = md_files[:limit]

    log.info(f"Embed-only: {len(md_files)} parsed files from {category or 'all'}")
    total_embedded = 0
    processed = 0
    errors = 0

    for i, md_file in enumerate(md_files):
        standard_name = md_file.replace(".md", "")
        source_file = standard_name + ".pdf"
        rel_path = f"{category}/{source_file}" if category else source_file

        # progress 체크: embedded 상태면 스킵
        progress = load_progress()
        file_status = progress.get("files", {}).get(rel_path, {}).get("status", "")
        if file_status == "embedded":
            log.info(f"  [{i+1}/{len(md_files)}] Skip (already embedded): {md_file}")
            continue

        log.info(f"  [{i+1}/{len(md_files)}] Embedding: {md_file}")

        # MD 파일 읽기
        md_path = os.path.join(PARSED_DIR, md_file)
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
        except Exception as e:
            log.error(f"    Read error: {e}")
            errors += 1
            continue

        # 파일 해시 (MD 파일 기준)
        import hashlib
        file_hash = hashlib.sha256(md_content.encode()).hexdigest()[:16]

        # DB 중복 체크
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {DB_TABLE} WHERE source_file=%s AND file_hash=%s LIMIT 1",
                        (source_file, file_hash))
            if cur.fetchone():
                log.info(f"    Skip (already in DB): {source_file}")
                update_file_progress(rel_path, "embedded")
                continue

        # 기존 레코드 삭제 (재임베딩 시)
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {DB_TABLE} WHERE source_file=%s", (source_file,))
            if cur.rowcount > 0:
                log.info(f"    Deleted {cur.rowcount} old records")
        conn.commit()

        # 메타데이터 추출
        parts = standard_name.split("_")
        manufacturer = parts[0] if len(parts) > 0 else "Unknown"
        model = parts[1] if len(parts) > 1 else "Unknown"
        doc_type = parts[2] if len(parts) > 2 else "Manual"
        language = parts[3] if len(parts) > 3 else "KO"

        # PDF URL (Supabase)
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', source_file)
        pdf_url = f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/pdfs/{safe_name}"

        # MD를 청크로 분할
        chunks_data = []
        chunk_idx = 0

        # 페이지별 분리 (## Page N 기준)
        sections = re.split(r"(?=^## Page \d+)", md_content, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 페이지 번호 추출
            page_match = re.match(r"## Page (\d+)", section)
            page_num = int(page_match.group(1)) if page_match else None

            # 이미지 캡션 추출
            for img_match in re.finditer(r"!\[([^\]]*)\]\(([^)]*)\)", section):
                caption = img_match.group(1)
                img_url = img_match.group(2)
                if caption and len(caption) >= 10:
                    chunks_data.append({
                        "source_file": source_file, "file_hash": file_hash,
                        "category": category or "", "chunk_index": chunk_idx,
                        "chunk_type": "image_caption", "page_number": page_num,
                        "content": caption, "image_url": img_url, "pdf_url": pdf_url,
                        "metadata": json.dumps({"page": page_num, "manufacturer": manufacturer,
                            "model": model, "doc_type": doc_type, "language": language,
                            "type": "image_caption"}, ensure_ascii=False),
                    })
                    chunk_idx += 1

            # 테이블 추출 (| 로 시작하는 블록)
            table_blocks = re.findall(r"((?:^\|.*\n?)+)", section, flags=re.MULTILINE)
            for tbl in table_blocks:
                tbl = tbl.strip()
                if len(tbl) >= 30:
                    chunks_data.append({
                        "source_file": source_file, "file_hash": file_hash,
                        "category": category or "", "chunk_index": chunk_idx,
                        "chunk_type": "table", "page_number": page_num,
                        "content": tbl, "image_url": "", "pdf_url": pdf_url,
                        "metadata": json.dumps({"page": page_num, "manufacturer": manufacturer,
                            "model": model, "doc_type": doc_type, "language": language,
                            "type": "table"}, ensure_ascii=False),
                    })
                    chunk_idx += 1

            # 텍스트 추출 (이미지/테이블/헤더 제외)
            text_lines = []
            for line in section.split("\n"):
                line = line.strip()
                if line.startswith("##") or line.startswith("![") or line.startswith("|") or line == "---":
                    continue
                if line:
                    text_lines.append(line)
            text = "\n".join(text_lines)

            if text and len(text) >= 20:
                for tc in chunk_text(text):
                    tc = tc.strip()
                    if len(tc) < 20:
                        continue
                    chunks_data.append({
                        "source_file": source_file, "file_hash": file_hash,
                        "category": category or "", "chunk_index": chunk_idx,
                        "chunk_type": "text", "page_number": page_num,
                        "content": tc, "image_url": "", "pdf_url": pdf_url,
                        "metadata": json.dumps({"page": page_num, "manufacturer": manufacturer,
                            "model": model, "doc_type": doc_type, "language": language,
                            "type": "text"}, ensure_ascii=False),
                    })
                    chunk_idx += 1

        if not chunks_data:
            log.warning(f"    No chunks from {md_file}")
            errors += 1
            continue

        # 임베딩
        embeddable = [c for c in chunks_data if c["content"] and len(c["content"].strip()) >= 20]
        all_embeddings = []
        embed_ok = True

        for bi in range(0, len(embeddable), batch_size):
            batch = embeddable[bi:bi + batch_size]
            texts = [c["content"] for c in batch]
            for attempt in range(3):
                try:
                    all_embeddings.extend(embed_texts(texts, embed_url=embed_url))
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep((attempt + 1) * 3)
                    else:
                        log.error(f"    Embedding failed: {md_file} batch {bi}: {e}")
                        embed_ok = False
            if not embed_ok:
                break
            if bi + batch_size < len(embeddable):
                time.sleep(0.1)  # Ollama에는 짧은 딜레이

        if not embed_ok:
            errors += 1
            continue

        # 임베딩 결합
        for chunk, emb in zip(embeddable, all_embeddings):
            chunk["embedding"] = str(emb)

        # DB 저장
        for bi in range(0, len(embeddable), 50):
            upsert_chunks(conn, embeddable[bi:bi + 50])

        # progress 업데이트
        update_file_progress(rel_path, "embedded", chunks=len(embeddable))
        total_embedded += len(embeddable)
        processed += 1
        log.info(f"    OK: {len(embeddable)} chunks embedded")

    log.info(f"\nEmbed-only done: {processed} files, {total_embedded} chunks, {errors} errors")
    return total_embedded


def main():
    parser = argparse.ArgumentParser(description="Batch PDF/DOCX parsing")
    parser.add_argument("--category", help="Category folder name (e.g. 4_servo)")
    parser.add_argument("--file", help="Single file path (PDF or DOCX)")
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-embed", action="store_true", help="Parse + upload only, skip embedding")
    parser.add_argument("--embed-only", action="store_true", help="Embed already-parsed files (read from manual_parsed/)")
    parser.add_argument("--embed-url", help="Embedding server URL (default: http://182.224.6.147:11434/api/embed)")
    parser.add_argument("--embed-batch", type=int, default=None, help="Embedding batch size (default: 16, ollama: 128)")
    parser.add_argument("--source-dir", help="Source directory (default: data/manuals-ready)")
    parser.add_argument("--table", help="DB table name (default: manual.documents)")
    args = parser.parse_args()

    # 소스 디렉토리 / 테이블 오버라이드
    global READY_DIR, DB_TABLE
    if args.source_dir:
        READY_DIR = os.path.normpath(args.source_dir)
    if args.table:
        DB_TABLE = f"manual.{args.table}"

    conn = None
    if not args.dry_run:
        conn = psycopg2.connect(**DB_CONFIG)
        ensure_schema(conn)
        ensure_bucket()

    # --embed-only 모드: 이미 파싱된 MD 파일에서 임베딩만 수행
    if args.embed_only:
        if not conn:
            log.error("--embed-only requires DB connection (no --dry-run)")
            return
        embed_only_from_parsed(
            category=args.category or "",
            conn=conn,
            embed_url=args.embed_url,
            embed_batch=args.embed_batch,
            limit=args.limit,
        )
        if conn: conn.close()
        return

    SUPPORTED_EXTS = {".pdf", ".docx"}
    if args.file:
        all_files = [args.file]
        category = Path(args.file).parent.name
    elif args.category:
        cat_dir = os.path.join(READY_DIR, args.category)
        if not os.path.isdir(cat_dir):
            log.error(f"Not found: {cat_dir}")
            return
        all_files = sorted([os.path.join(cat_dir, f) for f in os.listdir(cat_dir)
                           if Path(f).suffix.lower() in SUPPORTED_EXTS])
        category = args.category
    else:
        log.error("Specify --category or --file")
        return

    if args.limit:
        all_files = all_files[:args.limit]

    pdf_count = sum(1 for f in all_files if f.lower().endswith(".pdf"))
    docx_count = sum(1 for f in all_files if f.lower().endswith(".docx"))
    if args.embed_url:
        log.info(f"Embed URL: {args.embed_url} (batch={args.embed_batch or EMBED_BATCH})")
    log.info(f"Processing {len(all_files)} files ({pdf_count} PDF + {docx_count} DOCX) from {category}")
    total_chunks = 0
    processed = 0
    errors = 0

    import gc

    for i, fp in enumerate(all_files):
        log.info(f"[{i+1}/{len(all_files)}] {Path(fp).name}")
        gc.collect()
        try:
            if fp.lower().endswith(".docx"):
                n = process_single_docx(fp, category, conn, dry_run=args.dry_run, no_embed=args.no_embed,
                                        embed_url=args.embed_url, embed_batch=args.embed_batch)
            else:
                n = process_single_pdf(fp, category, conn, dry_run=args.dry_run, no_embed=args.no_embed,
                                       embed_url=args.embed_url, embed_batch=args.embed_batch)
            if n > 0:
                total_chunks += n
                processed += 1
                if not args.dry_run:
                    rel_path = f"{category}/{Path(fp).name}"
                    status = "parsed" if args.no_embed else "embedded"
                    update_file_progress(rel_path, status, chunks=n)
            elif n == -1:
                errors += 1
                if not args.dry_run:
                    rel_path = f"{category}/{Path(fp).name}"
                    update_file_progress(rel_path, "error")
        except Exception as e:
            log.error(f"  FAIL: {Path(fp).name} -- {e}")
            errors += 1
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass

    log.info(f"\nDone: {processed} processed, {total_chunks} chunks, {errors} errors")
    if conn: conn.close()


if __name__ == "__main__":
    main()
