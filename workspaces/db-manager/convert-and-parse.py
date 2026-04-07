"""convert-and-parse.py — 손상 .docx 34개를 LibreOffice로 PDF 변환 후 파싱+임베딩.

1. LibreOffice headless로 docx → PDF 변환
2. batch-parse.py의 PDF 파싱 로직으로 처리
3. 임베딩까지 진행
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
import requests

# 설정
SOURCE_DIR = "C:/MES/wta-agents/data/wta-manuals-final"
CONVERT_DIR = "C:/MES/wta-agents/workspaces/db-manager/converted_pdfs"
SOFFICE = "C:/Program Files/LibreOffice/program/soffice.exe"
DB_TABLE = "manual.wta_documents"
EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000
EMBED_BATCH = 64
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# 34개 손상 파일 목록
FAILED_FILES = [
    ("CVD", "MMC-CVD_1_MANUAL_Final.docx"),
    ("CVD", "MMC-CVD_1_MANUAL_Final_Auto_Recovered.docx"),
    ("CVD", "Zhuzhou_CVD_2_User_Manual.docx"),
    ("CVD", "Zhuzhou_CVD_3456_User_Manual.docx"),
    ("Double_Side_Grinder", "WBM_Handler_Dain_Precision_2019.12.10.docx"),
    ("Honing_Inspection", "10S_SW_Manual.docx"),
    ("Inspection", "F1Inspection_Manual_Japanese.docx"),
    ("Inspection", "F1Inspection_Manual_korean_260223_software.docx"),
    ("Inspection", "HIM-F2_UserManual_jp_v1.0.docx"),
    ("Inspection", "Huarui_Inspection_Manual_Final_Chinese.docx"),
    ("Inspection", "Inspection_10S_SW_Manual.docx"),
    ("Inspection", "Inspection_User_Manual_ver.0.12_-_IOI_Revised.docx"),
    ("Inspection", "Korea_Kyocera_F2Inspection_Manual_260220_Revised.docx"),
    ("Inspection", "Korea_Tungsten_F1Inspection_SW_Manual.docx"),
    ("Inspection", "Manual_20230127.docx"),
    ("Inspection", "Manual_20230127_Inspection_zccct.docx"),
    ("Laser_Marking", "Haisheng_1_Unloading_Manual.docx"),
    ("Mask_Auto", "Haisheng_Manual_10.21.docx"),
    ("Mask_Auto", "Haisheng_Manual_KR.docx"),
    ("Single_Side_Grinder", "2_Sintering_Sorter_Manual_1021.docx"),
    ("Sintering_Sorter", "2_Sintering_Sorter_Manual_1021.docx"),
    ("Sintering_Sorter", "4Unit_SW_Manual.docx"),
    ("Sintering_Sorter", "4Unit_SW_Manual_f41488.docx"),
    ("Sintering_Sorter", "Huarui_8_9_Sintering_Sorter_Manual_19p_33p_81_82p.docx"),
    ("Sintering_Sorter", "Huarui_Manual_Sintering_Sorter_Chinese.docx"),
    ("Sintering_Sorter", "Korea_Tungsten_3Unit_SW_Manual.docx"),
    ("Sintering_Sorter", "Korea_Tungsten_4Unit_SW_Manual.docx"),
    ("Sintering_Sorter", "Manual_Sintering_Sorter_Chinese.docx"),
    ("Sintering_Sorter", "OKE_3_Sintering_Sorter_Manual.docx"),
    ("Sintering_Sorter", "SW_Manual.docx"),
    ("Sintering_Sorter", "SW_Manual_20dd67.docx"),
    ("Sintering_Sorter", "Weikai_1_Sintering_Sorter_Manual.docx"),
    ("Sintering_Sorter", "YG1_Sintering_Sorter_SW_Manual_20211014.docx"),
    ("WBM_WVR_Daesung_Honing", "WBM_2th_Handler_20200417.docx"),
    ("WBM_WVR_Daesung_Honing", "WBMHandler_Dain_Precision.docx"),
    ("WBM_WVR_Daesung_Honing", "WBM_Handler_Dain_Precision_2019.12.10.docx"),
]


def load_db_password():
    with open("C:/MES/backend/.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                return line.strip().split("=", 1)[1]
    return None


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


def embed_texts(texts):
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(EMBED_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"Embedding error: {data}")
    return [v[:EMBED_DIM] for v in data["embeddings"]]


def upsert_chunks(conn, chunks_data):
    if not chunks_data:
        return
    sql = f"""INSERT INTO {DB_TABLE} (source_file, file_hash, category, chunk_index, chunk_type,
        page_number, content, image_url, pdf_url, metadata, embedding, updated_at) VALUES %s
        ON CONFLICT (source_file, chunk_index) DO UPDATE SET file_hash=EXCLUDED.file_hash,
        chunk_type=EXCLUDED.chunk_type, page_number=EXCLUDED.page_number, content=EXCLUDED.content,
        image_url=EXCLUDED.image_url, pdf_url=EXCLUDED.pdf_url, metadata=EXCLUDED.metadata,
        embedding=EXCLUDED.embedding, updated_at=now()"""
    template = ("(%(source_file)s, %(file_hash)s, %(category)s, %(chunk_index)s, %(chunk_type)s, "
                "%(page_number)s, %(content)s, %(image_url)s, %(pdf_url)s, %(metadata)s::jsonb, "
                "%(embedding)s::vector, now())")
    with conn.cursor() as cur:
        execute_values(cur, sql, chunks_data, template=template, page_size=50)
    conn.commit()


def convert_docx_to_pdf(docx_path, output_dir):
    """LibreOffice headless로 docx → PDF 변환."""
    os.makedirs(output_dir, exist_ok=True)
    result = subprocess.run(
        [SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    pdf_name = Path(docx_path).stem + ".pdf"
    pdf_path = os.path.join(output_dir, pdf_name)
    if os.path.exists(pdf_path):
        return pdf_path
    return None


def process_pdf(pdf_path, source_file, category, conn):
    """PDF에서 텍스트 추출 → 청크 → 임베딩 → DB 저장."""
    try:
        import fitz
    except ImportError:
        print("  ERROR: pymupdf not installed", flush=True)
        return -1

    # 파일 해시 (원본 docx 기준 - source_file로 매칭)
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    file_hash = h.hexdigest()[:16]

    # DB 중복 확인
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {DB_TABLE} WHERE source_file=%s LIMIT 1", (source_file,))
        if cur.fetchone():
            return 0  # 이미 처리됨

    # PDF 열기
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  ERROR opening PDF: {e}", flush=True)
        return -1

    # 메타데이터
    parts = Path(source_file).stem.split("_")
    manufacturer = parts[0] if parts else "Unknown"
    model = parts[1] if len(parts) > 1 else "Unknown"
    meta_base = {"manufacturer": manufacturer, "model": model,
                 "doc_type": "Manual", "language": "KO", "format": "docx-converted-pdf"}

    # 텍스트 추출 + 청킹
    all_chunks = []
    chunk_idx = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").replace("\x00", "").strip()
        if not text or len(text) < 20:
            continue

        for tc in chunk_text(text):
            tc = tc.strip()
            if len(tc) < 20:
                continue
            all_chunks.append({
                "source_file": source_file, "file_hash": file_hash, "category": category,
                "chunk_index": chunk_idx, "chunk_type": "text", "page_number": page_num + 1,
                "content": tc, "image_url": "", "pdf_url": "",
                "metadata": json.dumps({**meta_base, "page": page_num + 1, "type": "text"},
                                       ensure_ascii=False),
            })
            chunk_idx += 1

    doc.close()

    if not all_chunks:
        print(f"  EMPTY", flush=True)
        return 0

    # 임베딩
    embeddable = [c for c in all_chunks if len(c["content"].strip()) >= 20]
    for i in range(0, len(embeddable), EMBED_BATCH):
        batch = embeddable[i:i + EMBED_BATCH]
        texts = [c["content"] for c in batch]
        for attempt in range(3):
            try:
                embeddings = embed_texts(texts)
                for chunk, emb in zip(batch, embeddings):
                    chunk["embedding"] = str(emb)
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep((attempt + 1) * 5)
                else:
                    print(f"  Embed FAILED: {e}", flush=True)
                    # 임베딩 실패해도 None으로 저장
                    for chunk in batch:
                        chunk["embedding"] = None
        time.sleep(0.3)

    # DB 저장
    for i in range(0, len(embeddable), 50):
        upsert_chunks(conn, embeddable[i:i + 50])

    return len(embeddable)


def main():
    os.makedirs(CONVERT_DIR, exist_ok=True)
    conn = psycopg2.connect(
        host="localhost", port=55432, user="postgres",
        password=load_db_password(), dbname="postgres",
    )

    # 중복 제거
    seen = set()
    unique_files = []
    for cat, fname in FAILED_FILES:
        key = f"{cat}/{fname}"
        if key not in seen:
            seen.add(key)
            unique_files.append((cat, fname))

    total = len(unique_files)
    print(f"[convert] {total} files to process", flush=True)

    ok = 0
    skip = 0
    convert_fail = 0
    parse_fail = 0
    total_chunks = 0

    for i, (cat, fname) in enumerate(unique_files, 1):
        docx_path = os.path.join(SOURCE_DIR, cat, fname)
        if not os.path.exists(docx_path):
            print(f"[{i}/{total}] {cat}/{fname} NOT FOUND", flush=True)
            parse_fail += 1
            continue

        print(f"[{i}/{total}] {cat}/{fname}", end=" ", flush=True)

        # 1. 변환
        pdf_path = convert_docx_to_pdf(docx_path, CONVERT_DIR)
        if not pdf_path:
            print("CONVERT FAIL", flush=True)
            convert_fail += 1
            continue

        # 2. 파싱+임베딩
        n = process_pdf(pdf_path, fname, cat, conn)
        if n > 0:
            print(f"OK ({n} chunks)", flush=True)
            ok += 1
            total_chunks += n
        elif n == 0:
            print("SKIP/EMPTY", flush=True)
            skip += 1
        else:
            print("PARSE FAIL", flush=True)
            parse_fail += 1

    conn.close()
    print(f"\n[DONE] OK={ok}, Skip={skip}, ConvertFail={convert_fail}, ParseFail={parse_fail}, Chunks={total_chunks}", flush=True)


if __name__ == "__main__":
    main()
