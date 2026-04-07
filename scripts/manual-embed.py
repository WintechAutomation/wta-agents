"""manual-embed.py — PDF 매뉴얼 파싱 + 임베딩 파이프라인.

PDF에서 텍스트/이미지/표를 추출하여 Qwen3-Embedding-8B 임베딩 후 pgvector에 저장.
이미지는 Supabase Storage 버킷 "vector"에 업로드.

실행:
  python manual-embed.py                              # data/manuals/ 전체 처리
  python manual-embed.py --dir data/manuals/1_robot    # 특정 카테고리만
  python manual-embed.py --file path/to/manual.pdf     # 단일 파일
  python manual-embed.py --dry-run                     # 추출만 (임베딩 X)

필수 패키지:
  pip install pymupdf pdfplumber Pillow psycopg2-binary requests
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("[manual-embed] pymupdf 미설치. 실행: pip install pymupdf")

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # 표 추출 비활성화

import psycopg2
from psycopg2.extras import execute_values
import time
import requests

# ── 설정 ──
MANUALS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "manuals")
)
SKIPPED_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "manuals-skipped")
)
SKIP_LOG = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "manuals-skipped", "skip_log.jsonl")
)
EMBED_URL = os.environ.get("EMBED_URL", "http://182.224.6.147:11434/api/embed")
EMBED_BATCH = int(os.environ.get("EMBED_BATCH", "16"))  # 동시 에이전트 사용 시 타임아웃 방지
EMBED_DELAY = float(os.environ.get("EMBED_DELAY", "0.5"))  # 배치 간 딜레이(초)
EMBED_DIM = 2000
SOURCE_TYPE = "manual"
IMAGE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "manual_images")
)

# Supabase Storage 설정
SUPABASE_URL = "http://localhost:8000"
SUPABASE_BUCKET = "vector"
_env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))
SERVICE_ROLE_KEY = ""
# 외부 공개 URL (도메인 설정 후 SUPABASE_PUBLIC_URL 환경변수로 오버라이드)
# 예: SUPABASE_PUBLIC_URL=https://storage.cs-wta.com
SUPABASE_PUBLIC_URL = os.environ.get("SUPABASE_PUBLIC_URL", SUPABASE_URL)
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("SERVICE_ROLE_KEY="):
                SERVICE_ROLE_KEY = _line.split("=", 1)[1].strip()
            elif _line.startswith("SUPABASE_PUBLIC_URL="):
                SUPABASE_PUBLIC_URL = _line.split("=", 1)[1].strip()

# 청크 설정
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# 이미지 추출 설정
MIN_IMAGE_WIDTH = 100
MIN_IMAGE_HEIGHT = 100
IMAGE_DPI = 200

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password",
    "dbname": "postgres",
}

logging.basicConfig(
    level=logging.INFO,
    format="[manual-embed] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("manual-embed")


# ── 데이터 모델 ──

@dataclass
class ExtractedChunk:
    chunk_type: str          # "text", "table", "image_caption"
    content: str
    page_number: int
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)
    image_path: str | None = None


@dataclass
class ParsedDocument:
    file_path: str
    file_hash: str
    category: str
    total_pages: int
    chunks: list[ExtractedChunk] = field(default_factory=list)


# ── Supabase Storage ──

def ensure_bucket(bucket: str = SUPABASE_BUCKET) -> None:
    """Supabase Storage 버킷 존재 확인, 없으면 생성."""
    if not SERVICE_ROLE_KEY:
        log.warning("SERVICE_ROLE_KEY 미설정 — Supabase Storage 업로드 비활성화")
        return

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
    }
    resp = requests.get(f"{SUPABASE_URL}/storage/v1/bucket/{bucket}", headers=headers, timeout=10)
    if resp.status_code == 200:
        return
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/bucket",
        headers={**headers, "Content-Type": "application/json"},
        json={"id": bucket, "name": bucket, "public": True},
        timeout=10,
    )
    if resp.status_code in (200, 201):
        log.info(f"버킷 '{bucket}' 생성 완료")
    else:
        log.warning(f"버킷 생성 실패: {resp.status_code} {resp.text[:200]}")


def upload_to_supabase(local_path: str, storage_path: str, bucket: str = SUPABASE_BUCKET) -> str | None:
    """파일을 Supabase Storage에 업로드하고 공개 URL 반환 (SUPABASE_PUBLIC_URL 기준)."""
    if not SERVICE_ROLE_KEY:
        return None

    ext = os.path.splitext(local_path)[1].lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".pdf": "application/pdf", ".md": "text/markdown; charset=utf-8",
    }
    content_type = mime_map.get(ext, "application/octet-stream")

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    with open(local_path, "rb") as f:
        resp = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{bucket}/{storage_path}",
            headers=headers,
            data=f,
            timeout=120,
        )

    if resp.status_code in (200, 201):
        # 공개 URL은 SUPABASE_PUBLIC_URL 기준 (외부 도메인 설정 시 자동 반영)
        return f"{SUPABASE_PUBLIC_URL}/storage/v1/object/public/{bucket}/{storage_path}"
    else:
        log.warning(f"업로드 실패 ({storage_path}): {resp.status_code} {resp.text[:200]}")
        return None


def upload_pdf_to_supabase(file_path: str) -> str | None:
    """PDF 파일을 Supabase Storage pdfs/ 경로에 업로드하고 공개 URL 반환."""
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', Path(file_path).name)
    storage_path = f"pdfs/{safe_name}"
    url = upload_to_supabase(file_path, storage_path)
    if url:
        log.info(f"    PDF 업로드 완료: {storage_path}")
    return url


# ── PDF 메타데이터 추출 & 리네이밍 ──

# 제조사 키워드 매핑 (PDF 텍스트 -> 영문 제조사명)
MANUFACTURER_MAP = {
    "삼성": "Samsung", "samsung": "Samsung",
    "오리엔탈모터": "OrientalMotor", "oriental motor": "OrientalMotor", "orientalmotor": "OrientalMotor",
    "미쓰비시": "Mitsubishi", "mitsubishi": "Mitsubishi", "melservo": "Mitsubishi", "melsec": "Mitsubishi",
    "야스카와": "Yaskawa", "yaskawa": "Yaskawa", "sigma": "Yaskawa",
    "파나소닉": "Panasonic", "panasonic": "Panasonic", "minas": "Panasonic",
    "옴론": "Omron", "omron": "Omron",
    "키엔스": "Keyence", "keyence": "Keyence",
    "abb": "ABB",
    "kuka": "KUKA",
    "fanuc": "FANUC", "화낙": "FANUC",
    "siemens": "Siemens", "지멘스": "Siemens",
    "beckhoff": "Beckhoff",
    "iai": "IAI",
    "smc": "SMC",
    "festo": "Festo",
    "sick": "SICK",
    "cognex": "Cognex",
    "hmi": "HMI",
    "ls": "LS", "엘에스": "LS",
    "delta": "Delta", "델타": "Delta",
    "autonics": "Autonics", "오토닉스": "Autonics",
    "pro-face": "ProFace", "proface": "ProFace",
    "weintek": "Weintek",
    "hiwin": "HIWIN",
    "thk": "THK",
    "nsk": "NSK",
    "schneider": "Schneider",
    "rockwell": "Rockwell", "allen-bradley": "Rockwell",
    "bosch": "Bosch", "rexroth": "BoschRexroth",
    "lenze": "Lenze",
    "sew": "SEW",
    "danfoss": "Danfoss",
    "weg": "WEG",
    "eaton": "Eaton",
    "phoenix": "PhoenixContact",
    "wago": "WAGO",
    "balluff": "Balluff",
    "ifm": "IFM",
    "baumer": "Baumer",
    "csd5": "Samsung", "csd3": "Samsung", "csvg": "Samsung",
    "crevis": "Crevis",
}

# 문서 종류 키워드 매핑
DOC_TYPE_MAP = {
    "user manual": "UserManual", "사용자 매뉴얼": "UserManual", "사용 설명서": "UserManual",
    "user's manual": "UserManual", "users manual": "UserManual",
    "operation guide": "OperationGuide", "조작 설명서": "OperationGuide",
    "operation manual": "OperationManual", "운전 설명서": "OperationManual",
    "install": "InstallGuide", "설치 설명서": "InstallGuide", "설치 매뉴얼": "InstallGuide",
    "setup": "SetupGuide", "셋업": "SetupGuide", "셋팅": "SetupGuide",
    "maintenance": "MaintenanceManual", "보수": "MaintenanceManual", "정비": "MaintenanceManual",
    "parameter": "ParameterManual", "파라미터": "ParameterManual",
    "communication": "CommManual", "통신": "CommManual", "protocol": "CommManual",
    "troubleshoot": "Troubleshooting", "에러": "Troubleshooting",
    "quick start": "QuickStart",
    "catalog": "Catalog", "카탈로그": "Catalog",
    "datasheet": "Datasheet", "사양서": "Datasheet", "specification": "Datasheet",
    "wiring": "WiringGuide", "배선": "WiringGuide",
    "programming": "ProgrammingManual",
    "ascii": "CommManual",
    "firmware": "FirmwareNote", "release note": "ReleaseNote",
}


@dataclass
class PdfMetadata:
    """PDF에서 추출한 메타데이터."""
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    doc_type: str = "Manual"
    language: str = "KO"
    original_name: str = ""
    standardized_name: str = ""


def extract_pdf_metadata(file_path: str) -> PdfMetadata:
    """PDF 첫 3페이지에서 제조사, 모델명, 문서종류, 언어 파악."""
    meta = PdfMetadata(original_name=Path(file_path).name)
    filename_lower = Path(file_path).stem.lower()

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        log.warning(f"    메타데이터 추출 실패 (파일 열기): {e}")
        return meta

    # 첫 3페이지 텍스트 추출
    pages_text = ""
    for i in range(min(3, len(doc))):
        pages_text += doc[i].get_text("text").replace("\x00", "") + "\n"
    doc.close()

    combined = (filename_lower + " " + pages_text.lower()).strip()

    # 1. 제조사 판별
    for keyword, mfr in MANUFACTURER_MAP.items():
        if keyword in combined:
            meta.manufacturer = mfr
            break

    # 2. 모델명 추출 (파일명에서 우선, 없으면 텍스트에서)
    # 파일명에서 모델명 패턴 탐색 (영숫자+하이픈 조합)
    model_patterns = [
        r'([A-Z]{2,}[\-]?[A-Z0-9]{1,}[\-]?[A-Z0-9]*)',  # CSD5, IRB-360, SigmaV 등
    ]
    filename_upper = Path(file_path).stem
    for pattern in model_patterns:
        m = re.search(pattern, filename_upper)
        if m:
            candidate = m.group(1)
            # 너무 짧거나 일반적인 단어 제외
            if len(candidate) >= 3 and candidate not in ("PDF", "DOC", "KOR", "ENG", "Drive", "MAY"):
                meta.model = candidate
                break

    # 3. 문서 종류 판별
    for keyword, dtype in DOC_TYPE_MAP.items():
        if keyword in combined:
            meta.doc_type = dtype
            break

    # 4. 언어 판별
    # 한글이 많으면 KO, 영문만이면 EN
    ko_chars = len(re.findall(r'[가-힣]', pages_text))
    en_chars = len(re.findall(r'[a-zA-Z]', pages_text))
    if ko_chars > 50:
        meta.language = "KO"
    elif en_chars > 100 and ko_chars < 10:
        meta.language = "EN"
    else:
        meta.language = "KO"  # 기본값

    # 표준 파일명 생성
    meta.standardized_name = f"{meta.manufacturer}_{meta.model}_{meta.doc_type}_{meta.language}.pdf"

    return meta


def rename_pdf(file_path: str, meta: PdfMetadata) -> str:
    """PDF를 표준 파일명으로 리네이밍. 리네이밍된 경로 반환.

    원본 파일은 유지하고, 같은 디렉토리에 표준 이름으로 복사.
    이미 표준 이름이면 그대로 반환.
    """
    import shutil

    current_name = Path(file_path).name
    if current_name == meta.standardized_name:
        return file_path

    new_path = os.path.join(os.path.dirname(file_path), meta.standardized_name)

    # 동일 이름 파일이 이미 존재하면 번호 추가
    if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(file_path):
        base, ext = os.path.splitext(meta.standardized_name)
        counter = 2
        while os.path.exists(new_path):
            new_path = os.path.join(os.path.dirname(file_path), f"{base}_{counter}{ext}")
            counter += 1

    shutil.copy2(file_path, new_path)
    log.info(f"    리네이밍: {current_name} -> {Path(new_path).name}")
    return new_path


# 임베딩 가치 판단 기준
MIN_TEXT_CHARS = 500       # 최소 텍스트 문자 수
MIN_TEXT_PAGES_RATIO = 0.3  # 텍스트 있는 페이지 비율


def assess_embedding_value(file_path: str) -> tuple[bool, str]:
    """PDF 임베딩 가치 판단. (통과 여부, 사유) 반환.

    스킵 대상:
    - 텍스트가 거의 없는 도면/카탈로그 (이미지 위주)
    - 총 텍스트가 MIN_TEXT_CHARS 미만
    - 텍스트 페이지 비율이 MIN_TEXT_PAGES_RATIO 미만
    """
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        return False, f"PDF 열기 실패: {e}"

    total_pages = len(doc)
    if total_pages == 0:
        doc.close()
        return False, "빈 PDF (0페이지)"

    total_text = ""
    pages_with_text = 0

    for i in range(total_pages):
        text = doc[i].get_text("text").replace("\x00", "").strip()
        total_text += text
        if len(text) > 50:
            pages_with_text += 1

    doc.close()

    total_chars = len(total_text)
    text_ratio = pages_with_text / total_pages if total_pages > 0 else 0

    if total_chars < MIN_TEXT_CHARS:
        return False, f"텍스트 부족 ({total_chars}자 < {MIN_TEXT_CHARS}자 기준)"

    if text_ratio < MIN_TEXT_PAGES_RATIO:
        return False, f"텍스트 페이지 비율 낮음 ({text_ratio:.1%} < {MIN_TEXT_PAGES_RATIO:.0%})"

    return True, f"통과 ({total_chars}자, 텍스트 페이지 {pages_with_text}/{total_pages})"


def skip_file(file_path: str, reason: str, meta: PdfMetadata | None = None) -> None:
    """스킵 파일을 manuals-skipped/로 이동하고 사유 기록."""
    import shutil

    os.makedirs(SKIPPED_DIR, exist_ok=True)

    dest = os.path.join(SKIPPED_DIR, Path(file_path).name)
    if os.path.abspath(dest) != os.path.abspath(file_path):
        # 동일 이름 존재 시 번호 추가
        if os.path.exists(dest):
            base, ext = os.path.splitext(Path(file_path).name)
            counter = 2
            while os.path.exists(dest):
                dest = os.path.join(SKIPPED_DIR, f"{base}_{counter}{ext}")
                counter += 1
        shutil.move(file_path, dest)
        log.info(f"    -> 스킵 이동: {Path(dest).name}")

    # JSONL 로그 기록
    record = {
        "original": Path(file_path).name,
        "reason": reason,
        "manufacturer": meta.manufacturer if meta else "",
        "model": meta.model if meta else "",
        "skipped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(SKIP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── PDF 파싱 ──

def compute_file_hash(file_path: str) -> str:
    """파일 SHA-256 해시 (변경 감지용)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()[:16]


def extract_text_chunks(doc: fitz.Document) -> list[ExtractedChunk]:
    """PyMuPDF로 페이지별 텍스트 추출 + 청크 분할."""
    chunks = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").replace("\x00", "").strip()
        if not text:
            continue

        page_chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        for chunk_text_content in page_chunks:
            if len(chunk_text_content.strip()) < 20:
                continue
            chunks.append(ExtractedChunk(
                chunk_type="text",
                content=chunk_text_content.strip(),
                page_number=page_num + 1,
            ))
    return chunks


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 문단/문장 경계 기준으로 청크 분할."""
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
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i: i + size])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)
    return chunks


def extract_tables(file_path: str) -> list[ExtractedChunk]:
    """pdfplumber로 표 추출 -> Markdown 변환."""
    if pdfplumber is None:
        log.warning("pdfplumber 미설치 — 표 추출 건너뜀")
        return []

    chunks = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue

                    md = table_to_markdown(table)
                    if len(md.strip()) < 30:
                        continue

                    chunks.append(ExtractedChunk(
                        chunk_type="table",
                        content=md,
                        page_number=page_num + 1,
                        metadata={"table_index": table_idx},
                    ))
    except Exception as e:
        log.warning(f"표 추출 실패: {e}")

    return chunks


def table_to_markdown(table: list[list[str | None]]) -> str:
    """2D 테이블 -> Markdown 테이블 문자열."""
    if not table:
        return ""

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

    return "\n".join(lines)


MIN_VECTOR_DRAWINGS = 20   # 벡터 드로잉 이 이상이면 다이어그램 페이지로 판단
RENDER_DPI = 150           # 페이지 렌더링 DPI (용량/품질 균형)


def extract_images(doc: fitz.Document, file_path: str, image_folder: str = "") -> list[ExtractedChunk]:
    """PyMuPDF로 이미지 추출 + 벡터 다이어그램 페이지 렌더링.

    1. 래스터 이미지: get_images()로 추출 (기존 방식)
    2. 벡터 다이어그램: 드로잉이 많고 래스터 이미지가 없는 페이지를 전체 렌더링

    image_folder: Supabase Storage 폴더명 (예: Samsung_CSD5_UserManual_KO).
    """
    basename = Path(file_path).stem
    folder = image_folder or re.sub(r'[^a-zA-Z0-9._-]', '_', basename)
    sub_dir = os.path.join(IMAGE_DIR, folder)
    os.makedirs(sub_dir, exist_ok=True)

    chunks = []
    rendered_pages = set()  # 렌더링된 페이지 (래스터 추출 스킵용)

    # --- 1단계: 벡터 다이어그램 페이지 감지 + 렌더링 ---
    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            raster_images = page.get_images(full=True)
            drawings = page.get_drawings()
        except Exception:
            continue

        # 조건: 드로잉 많고 래스터 이미지 없거나 적음 -> 벡터 다이어그램
        has_many_drawings = len(drawings) >= MIN_VECTOR_DRAWINGS
        has_few_rasters = len(raster_images) <= 1
        text_len = len(page.get_text("text").strip())
        is_diagram = has_many_drawings and has_few_rasters and text_len < 3000

        if not is_diagram:
            continue

        try:
            pix = page.get_pixmap(dpi=RENDER_DPI)
            img_filename = f"page_{page_num + 1}_full.png"
            img_path = os.path.join(sub_dir, img_filename)
            pix.save(img_path)

            storage_path = f"images/{folder}/{img_filename}"
            image_url = upload_to_supabase(img_path, storage_path)

            caption = f"[다이어그램: {basename} p.{page_num + 1}, {pix.width}x{pix.height}px, 벡터 렌더링]"

            chunks.append(ExtractedChunk(
                chunk_type="image_caption",
                content=caption,
                page_number=page_num + 1,
                image_path=img_path,
                metadata={
                    "image_file": img_filename,
                    "image_url": image_url or "",
                    "width": pix.width,
                    "height": pix.height,
                    "render_type": "vector_page",
                    "drawings_count": len(drawings),
                },
            ))
            rendered_pages.add(page_num)
        except Exception as e:
            log.warning(f"    페이지 렌더링 실패 (p{page_num+1}): {e}")

    if rendered_pages:
        log.info(f"    벡터 다이어그램 렌더링: {len(rendered_pages)}페이지")

    # --- 2단계: 래스터 이미지 추출 (렌더링 안 된 페이지만) ---
    for page_num in range(len(doc)):
        if page_num in rendered_pages:
            continue

        page = doc[page_num]
        try:
            images = page.get_images(full=True)
        except Exception:
            continue

        for img_idx, img_info in enumerate(images):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image or "image" not in base_image:
                    continue
            except Exception:
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                continue

            ext = base_image.get("ext", "png")
            image_bytes = base_image["image"]

            try:
                img_filename = f"page_{page_num + 1}_img{img_idx}.{ext}"
                img_path = os.path.join(sub_dir, img_filename)
                with open(img_path, "wb") as f:
                    f.write(image_bytes)

                storage_path = f"images/{folder}/{img_filename}"
                image_url = upload_to_supabase(img_path, storage_path)
            except Exception as e:
                log.warning(f"    이미지 저장 실패 (p{page_num+1} #{img_idx}): {e}")
                continue

            caption = f"[이미지: {basename} p.{page_num + 1} #{img_idx + 1}, {width}x{height}px]"

            chunks.append(ExtractedChunk(
                chunk_type="image_caption",
                content=caption,
                page_number=page_num + 1,
                image_path=img_path,
                metadata={
                    "image_file": img_filename,
                    "image_url": image_url or "",
                    "width": width,
                    "height": height,
                    "render_type": "raster_extract",
                },
            ))

    return chunks


def render_page_image(doc: fitz.Document, page_num: int, file_path: str) -> str:
    """페이지 전체를 이미지로 렌더링 (비전 분석용)."""
    basename = Path(file_path).stem
    sub_dir = os.path.join(IMAGE_DIR, basename)
    os.makedirs(sub_dir, exist_ok=True)

    page = doc[page_num]
    pix = page.get_pixmap(dpi=IMAGE_DPI)
    img_filename = f"page{page_num + 1}.png"
    img_path = os.path.join(sub_dir, img_filename)
    pix.save(img_path)
    return img_path


# ── 이미지 캡션 생성 ──

def generate_image_captions(chunks: list[ExtractedChunk], method: str = "placeholder") -> list[ExtractedChunk]:
    """이미지 청크에 설명 텍스트 생성. 현재는 플레이스홀더."""
    if method == "placeholder":
        return chunks
    # 향후: Claude Code 세션에서 직접 이미지 분석하여 캡션 생성
    return chunks


# ── 문서 파싱 통합 ──

def parse_pdf(file_path: str, image_folder: str = "") -> ParsedDocument:
    """PDF 파일을 파싱하여 모든 청크 추출."""
    file_hash = compute_file_hash(file_path)

    rel_path = os.path.relpath(file_path, MANUALS_DIR)
    parts = Path(rel_path).parts
    category = parts[0] if len(parts) > 1 else "uncategorized"

    doc = fitz.open(file_path)
    total_pages = len(doc)
    log.info(f"  파싱: {Path(file_path).name} ({total_pages}페이지)")

    # 1. 텍스트 추출
    text_chunks = extract_text_chunks(doc)
    log.info(f"    텍스트: {len(text_chunks)}개 청크")

    # 2. 표 추출
    table_chunks = extract_tables(file_path)
    log.info(f"    표: {len(table_chunks)}개")

    # 3. 이미지 추출 (PDF별 폴더 분리)
    try:
        image_chunks = extract_images(doc, file_path, image_folder=image_folder)
    except Exception as e:
        log.warning(f"    이미지 추출 실패 (계속 진행): {e}")
        image_chunks = []
    log.info(f"    이미지: {len(image_chunks)}개")

    # 4. 이미지 캡션 생성
    image_chunks = generate_image_captions(image_chunks)

    doc.close()

    # 청크 번호 부여
    all_chunks = text_chunks + table_chunks + image_chunks
    for i, chunk in enumerate(all_chunks):
        chunk.chunk_index = i

    return ParsedDocument(
        file_path=file_path,
        file_hash=file_hash,
        category=category,
        total_pages=total_pages,
        chunks=all_chunks,
    )


# ── 파싱 결과 Markdown 생성 & 업로드 ──

PARSED_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "manual_parsed")
)


def generate_parsed_markdown(parsed: "ParsedDocument", meta: "PdfMetadata") -> str:
    """파싱된 청크를 페이지별 Markdown으로 변환."""
    lines = []
    lines.append(f"# {meta.manufacturer} {meta.model} — {meta.doc_type}")
    lines.append(f"")
    lines.append(f"- **원본**: {meta.original_name}")
    lines.append(f"- **표준명**: {meta.standardized_name}")
    lines.append(f"- **언어**: {meta.language}")
    lines.append(f"- **총 페이지**: {parsed.total_pages}")
    lines.append(f"- **총 청크**: {len(parsed.chunks)}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 페이지별 그룹핑
    page_chunks: dict[int, list] = {}
    for chunk in parsed.chunks:
        pg = chunk.page_number
        if pg not in page_chunks:
            page_chunks[pg] = []
        page_chunks[pg].append(chunk)

    for pg in sorted(page_chunks.keys()):
        lines.append(f"## Page {pg}")
        lines.append(f"")
        for chunk in page_chunks[pg]:
            if chunk.chunk_type == "text":
                lines.append(chunk.content)
                lines.append(f"")
            elif chunk.chunk_type == "table":
                lines.append(f"### 표")
                lines.append(f"")
                lines.append(chunk.content)
                lines.append(f"")
            elif chunk.chunk_type == "image_caption":
                img_url = chunk.metadata.get("image_url", "")
                if img_url:
                    lines.append(f"![{chunk.content}]({img_url})")
                else:
                    lines.append(chunk.content)
                lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    return "\n".join(lines)


def save_and_upload_parsed_md(parsed: "ParsedDocument", meta: "PdfMetadata",
                               folder_name: str) -> str | None:
    """파싱 Markdown을 로컬 저장 + Supabase Storage 업로드. URL 반환."""
    os.makedirs(PARSED_DIR, exist_ok=True)

    md_content = generate_parsed_markdown(parsed, meta)
    md_filename = f"{folder_name}.md"
    md_path = os.path.join(PARSED_DIR, md_filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    log.info(f"    파싱 MD 저장: {md_filename} ({len(md_content)}자)")

    # Supabase Storage 업로드: parsed/{폴더명}.md
    storage_path = f"parsed/{md_filename}"
    url = upload_to_supabase(md_path, storage_path)
    if url:
        log.info(f"    파싱 MD 업로드 완료: {storage_path}")
    return url


# ── 임베딩 & 저장 ──

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Qwen3-Embedding-8B 서버에 배치 임베딩 요청. Ollama(/api/embed) 및 로컬 서버 모두 지원."""
    if "api/embed" in EMBED_URL:  # Ollama 형식
        resp = requests.post(EMBED_URL, json={"model": "qwen3-embedding:8b", "input": texts}, timeout=300)
    else:
        resp = requests.post(EMBED_URL, json={"texts": texts, "normalize": True}, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"임베딩 응답 오류: {data}")
    # Matryoshka: 4096차원 → 2000차원으로 잘라서 반환
    return [v[:EMBED_DIM] for v in data["embeddings"]]


def ensure_schema(conn):
    """manual 스키마 및 테이블 생성."""
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
                metadata JSONB DEFAULT '{}',
                embedding vector(2000),
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE (source_file, chunk_index)
            )
        """)
        cur.execute("""
            DO $$ BEGIN
                ALTER TABLE manual.documents ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT '';
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
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
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_docs_category
                ON manual.documents (category)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_docs_type
                ON manual.documents (chunk_type)
        """)
    conn.commit()
    log.info("스키마/테이블 확인 완료")


def is_already_indexed(conn, source_file: str, file_hash: str) -> bool:
    """동일 파일+해시가 이미 인덱싱되었는지 확인."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM manual.documents WHERE source_file = %s AND file_hash = %s LIMIT 1",
            (source_file, file_hash),
        )
        return cur.fetchone() is not None


def upsert_chunks(conn, source_file: str, file_hash: str, category: str,
                   chunks: list[ExtractedChunk], embeddings: list[list[float]],
                   pdf_url: str = ""):
    """청크 + 임베딩을 DB에 upsert."""
    rows = []
    for chunk, emb in zip(chunks, embeddings):
        image_url = chunk.metadata.get("image_url", "") if chunk.chunk_type == "image_caption" else ""
        rows.append({
            "source_file": source_file,
            "file_hash": file_hash,
            "category": category,
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "image_url": image_url,
            "pdf_url": pdf_url,
            "metadata": json.dumps(
                {**chunk.metadata, "page": chunk.page_number, "type": chunk.chunk_type},
                ensure_ascii=False,
            ),
            "embedding": str(emb),
        })

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
        "%(page_number)s, %(content)s, %(image_url)s, %(pdf_url)s, %(metadata)s::jsonb, %(embedding)s::vector, now())"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, template=template, page_size=50)

    max_idx = max(c.chunk_index for c in chunks) if chunks else -1
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM manual.documents WHERE source_file = %s AND chunk_index > %s",
            (source_file, max_idx),
        )
    conn.commit()


def process_document(conn, file_path: str, dry_run: bool = False, force: bool = False,
                     no_skip: bool = False, no_embed: bool = False) -> int:
    """단일 PDF 처리. 새 파이프라인 순서:
    1. 메타데이터 추출 (제조사, 모델, 문서종류, 언어)
    2. 임베딩 가치 판단 (텍스트 충분한지)
    3. 가치 있음 -> 리네이밍 + Supabase 업로드 + 임베딩
    4. 가치 없음 -> 스킵 분류 + 사유 기록

    처리된 청크 수 반환. 스킵된 경우 -1 반환.
    """
    # 1단계: 메타데이터 추출
    meta = extract_pdf_metadata(file_path)
    log.info(f"  메타: {meta.manufacturer}/{meta.model}/{meta.doc_type}/{meta.language}")
    log.info(f"    표준명: {meta.standardized_name}")

    # 2단계: 임베딩 가치 판단
    if not no_skip:
        worthy, reason = assess_embedding_value(file_path)
        if not worthy:
            log.info(f"    -> 스킵: {reason}")
            if not dry_run:
                skip_file(file_path, reason, meta)
            return -1

    # 3단계: 리네이밍
    work_path = rename_pdf(file_path, meta)

    # Supabase 이미지 폴더명 = 표준화된 이름에서 .pdf 제거
    image_folder = re.sub(r'[^a-zA-Z0-9._-]', '_', meta.standardized_name.replace(".pdf", ""))

    # 4단계: 파싱
    parsed = parse_pdf(work_path, image_folder=image_folder)
    if not parsed.chunks:
        log.info("    -> 추출된 내용 없음, 건너뜀")
        return 0

    # source_file을 표준화된 이름으로 저장
    source_file = meta.standardized_name

    if dry_run:
        log.info(f"    -> [DRY-RUN] {len(parsed.chunks)}개 청크 "
                 f"(텍스트:{sum(1 for c in parsed.chunks if c.chunk_type == 'text')}, "
                 f"표:{sum(1 for c in parsed.chunks if c.chunk_type == 'table')}, "
                 f"이미지:{sum(1 for c in parsed.chunks if c.chunk_type == 'image_caption')})")
        return len(parsed.chunks)

    # 변경 감지 (해시 비교)
    if not force and is_already_indexed(conn, source_file, parsed.file_hash):
        log.info("    -> 변경 없음, 건너뜀")
        return 0

    # 임베딩 가능한 청크만 (이미지 플레이스홀더 제외)
    embeddable = [c for c in parsed.chunks if c.content and len(c.content.strip()) >= 20]
    if not embeddable:
        return 0

    # 청크 metadata에 PDF 메타정보 추가
    for chunk in embeddable:
        chunk.metadata["manufacturer"] = meta.manufacturer
        chunk.metadata["model"] = meta.model
        chunk.metadata["doc_type"] = meta.doc_type
        chunk.metadata["language"] = meta.language
        chunk.metadata["original_name"] = meta.original_name

    if no_embed:
        # 5단계: Supabase 업로드 (임베딩 없이)
        pdf_url = upload_pdf_to_supabase(work_path) or ""
        save_and_upload_parsed_md(parsed, meta, image_folder)
        log.info(f"    -> [NO-EMBED] {len(embeddable)}개 청크 파싱 완료 (임베딩 스킵)")
        return len(embeddable)

    # 배치 임베딩 (재시도 + 딜레이)
    all_embeddings = []
    for i in range(0, len(embeddable), EMBED_BATCH):
        batch = embeddable[i:i + EMBED_BATCH]
        texts = [c.content for c in batch]

        for attempt in range(3):
            try:
                batch_embeddings = embed_texts(texts)
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    log.warning(f"    임베딩 재시도 {attempt+1}/3 (배치 {i}, {wait}초 대기): {e}")
                    time.sleep(wait)
                else:
                    log.error(f"    임베딩 최종 실패 (배치 {i}): {e}")
                    return 0

        if i + EMBED_BATCH < len(embeddable):
            time.sleep(EMBED_DELAY)

    # 5단계: Supabase 업로드 (리네이밍된 PDF)
    pdf_url = upload_pdf_to_supabase(work_path) or ""

    # 6단계: 파싱 결과 Markdown 저장 + 업로드
    save_and_upload_parsed_md(parsed, meta, image_folder)

    # 7단계: DB 저장
    upsert_chunks(conn, source_file, parsed.file_hash, parsed.category,
                   embeddable, all_embeddings, pdf_url=pdf_url)

    log.info(f"    -> {len(embeddable)}개 청크 저장 완료 (source: {source_file})")
    return len(embeddable)


# ── 메인 ──

def collect_pdf_files(target_dir: str) -> list[str]:
    """디렉토리에서 PDF 파일 목록 수집."""
    files = []
    for root, _dirs, filenames in os.walk(target_dir):
        for name in sorted(filenames):
            if name.lower().endswith(".pdf"):
                files.append(os.path.join(root, name))
    return files


def main():
    parser = argparse.ArgumentParser(description="PDF 매뉴얼 임베딩 파이프라인")
    parser.add_argument("--dir", default=MANUALS_DIR, help="매뉴얼 디렉토리 (기본: data/manuals/)")
    parser.add_argument("--file", help="단일 PDF 파일 처리")
    parser.add_argument("--dry-run", action="store_true", help="추출만 수행 (임베딩/저장 안함)")
    parser.add_argument("--force", action="store_true", help="변경 없어도 강제 재처리")
    parser.add_argument("--category", help="특정 카테고리만 처리 (예: 1_robot)")
    parser.add_argument("--no-skip", action="store_true", help="스킵 판단 비활성화 (모든 PDF 임베딩)")
    parser.add_argument("--no-embed", action="store_true", help="파싱+업로드만, 임베딩 건너뛰기")
    args = parser.parse_args()

    if args.file:
        if not os.path.isfile(args.file):
            log.error(f"파일 없음: {args.file}")
            sys.exit(1)
        pdf_files = [args.file]
    else:
        target = args.dir
        if args.category:
            target = os.path.join(args.dir, args.category)
        pdf_files = collect_pdf_files(target)

    log.info(f"대상: {len(pdf_files)}개 PDF 파일")
    if not pdf_files:
        log.info("처리할 파일 없음")
        return

    conn = None
    if not args.dry_run:
        conn = psycopg2.connect(**DB_CONFIG)
        ensure_schema(conn)
        ensure_bucket()

    total_chunks = 0
    processed = 0
    skipped = 0
    errors = 0

    for file_path in pdf_files:
        try:
            n = process_document(conn, file_path, dry_run=args.dry_run,
                                 force=args.force, no_skip=args.no_skip,
                                 no_embed=args.no_embed)
            if n == -1:
                skipped += 1
            elif n > 0:
                total_chunks += n
                processed += 1
        except Exception as e:
            log.error(f"처리 실패: {Path(file_path).name} — {e}")
            errors += 1

    log.info(f"\n완료: {processed}개 처리 / {skipped}개 스킵 / {total_chunks}개 청크 / {errors}개 오류")

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
