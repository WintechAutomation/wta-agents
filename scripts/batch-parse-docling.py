"""batch-parse-docling.py — Docling 기반 매뉴얼 파싱 파이프라인.

PDF + DOCX → Docling 변환 → 텍스트/표/이미지 추출 → 청킹 → 임베딩 → DB 저장.
이미지: 캡션 태깅 + Supabase Storage 업로드 (이미지 자체는 임베딩 안 함, 캡션만 임베딩).

Usage:
  py batch-parse-docling.py --source-dir ../data/wta-manuals-final --category 프레스
  py batch-parse-docling.py --source-dir ../data/wta-manuals-final --category 소결취출기 --limit 5
  py batch-parse-docling.py --file path/to/file.pdf
  py batch-parse-docling.py --source-dir ../data/wta-manuals-final --category 프레스 --dry-run
  py batch-parse-docling.py --source-dir ../data/wta-manuals-final --category 프레스 --no-embed
  py batch-parse-docling.py --source-dir ../data/wta-manuals-final --table manual.wta_documents
"""

import argparse
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import execute_values
import requests

from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableStructureOptions,
    TableFormerMode,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode

# -- Config --
BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_SOURCE_DIR = os.path.join(BASE_DIR, "data", "wta-manuals-final")
PARSED_DIR = os.path.join(BASE_DIR, "data", "wta_parsed")
IMAGE_DIR = os.path.join(BASE_DIR, "data", "wta_images")
PROGRESS_FILE = os.path.join(BASE_DIR, "data", "manual_progress.json")

OLLAMA_URL = "http://182.224.6.147:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000
EMBED_BATCH = 16
EMBED_DELAY = 0.5
CHUNK_SIZE = 1000       # 텍스트 청크 최대 (약 512토큰)
CHUNK_OVERLAP = 100     # 오버랩 (약 50토큰)
TABLE_MAX_SIZE = 2000   # 표 청크 최대
MIN_CHUNK_LEN = 50      # 최소 청크 길이 (미만 시 병합)
DB_TABLE = "manual.wta_documents"

SUPPORTED_EXTS = {".pdf", ".docx"}

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

# Supabase Storage 설정
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

logging.basicConfig(
    level=logging.INFO,
    format="[docling] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("docling-parse")

# -- Docling 컨버터 (모듈 레벨 싱글턴) --
_converter = None
_no_ocr = False


def get_converter():
    """Docling DocumentConverter 싱글턴."""
    global _converter
    if _converter is not None:
        return _converter

    pipeline_options = PdfPipelineOptions()
    # 이미지는 PyMuPDF로 별도 추출 (Docling은 텍스트+표만)
    pipeline_options.generate_picture_images = False
    pipeline_options.generate_page_images = False
    # PDF 텍스트 레이어 우선 (OCR 최소화 → 속도 향상)
    pipeline_options.force_backend_text = True
    pipeline_options.do_ocr = not _no_ocr
    # 테이블: 정확 모드
    pipeline_options.table_structure_options = TableStructureOptions(
        mode=TableFormerMode.ACCURATE,
        do_cell_matching=True,
    )

    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    return _converter


# -- 한글→영어 매핑 (Supabase Storage 경로용) --
CATEGORY_MAP = {
    "CBN": "CBN",
    "CVD": "CVD",
    "PVD": "PVD",
    "WBM_WVR대성호닝": "WBM_WVR_Daesung_Honing",
    "검사기": "Inspection",
    "라벨부착기": "Labeling",
    "레이저마킹기": "Laser_Marking",
    "리팔레팅": "Repalleting",
    "마스크자동기": "Mask_Auto",
    "마코호": "Macoho",
    "상하면연삭기": "Double_Side_Grinder",
    "소결취출기": "Sintering_Sorter",
    "편면연삭기": "Single_Side_Grinder",
    "포장기": "Packaging",
    "프레스": "Press",
    "호닝기": "Honing",
    "호닝형상검사기": "Honing_Inspection",
    "후지산기연삭핸들러": "Fujisanki_Grinding_Handler",
}

# 파일명에 자주 등장하는 한글→영어 단어 매핑
WORD_MAP = {
    # 장비/기계 유형
    "소결취출기": "Sintering_Sorter",
    "프레스": "Press",
    "핸들러": "Handler",
    "연삭기": "Grinder",
    "검사기": "Inspection",
    "마킹기": "Marking",
    "포장기": "Packaging",
    "호닝기": "Honing",
    "편면연삭기": "Single_Side_Grinder",
    "상하면": "Double_Side",
    "라벨부착기": "Labeling",
    "리팔레팅": "Repalleting",
    "마스크자동기": "Mask_Auto",
    # 문서 유형
    "유지보수": "Maintenance",
    "유지 보수": "Maintenance",
    "사용자 매뉴얼": "User_Manual",
    "사용자매뉴얼": "User_Manual",
    "매뉴얼": "Manual",
    "메뉴얼": "Manual",
    "취급설명서": "Instruction_Manual",
    "설비 외형": "Equipment_Outline",
    "외형": "Outline",
    # 회사/고객명
    "다인정공": "Dain_Precision",
    "한국야금": "Korea_Tungsten",
    "한국교세라": "Korea_Kyocera",
    "교세라": "Kyocera",
    "몰디노": "Moldino",
    "스탈리": "Stahli",
    "후지산키": "Fujisanki",
    "후지산기": "Fujisanki",
    "대성호닝": "Daesung_Honing",
    "마코호": "Macoho",
    "화루이": "Huarui",
    "기후": "Gifu",
    "하이썽": "Haisheng",
    # 동작/상태
    "번역 완료": "Translated",
    "완성본": "Final",
    "사진수정본": "Photo_Revised",
    "소모품 업데이트 버전": "Consumables_Updated",
    "작업자": "Operator",
    # 기타 기술 용어
    "컨베어타입": "Conveyor_Type",
    "하부": "Lower",
    "상부": "Upper",
    "중국어": "Chinese",
    "일본어": "Japanese",
    "연삭": "Grinding",
    "호닝형상": "Honing_Shape",
    "레이저": "Laser",
}

# 긴 키부터 매칭 (부분 매칭 방지)
_SORTED_WORDS = sorted(WORD_MAP.keys(), key=len, reverse=True)


# -- Supabase --
def safe_storage_name(name):
    """Supabase Storage용 한글→영어 변환. ASCII만 허용."""
    # 이미 ASCII-only면 그대로
    if re.match(r"^[a-zA-Z0-9._() #,-]+$", name):
        return re.sub(r"[^a-zA-Z0-9._-]", "_", name).strip("_")

    result = name
    # 한글 단어를 영어로 치환 (긴 키부터)
    for kr, en in zip(_SORTED_WORDS, [WORD_MAP[k] for k in _SORTED_WORDS]):
        result = result.replace(kr, en)

    # 남은 non-ASCII 문자 제거, 공백/특수문자 → underscore
    result = re.sub(r"[^a-zA-Z0-9._-]", "_", result)
    # 연속 underscore 정리
    result = re.sub(r"_+", "_", result).strip("_")

    if not result:
        return hashlib.md5(name.encode("utf-8")).hexdigest()[:12]
    return result


def upload_to_supabase(data_bytes, storage_path, mime="image/png"):
    """바이트 데이터를 Supabase Storage에 업로드."""
    if not SERVICE_ROLE_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": mime,
        "x-upsert": "true",
    }
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}",
        headers=headers,
        data=data_bytes,
        timeout=120,
    )
    if resp.status_code in (200, 201):
        return f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
    return None


def upload_file_to_supabase(local_path, storage_path):
    """로컬 파일을 Supabase Storage에 업로드."""
    if not SERVICE_ROLE_KEY:
        return None
    ext = os.path.splitext(local_path)[1].lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
        ".md": "text/markdown; charset=utf-8",
    }.get(ext, "application/octet-stream")
    with open(local_path, "rb") as f:
        return upload_to_supabase(f.read(), storage_path, mime)


def ensure_bucket():
    """Supabase 버킷 생성 확인."""
    if not SERVICE_ROLE_KEY:
        return
    headers = {"Authorization": f"Bearer {SERVICE_ROLE_KEY}", "apikey": SERVICE_ROLE_KEY}
    resp = requests.get(
        f"{SUPABASE_URL}/storage/v1/bucket/{SUPABASE_BUCKET}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code != 200:
        requests.post(
            f"{SUPABASE_URL}/storage/v1/bucket",
            headers={**headers, "Content-Type": "application/json"},
            json={"id": SUPABASE_BUCKET, "name": SUPABASE_BUCKET, "public": True},
            timeout=10,
        )


# -- 텍스트 청킹 (개선) --
def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """단락 기반 텍스트 청킹 (기본 함수, 하위 호환용)."""
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
                    chunks.append(para[j : j + size])
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


def _split_large_table(table_md, max_size=TABLE_MAX_SIZE):
    """대형 표를 헤더+N행 단위로 분할."""
    lines = table_md.strip().split("\n")
    if len(lines) < 3:
        return [table_md]

    # 헤더: 첫 줄 + 구분줄 (|---|---|)
    header_lines = []
    data_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i < 2 or (i == 2 and re.match(r"^\|[\s:|-]+\|$", stripped)):
            header_lines.append(line)
        else:
            data_lines.append(line)

    if not data_lines:
        return [table_md]

    header = "\n".join(header_lines)
    chunks = []
    current_rows = []
    current_len = len(header)

    for row in data_lines:
        row_len = len(row) + 1
        if current_len + row_len > max_size and current_rows:
            chunks.append(header + "\n" + "\n".join(current_rows))
            current_rows = []
            current_len = len(header)
        current_rows.append(row)
        current_len += row_len

    if current_rows:
        chunks.append(header + "\n" + "\n".join(current_rows))

    return chunks


def _merge_short_chunks(chunks, min_len=MIN_CHUNK_LEN, max_len=CHUNK_SIZE):
    """짧은 청크를 인접 청크에 병합."""
    if not chunks:
        return []

    merged = []
    buffer = ""

    for chunk in chunks:
        if len(chunk) < min_len:
            # 짧은 청크: 버퍼에 축적
            buffer = (buffer + "\n\n" + chunk).strip() if buffer else chunk
        else:
            if buffer:
                # 버퍼를 현재 청크 앞에 합치기
                combined = buffer + "\n\n" + chunk
                if len(combined) <= max_len:
                    merged.append(combined)
                    buffer = ""
                    continue
                else:
                    # 버퍼가 충분히 크면 독립 청크
                    if len(buffer) >= min_len:
                        merged.append(buffer)
                    buffer = ""
            merged.append(chunk)

    # 남은 버퍼
    if buffer:
        if merged and len(merged[-1]) + len(buffer) + 2 <= max_len:
            merged[-1] = merged[-1] + "\n\n" + buffer
        elif len(buffer) >= min_len:
            merged.append(buffer)

    return merged


def smart_chunk_markdown(md_text, source_file=""):
    """개선된 마크다운 청킹.

    Returns: list of dict {content, chunk_type, heading, page_number}
    - 표: 전체 유지 (2000자 초과 시 분할)
    - 텍스트: 1000자 단위 + 100 오버랩
    - 50자 미만 청크 병합
    - 섹션 제목 추적
    - Contextual prefix 추가
    """
    chunks = []
    current_heading = ""

    # 섹션 단위로 분할
    sections = re.split(r"(?=^#{1,4}\s)", md_text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        lines = section.split("\n")

        # 섹션 제목 추출
        first_line = lines[0].strip()
        heading_match = re.match(r"^#{1,4}\s+(.+)", first_line)
        if heading_match:
            current_heading = heading_match.group(1).strip()

        # 라인을 텍스트/표 블록으로 분류
        text_buffer = []
        table_buffer = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            is_table_line = stripped.startswith("|") and stripped.endswith("|")

            if is_table_line:
                if text_buffer and not in_table:
                    # 텍스트 버퍼 플러시
                    text_block = "\n".join(text_buffer).strip()
                    if text_block:
                        for tc in chunk_text(text_block, CHUNK_SIZE, CHUNK_OVERLAP):
                            chunks.append({
                                "content": tc.strip(),
                                "chunk_type": "text",
                                "heading": current_heading,
                                "page_number": None,
                            })
                    text_buffer = []
                table_buffer.append(line)
                in_table = True
            else:
                if in_table and table_buffer:
                    # 표 버퍼 플러시
                    table_md = "\n".join(table_buffer).strip()
                    if len(table_md) > TABLE_MAX_SIZE:
                        for sub_table in _split_large_table(table_md, TABLE_MAX_SIZE):
                            chunks.append({
                                "content": sub_table,
                                "chunk_type": "table",
                                "heading": current_heading,
                                "page_number": None,
                            })
                    elif table_md:
                        chunks.append({
                            "content": table_md,
                            "chunk_type": "table",
                            "heading": current_heading,
                            "page_number": None,
                        })
                    table_buffer = []
                    in_table = False
                text_buffer.append(line)

        # 남은 버퍼 플러시
        if table_buffer:
            table_md = "\n".join(table_buffer).strip()
            if len(table_md) > TABLE_MAX_SIZE:
                for sub_table in _split_large_table(table_md, TABLE_MAX_SIZE):
                    chunks.append({
                        "content": sub_table,
                        "chunk_type": "table",
                        "heading": current_heading,
                        "page_number": None,
                    })
            elif table_md:
                chunks.append({
                    "content": table_md,
                    "chunk_type": "table",
                    "heading": current_heading,
                    "page_number": None,
                })

        if text_buffer:
            text_block = "\n".join(text_buffer).strip()
            if text_block:
                for tc in chunk_text(text_block, CHUNK_SIZE, CHUNK_OVERLAP):
                    chunks.append({
                        "content": tc.strip(),
                        "chunk_type": "text",
                        "heading": current_heading,
                        "page_number": None,
                    })

    # 짧은 텍스트 청크 병합 (표 청크는 제외)
    text_chunks = [c for c in chunks if c["chunk_type"] == "text"]
    table_chunks = [c for c in chunks if c["chunk_type"] != "text"]

    text_contents = [c["content"] for c in text_chunks]
    merged_contents = _merge_short_chunks(text_contents, MIN_CHUNK_LEN, CHUNK_SIZE)

    # 병합된 텍스트 청크 재구성 (heading 매칭)
    merged_text_chunks = []
    heading_map = {c["content"]: c["heading"] for c in text_chunks}
    for mc in merged_contents:
        heading = heading_map.get(mc, "")
        if not heading:
            # 병합된 경우 원본 중 첫 매칭 heading
            for tc in text_chunks:
                if tc["content"] in mc:
                    heading = tc["heading"]
                    break
        merged_text_chunks.append({
            "content": mc,
            "chunk_type": "text",
            "heading": heading,
            "page_number": None,
        })

    # 원래 순서 유지: 표/텍스트 인터리브
    final_chunks = []
    text_iter = iter(merged_text_chunks)
    table_iter = iter(table_chunks)

    # 원래 chunks 순서대로 타입별 재배치
    next_text = next(text_iter, None)
    next_table = next(table_iter, None)
    for orig in chunks:
        if orig["chunk_type"] == "text" and next_text:
            final_chunks.append(next_text)
            next_text = next(text_iter, None)
        elif orig["chunk_type"] != "text" and next_table:
            final_chunks.append(next_table)
            next_table = next(table_iter, None)
    # 남은 것들
    while next_text:
        final_chunks.append(next_text)
        next_text = next(text_iter, None)
    while next_table:
        final_chunks.append(next_table)
        next_table = next(table_iter, None)

    # Contextual prefix 추가 + 빈 청크 필터
    doc_name = os.path.splitext(os.path.basename(source_file))[0] if source_file else ""
    result = []
    for c in final_chunks:
        content = c["content"].strip()
        if not content or len(content) < MIN_CHUNK_LEN:
            continue
        # prefix: "문서: {파일명} > 섹션: {헤딩}" (임베딩 품질 향상)
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
    """Ollama Qwen3-Embedding 서버 배치 임베딩."""
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"임베딩 응답 오류: {data}")
    # Matryoshka: 4096→2000 차원 잘라서 반환
    return [v[:EMBED_DIM] for v in data["embeddings"]]


# -- DB --
def ensure_schema(conn, table_name):
    """테이블 및 인덱스 생성."""
    schema = table_name.split(".")[0] if "." in table_name else "public"
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} (
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
            metadata JSONB DEFAULT '{{}}',
            embedding vector({EMBED_DIM}),
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (source_file, chunk_index)
        )""")
        idx_name = table_name.replace(".", "_") + "_embedding_idx"
        cur.execute(f"""CREATE INDEX IF NOT EXISTS {idx_name}
            ON {table_name} USING hnsw (embedding vector_cosine_ops)""")
    conn.commit()


def upsert_chunks(conn, chunks_data, table_name):
    """청크 데이터 DB upsert."""
    if not chunks_data:
        return
    sql = f"""INSERT INTO {table_name}
        (source_file, file_hash, category, chunk_index, chunk_type,
         page_number, content, image_url, pdf_url, metadata, embedding, updated_at)
        VALUES %s
        ON CONFLICT (source_file, chunk_index) DO UPDATE SET
            file_hash=EXCLUDED.file_hash, chunk_type=EXCLUDED.chunk_type,
            page_number=EXCLUDED.page_number, content=EXCLUDED.content,
            image_url=EXCLUDED.image_url, pdf_url=EXCLUDED.pdf_url,
            metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding,
            updated_at=now()"""
    template = (
        "(%(source_file)s, %(file_hash)s, %(category)s, %(chunk_index)s, %(chunk_type)s, "
        "%(page_number)s, %(content)s, %(image_url)s, %(pdf_url)s, "
        "%(metadata)s::jsonb, %(embedding)s::vector, now())"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, chunks_data, template=template, page_size=50)
    conn.commit()


# -- Progress tracking (file-lock safe) --
LOCK_FILE = PROGRESS_FILE + ".lock"


def _acquire_lock(lock_fd, timeout=10):
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
        for _ in range(3):
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
            log.warning(f"  Progress lock timeout: {rel_path}")
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


# -- 2단계: PyMuPDF 이미지 추출 + Docling 맥락 캡션 --
MAX_RENDER_PIXELS = 4000 * 4000  # 16MP 상한 (메모리 보호)
RENDER_DPI = 150
MIN_IMAGE_SIZE = 5000  # 최소 이미지 바이트 (아이콘 등 제외)


def build_page_context(md_text):
    """Docling Markdown에서 페이지별 섹션 헤딩 맵 구축.

    Markdown에 명시적 페이지 번호가 없으므로, ## 헤딩을 순서대로 수집하여
    이미지 캡션 태깅에 활용.
    Returns: list of section headings in order.
    """
    headings = []
    for line in md_text.split("\n"):
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if text and len(text) < 80:
                headings.append({"level": level, "text": text})
    return headings


def extract_images_pymupdf(file_path, md_text, safe_stem, category="", dry_run=False):
    """PyMuPDF로 PDF 이미지 추출 + Docling 파싱 맥락으로 캡션 태깅.

    Returns: list of dict with keys: page, caption, tag, image_url, local_path
    """
    if not file_path.lower().endswith(".pdf"):
        return []

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        log.warning(f"    PyMuPDF open failed: {e}")
        return []

    headings = build_page_context(md_text)
    results = []
    img_idx = 0

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        images = page.get_images(full=True)
        if not images:
            continue

        # 페이지 텍스트에서 가장 가까운 헤딩 추출
        page_text = page.get_text("text").replace("\x00", "").strip()
        page_heading = ""
        # 페이지 텍스트의 첫 줄 중 짧은 것을 헤딩 후보로
        for line in page_text.split("\n"):
            line = line.strip()
            if line and 5 < len(line) < 50:
                page_heading = line
                break

        # Docling 헤딩 목록에서 매칭 (순서 기반 근사치)
        section_heading = ""
        if headings and page_idx < len(headings):
            section_heading = headings[min(page_idx, len(headings) - 1)]["text"]
        elif headings:
            section_heading = headings[-1]["text"]

        # 섹션 프리픽스 생성
        section_prefix = ""
        if section_heading:
            m = re.match(r"^(\d+(?:\.\d+)*)\s*[.\s]*(.+)", section_heading)
            if m:
                num_part = m.group(1).replace(".", "-")
                title_part = re.sub(r'[\\/:*?"<>|\s]+', "_", m.group(2).strip())[:20]
                section_prefix = f"{num_part}_{title_part}"
            else:
                section_prefix = re.sub(r'[\\/:*?"<>|\s]+', "_", section_heading)[:25]

        for img_info in images:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image or len(base_image["image"]) < MIN_IMAGE_SIZE:
                    continue  # 아이콘/장식 제외
            except Exception:
                continue

            img_bytes = base_image["image"]
            ext = base_image.get("ext", "png")
            if ext not in ("png", "jpg", "jpeg"):
                ext = "png"

            # 캡션: 페이지 헤딩 or 섹션 헤딩
            caption_tag = re.sub(r"[^\w가-힣\s-]", "", page_heading or "image")[:30].strip().replace(" ", "_")
            if not caption_tag:
                caption_tag = "image"

            # 파일명: p{page}_{section}_{caption}.{ext}
            if section_prefix:
                img_filename = f"p{page_idx + 1}_{section_prefix}_{caption_tag}.{ext}"
            else:
                img_filename = f"p{page_idx + 1}_{caption_tag}.{ext}"

            # 캡션 텍스트 (DB 저장용)
            caption_text = f"[p.{page_idx + 1}] "
            if section_heading:
                caption_text += f"{section_heading} — "
            caption_text += page_heading or "image"

            # 로컬 저장
            local_path = ""
            image_url = ""
            if not dry_run:
                local_img_dir = os.path.join(IMAGE_DIR, safe_stem)
                os.makedirs(local_img_dir, exist_ok=True)
                local_path = os.path.join(local_img_dir, img_filename)
                with open(local_path, "wb") as f:
                    f.write(img_bytes)

                # Supabase 업로드: wta/{카테고리}/{파일명}/{이미지}
                storage_stem = safe_storage_name(safe_stem)
                storage_cat = safe_storage_name(category) if category else "uncategorized"
                storage_filename = safe_storage_name(os.path.splitext(img_filename)[0]) + f".{ext}"
                storage_path = f"wta/{storage_cat}/{storage_stem}/{storage_filename}"
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
                image_url = upload_to_supabase(img_bytes, storage_path, mime) or ""

            results.append({
                "page": page_idx + 1,
                "caption": caption_text[:300],
                "heading": page_heading[:100],
                "section": section_heading[:100],
                "tag": img_filename,
                "image_url": image_url,
                "local_path": local_path,
            })
            img_idx += 1

    doc.close()
    return results


# -- Docling 변환 + 청킹 --
def process_single_file(file_path, category, conn, table_name, dry_run=False, no_embed=False):
    """Docling으로 단일 파일 처리. 반환: 청크 수 또는 -1 (에러)."""
    filename = Path(file_path).name
    source_file = filename
    rel_path = f"{category}/{filename}"

    # 진행 상태 확인
    progress = load_progress()
    file_status = progress.get("files", {}).get(rel_path, {}).get("status", "")
    if file_status in ("parsed", "embedded"):
        log.info(f"  Skip ({file_status}): {filename}")
        return 0

    # 파일 크기 제한 (80MB)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 80:
        log.warning(f"  Skip (too large: {file_size_mb:.0f}MB): {filename}")
        update_file_progress(rel_path, "skipped")
        return -1

    # 파일 해시
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    file_hash = h.hexdigest()[:16]

    # DB 중복 확인
    if not dry_run and not no_embed:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {table_name} WHERE source_file=%s AND file_hash=%s LIMIT 1",
                (source_file, file_hash),
            )
            if cur.fetchone():
                log.info(f"  Skip (already indexed): {filename}")
                return 0

    # Docling 변환
    converter = get_converter()
    t0 = time.time()
    try:
        result = converter.convert(str(file_path))
    except Exception as e:
        log.error(f"  Docling 변환 실패: {filename} — {e}")
        update_file_progress(rel_path, "error")
        return -1
    elapsed = time.time() - t0

    doc = result.document

    # Markdown 내보내기 (PLACEHOLDER 모드)
    md_text = doc.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)
    # <!-- image --> placeholder 제거 (이미지는 별도 처리)
    md_text = re.sub(r"\s*<!-- image -->\s*", "\n\n", md_text)
    md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()

    if not md_text or len(md_text) < 30:
        log.warning(f"  No content: {filename}")
        update_file_progress(rel_path, "skipped")
        return 0

    # -- 2단계: PyMuPDF 이미지 추출 + Docling 맥락 캡션 태깅 --
    file_stem = Path(file_path).stem
    # 파일시스템 안전 이름 (한글 유지, 위험 특수문자만 치환)
    safe_stem = re.sub(r'[\\/:*?"<>|]', "_", file_stem)

    image_results = extract_images_pymupdf(file_path, md_text, safe_stem, category=category, dry_run=dry_run)
    uploaded_images = sum(1 for r in image_results if r["image_url"])

    # 이미지 캡션 청크 생성
    image_chunks = []
    for img_r in image_results:
        image_chunks.append({
            "source_file": source_file,
            "file_hash": file_hash,
            "category": category,
            "chunk_type": "image_caption",
            "page_number": img_r["page"],
            "content": img_r["caption"],
            "image_url": img_r["image_url"],
            "pdf_url": "",
            "metadata": json.dumps(
                {
                    "type": "image_caption",
                    "heading": img_r["heading"],
                    "section": img_r["section"],
                    "format": Path(file_path).suffix.lower(),
                    "image_file": img_r["tag"],
                },
                ensure_ascii=False,
            ),
        })

    # -- 텍스트/테이블 청킹 (smart_chunk_markdown 사용) --
    file_fmt = Path(file_path).suffix.lower()
    smart_chunks = smart_chunk_markdown(md_text, source_file)

    all_chunks = []
    for chunk_idx, sc in enumerate(smart_chunks):
        all_chunks.append({
            "source_file": source_file,
            "file_hash": file_hash,
            "category": category,
            "chunk_index": chunk_idx,
            "chunk_type": sc["chunk_type"],
            "page_number": sc.get("page_number"),
            "content": sc["content"],
            "image_url": "",
            "pdf_url": "",
            "metadata": json.dumps(
                {
                    "type": sc["chunk_type"],
                    "format": file_fmt,
                    "heading": sc.get("heading", ""),
                },
                ensure_ascii=False,
            ),
        })

    # 이미지 캡션 청크 추가 (chunk_index 이어서)
    next_idx = len(all_chunks)
    for ic in image_chunks:
        ic["chunk_index"] = next_idx
        all_chunks.append(ic)
        next_idx += 1

    if not all_chunks:
        log.warning(f"  No chunks: {filename}")
        update_file_progress(rel_path, "skipped")
        return 0

    # Markdown 저장 (로컬)
    os.makedirs(PARSED_DIR, exist_ok=True)
    md_path = os.path.join(PARSED_DIR, f"{Path(file_path).stem}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    # Supabase에 MD + 원본 PDF 업로드: wta/{카테고리}/{파일명}/
    storage_cat = safe_storage_name(category)
    storage_stem = safe_storage_name(safe_stem)
    storage_base = f"wta/{storage_cat}/{storage_stem}"
    # parsed.md 업로드
    upload_to_supabase(
        md_text.encode("utf-8"),
        f"{storage_base}/parsed.md",
        "text/markdown; charset=utf-8",
    )
    # original PDF/DOCX 업로드
    file_ext = Path(file_path).suffix.lower()
    file_mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(file_ext, "application/octet-stream")
    upload_file_to_supabase(file_path, f"{storage_base}/original{file_ext}")

    if dry_run:
        types = Counter(c["chunk_type"] for c in all_chunks)
        log.info(
            f"  [DRY] {filename}: {len(all_chunks)} chunks {dict(types)}, "
            f"{len(image_results)} imgs, MD {len(md_text)} chars, {elapsed:.1f}s"
        )
        return len(all_chunks)

    update_file_progress(rel_path, "parsed", chunks=len(all_chunks))

    if no_embed:
        log.info(
            f"  PARSED: {filename} — {len(all_chunks)} chunks, "
            f"{uploaded_images} imgs uploaded, {elapsed:.1f}s"
        )
        return len(all_chunks)

    # 임베딩 (image_caption 포함 — 캡션 텍스트만 임베딩)
    embeddable = [c for c in all_chunks if c["content"] and len(c["content"].strip()) >= 20]
    all_embeddings = []

    for i in range(0, len(embeddable), EMBED_BATCH):
        batch = embeddable[i : i + EMBED_BATCH]
        texts = [c["content"] for c in batch]
        for attempt in range(3):
            try:
                all_embeddings.extend(embed_texts(texts))
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep((attempt + 1) * 3)
                else:
                    log.error(f"  임베딩 실패: {filename} batch {i}: {e}")
                    return -1
        if i + EMBED_BATCH < len(embeddable):
            time.sleep(EMBED_DELAY)

    for chunk, emb in zip(embeddable, all_embeddings):
        chunk["embedding"] = str(emb)

    # DB 저장
    for i in range(0, len(embeddable), 50):
        upsert_chunks(conn, embeddable[i : i + 50], table_name)

    update_file_progress(rel_path, "embedded", chunks=len(embeddable))
    log.info(
        f"  OK: {filename} — {len(embeddable)} chunks, "
        f"{uploaded_images} imgs, {elapsed:.1f}s"
    )
    return len(embeddable)


# -- Embed-only: 이미 파싱된 MD 파일에서 임베딩만 수행 --
def embed_only_from_parsed(category, conn, table_name, embed_batch=None, limit=None, force=False):
    """wta_parsed/ 디렉토리의 MD 파일을 읽어 임베딩 + DB 저장."""
    batch_size = embed_batch or EMBED_BATCH
    md_files = sorted([f for f in os.listdir(PARSED_DIR) if f.endswith(".md")])

    # 카테고리 필터: wta-manuals-ready/{category}/ 에 있는 파일명과 매칭
    if category:
        cat_dir = os.path.join(DEFAULT_SOURCE_DIR, category)
        if os.path.isdir(cat_dir):
            src_stems = set(Path(f).stem for f in os.listdir(cat_dir)
                           if Path(f).suffix.lower() in SUPPORTED_EXTS)
            # MD 파일명에서 확장자 제거 후 소스와 매칭
            md_files = [f for f in md_files if f.replace(".md", "") in src_stems]

    if limit:
        md_files = md_files[:limit]

    log.info(f"Embed-only: {len(md_files)} parsed files from {category or 'all'}")
    total_embedded = 0
    processed = 0
    errors = 0

    for i, md_file in enumerate(md_files):
        standard_name = md_file.replace(".md", "")
        # 소스 파일 확장자 찾기
        source_file = standard_name + ".pdf"
        for ext in [".pdf", ".docx"]:
            candidate = standard_name + ext
            # 카테고리별 검색
            if category:
                if os.path.isfile(os.path.join(DEFAULT_SOURCE_DIR, category, candidate)):
                    source_file = candidate
                    break
            else:
                # 전체 카테고리에서 검색
                for cat in os.listdir(DEFAULT_SOURCE_DIR):
                    if os.path.isfile(os.path.join(DEFAULT_SOURCE_DIR, cat, candidate)):
                        source_file = candidate
                        if not category:
                            category = cat
                        break

        rel_path = f"{category}/{source_file}" if category else source_file

        # progress 체크: embedded 상태면 스킵 (force 모드면 무시)
        if not force:
            progress = load_progress()
            file_status = progress.get("files", {}).get(rel_path, {}).get("status", "")
            if file_status == "embedded":
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
        file_hash = hashlib.sha256(md_content.encode()).hexdigest()[:16]

        # DB 중복 체크 (force 모드면 무시)
        if not force:
            with conn.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {table_name} WHERE source_file=%s AND file_hash=%s LIMIT 1",
                            (source_file, file_hash))
                if cur.fetchone():
                    log.info(f"    Skip (already in DB): {source_file}")
                    update_file_progress(rel_path, "embedded")
                    continue

        # 기존 레코드 삭제 (재임베딩 시)
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table_name} WHERE source_file=%s", (source_file,))
            if cur.rowcount > 0:
                log.info(f"    Deleted {cur.rowcount} old records")
        conn.commit()

        # PDF URL (Supabase)
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', source_file)
        pdf_url = f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/wta/{category}/{safe_name}"

        # MD를 청크로 분할 (smart_chunk_markdown 사용)
        smart_chunks = smart_chunk_markdown(md_content, source_file)
        chunks_data = []
        for chunk_idx, sc in enumerate(smart_chunks):
            chunks_data.append({
                "source_file": source_file, "file_hash": file_hash,
                "category": category or "", "chunk_index": chunk_idx,
                "chunk_type": sc["chunk_type"], "page_number": sc.get("page_number"),
                "content": sc["content"], "image_url": "", "pdf_url": pdf_url,
                "metadata": json.dumps({
                    "category": category, "type": sc["chunk_type"],
                    "heading": sc.get("heading", ""),
                }, ensure_ascii=False),
            })

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
                    all_embeddings.extend(embed_texts(texts))
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
                time.sleep(0.1)

        if not embed_ok:
            errors += 1
            continue

        # 임베딩 결합
        for chunk, emb in zip(embeddable, all_embeddings):
            chunk["embedding"] = str(emb)

        # DB 저장
        for bi in range(0, len(embeddable), 50):
            upsert_chunks(conn, embeddable[bi:bi + 50], table_name)

        # progress 업데이트
        update_file_progress(rel_path, "embedded", chunks=len(embeddable))
        total_embedded += len(embeddable)
        processed += 1
        log.info(f"    OK: {len(embeddable)} chunks embedded")

    log.info(f"\nEmbed-only done: {processed} files, {total_embedded} chunks, {errors} errors")
    return total_embedded


# -- Main --
def main():
    parser = argparse.ArgumentParser(description="Docling 기반 매뉴얼 파싱 파이프라인")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR, help="소스 디렉토리")
    parser.add_argument("--category", help="카테고리 (하위 폴더명)")
    parser.add_argument("--file", help="단일 파일 처리")
    parser.add_argument("--table", default=DB_TABLE, help=f"DB 테이블명 (기본: {DB_TABLE})")
    parser.add_argument("--limit", type=int, help="처리할 파일 수 제한")
    parser.add_argument("--dry-run", action="store_true", help="분석만 (DB 저장 안 함)")
    parser.add_argument("--no-embed", action="store_true", help="파싱만 (임베딩 안 함)")
    parser.add_argument("--no-ocr", action="store_true", help="OCR 비활성화 (텍스트 레이어만 사용)")
    parser.add_argument("--embed-only", action="store_true", help="파싱 완료된 MD에서 임베딩만 수행")
    parser.add_argument("--force", action="store_true", help="DB 해시 중복 무시 (재임베딩 시 사용)")
    parser.add_argument("--embed-batch", type=int, default=None, help="임베딩 배치 크기 (기본: 16)")
    args = parser.parse_args()

    # OCR 설정 (컨버터 생성 전에 설정)
    global _no_ocr
    if args.no_ocr:
        _no_ocr = True
        log.info("OCR 비활성화 (force_backend_text만 사용)")

    table_name = args.table

    # --embed-only 모드
    if args.embed_only:
        log.info(f"Embed-only 모드: {PARSED_DIR} → {table_name}")
        conn = psycopg2.connect(**DB_CONFIG)
        ensure_schema(conn, table_name)
        embed_only_from_parsed(
            category=args.category or "",
            conn=conn,
            table_name=table_name,
            embed_batch=args.embed_batch,
            limit=args.limit,
            force=args.force,
        )
        conn.close()
        return

    log.info("=" * 60)
    log.info("Docling 매뉴얼 파싱 파이프라인")
    log.info(f"  소스: {args.source_dir}")
    log.info(f"  테이블: {table_name}")
    log.info(f"  임베딩: {OLLAMA_URL} ({EMBED_MODEL}, {EMBED_DIM}dim)")
    log.info(f"  이미지: 캡션 태깅 + Supabase 업로드")
    log.info("=" * 60)

    # Supabase 버킷 확인
    ensure_bucket()

    # DB 연결
    conn = None
    if not args.dry_run:
        conn = psycopg2.connect(**DB_CONFIG)
        ensure_schema(conn, table_name)

    # 파일 목록 수집
    files = []
    if args.file:
        fp = Path(args.file)
        if fp.exists() and fp.suffix.lower() in SUPPORTED_EXTS:
            files.append((str(fp), fp.parent.name))
        else:
            log.error(f"파일 없음 또는 미지원 형식: {args.file}")
            return
    elif args.category:
        cat_dir = Path(args.source_dir) / args.category
        if not cat_dir.is_dir():
            log.error(f"카테고리 디렉토리 없음: {cat_dir}")
            return
        for fp in sorted(cat_dir.iterdir()):
            if fp.is_file() and fp.suffix.lower() in SUPPORTED_EXTS:
                files.append((str(fp), args.category))
    else:
        src = Path(args.source_dir)
        for cat_dir in sorted(src.iterdir()):
            if not cat_dir.is_dir():
                continue
            for fp in sorted(cat_dir.iterdir()):
                if fp.is_file() and fp.suffix.lower() in SUPPORTED_EXTS:
                    files.append((str(fp), cat_dir.name))

    if args.limit:
        files = files[: args.limit]

    log.info(f"\n처리 대상: {len(files)}개 파일")

    total_chunks = 0
    processed = 0
    errors = 0
    skipped = 0

    for i, (fp, cat) in enumerate(files):
        log.info(f"\n[{i + 1}/{len(files)}] {Path(fp).name}")
        try:
            n = process_single_file(
                fp,
                cat,
                conn,
                table_name,
                dry_run=args.dry_run,
                no_embed=args.no_embed,
            )
            if n > 0:
                total_chunks += n
                processed += 1
            elif n == 0:
                skipped += 1
            else:
                errors += 1
        except Exception as e:
            log.error(f"  처리 오류: {Path(fp).name} — {e}")
            errors += 1

    log.info("\n" + "=" * 60)
    log.info(f"완료: {processed}개 처리, {skipped}개 스킵, {errors}개 에러")
    log.info(f"총 청크: {total_chunks}개")
    log.info("=" * 60)

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
