"""core-tech-embed.py — 핵심기술개발 자료 파싱 + 임베딩 스크립트.

대상: \\192.168.0.210\data\report (연도별 docx 파일)
단계:
  1) 파싱: docx에서 텍스트/표/이미지 분리 추출
  2) 임베딩: Qwen3-Embedding-8B로 벡터화
  3) 적재: manual.core_tech_documents 테이블에 upsert

실행:
  python core-tech-embed.py --parse-only     # 파싱만 (검증용)
  python core-tech-embed.py                  # 파싱 + 임베딩 + 적재
  python core-tech-embed.py --full           # 전체 재처리 (기존 데이터 포함)
  python core-tech-embed.py --file "경로"    # 단일 파일만 처리
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

import docx
import psycopg2
from psycopg2.extras import execute_values
import requests

# ── 설정 ──
REPORT_ROOT = r"\\192.168.0.210\data\report"
IMAGE_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "core-tech-images",
)

EMBED_URL = "http://182.224.6.147:11434/api/embed"
EMBED_MODEL = "qwen3-embedding:8b"
EMBED_DIM = 2000
EMBED_BATCH = 32  # docx 텍스트가 길어서 배치 작게

VL_URL = "http://182.224.6.147:11434/api/generate"
VL_MODEL = "qwen3-vl:32b"

CHUNK_MAX_CHARS = 1500  # 청크 최대 길이
CHUNK_OVERLAP = 200     # 청크 오버랩

MES_DB = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "dbname": "postgres",
}

logging.basicConfig(
    level=logging.INFO,
    format="[core-tech] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("core-tech")


# ── DB 비밀번호 로드 (.env) ──
def _load_db_password() -> str:
    env_path = "C:/MES/backend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DB_PASSWORD="):
                    return line.strip().split("=", 1)[1]
    raise RuntimeError("DB_PASSWORD not found in .env")


def get_db_conn():
    cfg = {**MES_DB, "password": _load_db_password()}
    return psycopg2.connect(**cfg)


# ── 파일 탐색 ──
def find_docx_files(root: str) -> list[str]:
    """docx 파일 목록 (임시파일 ~$ 제외, 양식 #0 제외)."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".docx"):
                continue
            if fname.startswith("~$"):
                continue
            if fname.startswith("#0."):
                continue
            files.append(os.path.join(dirpath, fname))
    files.sort()
    return files


def file_hash(path: str) -> str:
    """파일 SHA256 해시."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


# ── 메타데이터 추출 ──
def extract_metadata(filepath: str) -> dict:
    """파일 경로에서 doc_type, year, project_name 추출."""
    fname = os.path.basename(filepath)
    rel = filepath.replace("\\", "/")

    # doc_type: 계획서 / 결과보고서
    doc_type = "unknown"
    if "계획서" in fname or "계획" in fname:
        doc_type = "plan"  # 연구개발계획서
    elif "보고서" in fname or "결과" in fname or "개발보고서" in fname:
        doc_type = "report"  # 연구개발결과보고서

    # year: 경로에서 연도 추출
    year = None
    year_match = re.search(r"(20\d{2})", rel)
    if year_match:
        year = int(year_match.group(1))

    # project_name: 괄호 안의 프로젝트명
    proj_match = re.search(r"[（(](.+?)[）)]", fname)
    project_name = proj_match.group(1) if proj_match else fname.replace(".docx", "")

    return {
        "doc_type": doc_type,
        "year": year,
        "project_name": project_name,
    }


# ── DOCX 파싱 ──
def _extract_section_context(doc) -> list[dict]:
    """문서를 순회하며 각 요소의 위치/섹션/컨텍스트 정보 기록.

    Returns: [{"type": "para"|"image"|"table", "text": str, "section": str, ...}]
    """
    from docx.oxml.ns import qn

    elements = []
    current_section = ""
    prev_texts = []  # 최근 문단 텍스트 (컨텍스트용)

    for elem in doc.element.body:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag == "p":
            # 문단 텍스트
            text = "".join(node.text or "" for node in elem.iter(qn("w:t"))).strip()
            # 스타일로 섹션 제목 감지
            style_elem = elem.find(qn("w:pPr"))
            if style_elem is not None:
                style_name = style_elem.find(qn("w:pStyle"))
                if style_name is not None:
                    style_val = style_name.get(qn("w:val"), "")
                    if "Heading" in style_val or "heading" in style_val:
                        current_section = text

            # 제목 스타일 없어도 짧고 굵은 텍스트는 섹션으로 추정
            if text and len(text) < 50:
                bold_runs = elem.findall(f".//{qn('w:b')}")
                if bold_runs:
                    current_section = text

            if text:
                elements.append({
                    "type": "para",
                    "text": text,
                    "section": current_section,
                })
                prev_texts.append(text)
                if len(prev_texts) > 3:
                    prev_texts.pop(0)

            # 이미지 체크 (인라인/앵커)
            drawings = elem.findall(f".//{qn('w:drawing')}")
            for drawing in drawings:
                # blip에서 이미지 relationship ID 추출
                blips = drawing.findall(f".//{qn('a:blip')}")
                for blip in blips:
                    r_embed = blip.get(qn("r:embed"))
                    if r_embed:
                        elements.append({
                            "type": "image",
                            "rel_id": r_embed,
                            "section": current_section,
                            "surrounding_text": "\n".join(prev_texts[-3:]),
                        })

        elif tag == "tbl":
            elements.append({
                "type": "table",
                "element": elem,
                "section": current_section,
            })

    return elements


def parse_docx(filepath: str, meta: dict | None = None) -> dict:
    """docx 파일에서 텍스트, 표, 이미지 추출 (컨텍스트 정보 포함).

    Returns:
        {
            "text_chunks": [{"content": str, "chunk_index": int}],
            "tables": [{"content": str (markdown), "chunk_index": int, "section": str}],
            "images": [{"path": str, "chunk_index": int, "rel_id": str,
                         "section": str, "surrounding_text": str}],
        }
    """
    doc = docx.Document(filepath)
    file_stem = Path(filepath).stem
    safe_stem = re.sub(r'[<>:"/\\|?*]', '_', file_stem)[:80]

    result = {"text_chunks": [], "tables": [], "images": []}
    chunk_index = 0

    # 문서 구조 분석 (섹션/컨텍스트 추적)
    doc_elements = _extract_section_context(doc)

    # 1) 텍스트 추출 + 청킹
    paragraphs = [e["text"] for e in doc_elements if e["type"] == "para"]
    full_text = "\n".join(paragraphs)
    chunks = _chunk_text(full_text)
    for chunk in chunks:
        result["text_chunks"].append({
            "content": chunk,
            "chunk_index": chunk_index,
        })
        chunk_index += 1

    # 2) 표 추출 → 마크다운
    for tidx, table in enumerate(doc.tables):
        md = _table_to_markdown(table)
        if md.strip():
            # 해당 표의 섹션 정보 찾기
            tbl_section = ""
            for e in doc_elements:
                if e["type"] == "table":
                    tbl_section = e.get("section", "")
                    break
            result["tables"].append({
                "content": md,
                "chunk_index": chunk_index,
                "section": tbl_section,
            })
            chunk_index += 1

    # 3) 이미지 추출 (컨텍스트 정보 포함)
    # 저장 경로: data/core-tech-images/{year}/{project_name}/
    m = meta or {}
    year_str = str(m.get("year", "unknown"))
    proj_name = re.sub(r'[<>:"/\\|?*]', '_', m.get("project_name", safe_stem))[:80]
    img_dir = os.path.join(IMAGE_BASE_DIR, year_str, proj_name)
    os.makedirs(img_dir, exist_ok=True)

    # rel_id → 컨텍스트 매핑
    img_contexts = {}
    for e in doc_elements:
        if e["type"] == "image":
            img_contexts[e["rel_id"]] = {
                "section": e.get("section", ""),
                "surrounding_text": e.get("surrounding_text", ""),
            }

    img_count = 0
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            img_data = rel.target_part.blob
            ext = os.path.splitext(rel.target_ref)[1] or ".png"
            img_filename = f"img_{img_count:03d}{ext}"
            img_path = os.path.join(img_dir, img_filename)

            with open(img_path, "wb") as f:
                f.write(img_data)

            ctx = img_contexts.get(rel.rId, {})
            result["images"].append({
                "path": img_path,
                "chunk_index": chunk_index,
                "rel_id": rel.rId,
                "section": ctx.get("section", ""),
                "surrounding_text": ctx.get("surrounding_text", ""),
            })
            chunk_index += 1
            img_count += 1

    return result


def _chunk_text(text: str) -> list[str]:
    """텍스트를 CHUNK_MAX_CHARS 크기로 분할 (문단 경계 우선)."""
    if len(text) <= CHUNK_MAX_CHARS:
        return [text] if text.strip() else []

    chunks = []
    paragraphs = text.split("\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 > CHUNK_MAX_CHARS:
            if current.strip():
                chunks.append(current.strip())
            # 오버랩: 이전 청크 끝부분 유지
            if len(current) > CHUNK_OVERLAP:
                current = current[-CHUNK_OVERLAP:] + "\n" + para
            else:
                current = para
        else:
            current = current + "\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _table_to_markdown(table) -> str:
    """docx 테이블 → 마크다운 테이블."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("|", "\\|").replace("\n", " ") for cell in row.cells]
        rows.append(cells)

    if not rows:
        return ""

    # 빈 테이블 필터
    all_empty = all(all(c == "" for c in row) for row in rows)
    if all_empty:
        return ""

    md_lines = []
    # 헤더
    md_lines.append("| " + " | ".join(rows[0]) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
    # 데이터
    for row in rows[1:]:
        # 열 수 맞추기
        while len(row) < len(rows[0]):
            row.append("")
        md_lines.append("| " + " | ".join(row[:len(rows[0])]) + " |")

    return "\n".join(md_lines)


# ── 임베딩 ──
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Qwen3-Embedding-8B 배치 임베딩."""
    payload = {"model": EMBED_MODEL, "input": texts}
    resp = requests.post(EMBED_URL, json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" not in data:
        raise ValueError(f"임베딩 응답 오류: {data}")
    return [v[:EMBED_DIM] for v in data["embeddings"]]


def describe_image(image_path: str, context: dict | None = None) -> str:
    """Qwen3-VL로 이미지 설명 생성 (문서 컨텍스트 포함).

    Args:
        context: {"project_name", "doc_type", "section", "surrounding_text"}
    """
    import base64
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # 컨텍스트 기반 프롬프트 구성
    ctx = context or {}
    project = ctx.get("project_name", "")
    doc_type = {"plan": "연구개발계획서", "report": "연구개발결과보고서"}.get(
        ctx.get("doc_type", ""), "연구개발 보고서"
    )
    section = ctx.get("section", "")
    surrounding = ctx.get("surrounding_text", "")

    prompt_parts = [f"이 이미지는 '{project}' {doc_type}"]
    if section:
        prompt_parts.append(f"의 '{section}' 섹션")
    prompt_parts.append("에 포함된 도면 또는 사진입니다.")
    if surrounding:
        prompt_parts.append(f"\n\n주변 텍스트 컨텍스트:\n{surrounding[:500]}")
    prompt_parts.append(
        "\n\n이미지의 내용을 한국어로 상세히 설명해주세요. "
        "장비명, 부품명, 구조, 동작 원리, 치수, 규격 등 기술적 내용을 중심으로 설명하세요."
    )

    payload = {
        "model": VL_MODEL,
        "prompt": "".join(prompt_parts),
        "images": [img_b64],
        "stream": False,
    }
    resp = requests.post(VL_URL, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json().get("response", "")


# ── DB 적재 ──
def upsert_chunks(conn, chunks: list[dict]) -> int:
    """manual.core_tech_documents에 upsert."""
    sql = """
        INSERT INTO manual.core_tech_documents
            (title, source_file, file_hash, category, project_code,
             chunk_index, chunk_type, content, embedding, metadata,
             security_level, created_by)
        VALUES %s
        ON CONFLICT (source_file, chunk_index)
        DO UPDATE SET
            title = EXCLUDED.title,
            file_hash = EXCLUDED.file_hash,
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding,
            metadata = EXCLUDED.metadata,
            updated_at = now()
    """
    template = (
        "(%(title)s, %(source_file)s, %(file_hash)s, %(category)s, %(project_code)s, "
        "%(chunk_index)s, %(chunk_type)s, %(content)s, %(embedding)s::vector, "
        "%(metadata)s::jsonb, %(security_level)s, %(created_by)s)"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, chunks, template=template, page_size=50)
    conn.commit()
    return len(chunks)


# ── 메인 처리 ──
def process_file(filepath: str, conn=None, parse_only: bool = False, skip_images: bool = False, images_only: bool = False) -> dict:
    """단일 docx 파일 처리."""
    fname = os.path.basename(filepath)
    fhash = file_hash(filepath)
    meta = extract_metadata(filepath)

    log.info(f"파싱: {fname}")
    parsed = parse_docx(filepath, meta=meta)

    stats = {
        "file": fname,
        "text_chunks": len(parsed["text_chunks"]),
        "tables": len(parsed["tables"]),
        "images": len(parsed["images"]),
    }
    log.info(f"  텍스트 {stats['text_chunks']}청크, 표 {stats['tables']}개, 이미지 {stats['images']}개")

    # images_only 모드에서 이미지 없으면 스킵
    if images_only and not parsed["images"]:
        return stats

    if parse_only:
        # 파싱 결과 샘플 출력
        if parsed["text_chunks"]:
            sample = parsed["text_chunks"][0]["content"][:200]
            log.info(f"  [텍스트 샘플] {sample}...")
        if parsed["tables"]:
            sample = parsed["tables"][0]["content"][:200]
            log.info(f"  [표 샘플] {sample}...")
        return stats

    if conn is None:
        return stats

    # 변경 감지: 해시 동일하면 스킵 (images_only 모드에서는 이미지 적재 여부로 판단)
    if images_only:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM manual.core_tech_documents WHERE source_file = %s AND chunk_type = 'image_description'",
                (fname,),
            )
            if cur.fetchone()[0] > 0:
                log.info(f"  이미지 이미 적재됨 — 스킵")
                stats["skipped"] = True
                return stats
    else:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT file_hash FROM manual.core_tech_documents WHERE source_file = %s LIMIT 1",
                (fname,),
            )
            row = cur.fetchone()
            if row and row[0] == fhash:
                log.info(f"  변경 없음 (해시 동일) — 스킵")
                stats["skipped"] = True
                return stats

    # 임베딩 대상 수집
    db_rows = []
    all_contents = []
    all_meta = []

    # 텍스트 청크 (images_only 모드에서는 스킵)
    if not images_only:
        for chunk in parsed["text_chunks"]:
            all_contents.append(chunk["content"])
            all_meta.append({
                "chunk_index": chunk["chunk_index"],
                "chunk_type": "text",
            })

        # 표 (마크다운)
        for tbl in parsed["tables"]:
            all_contents.append(tbl["content"])
            all_meta.append({
                "chunk_index": tbl["chunk_index"],
                "chunk_type": "table",
            })

    # 이미지 → VL 설명 생성 (���텍스트 포함)
    for img in ([] if skip_images else parsed["images"]):
        try:
            vl_context = {
                "project_name": meta["project_name"],
                "doc_type": meta["doc_type"],
                "section": img.get("section", ""),
                "surrounding_text": img.get("surrounding_text", ""),
            }
            desc = describe_image(img["path"], context=vl_context)
            if desc.strip():
                all_contents.append(desc)
                all_meta.append({
                    "chunk_index": img["chunk_index"],
                    "chunk_type": "image_description",
                    "image_path": img["path"],
                    "section": img.get("section", ""),
                    "surrounding_text": img.get("surrounding_text", "")[:300],
                })
                log.info(f"  [VL] 이미지 설명 생성: {os.path.basename(img['path'])} ({len(desc)}자)")
        except Exception as e:
            log.warning(f"  [VL] 이미지 설명 실패: {os.path.basename(img['path'])} — {e}")

    if not all_contents:
        log.warning(f"  콘텐츠 없음 — 스킵")
        return stats

    # 배치 임베딩
    all_embeddings = []
    for i in range(0, len(all_contents), EMBED_BATCH):
        batch = all_contents[i:i + EMBED_BATCH]
        try:
            embs = embed_texts(batch)
            all_embeddings.extend(embs)
        except Exception as e:
            log.error(f"  임베딩 실패 (배치 {i}~{i+len(batch)}): {e}")
            # 실패한 배치는 빈 벡터로 채움
            all_embeddings.extend([None] * len(batch))

    # DB 행 구성
    doc_type_label = {"plan": "연구개발계획서", "report": "연구개발결과보고서"}.get(
        meta["doc_type"], meta["doc_type"]
    )
    for content, m, emb in zip(all_contents, all_meta, all_embeddings):
        if emb is None:
            continue
        db_rows.append({
            "title": meta["project_name"],
            "source_file": fname,
            "file_hash": fhash,
            "category": doc_type_label,
            "project_code": None,
            "chunk_index": m["chunk_index"],
            "chunk_type": m["chunk_type"],
            "content": content,
            "embedding": str(emb),
            "metadata": json.dumps({
                "doc_type": meta["doc_type"],
                "year": meta["year"],
                "project_name": meta["project_name"],
                **({"image_path": m["image_path"]} if "image_path" in m else {}),
                **({"section_title": m["section"]} if m.get("section") else {}),
                **({"surrounding_text": m["surrounding_text"]} if m.get("surrounding_text") else {}),
            }, ensure_ascii=False),
            "security_level": "confidential",
            "created_by": "core-tech-embed",
        })

    if db_rows:
        count = upsert_chunks(conn, db_rows)
        log.info(f"  DB 적재: {count}건")
        stats["embedded"] = count

    return stats


def main():
    parser = argparse.ArgumentParser(description="핵심기술개발 자료 파싱 + 임베딩")
    parser.add_argument("--parse-only", action="store_true", help="파싱만 수행 (DB/임베딩 없음)")
    parser.add_argument("--full", action="store_true", help="전체 재처리 (해시 동일 파일도 포함)")
    parser.add_argument("--file", type=str, help="단일 파일만 처리")
    parser.add_argument("--skip-images", action="store_true", help="이미지 VL 분석 스킵 (텍스트+표만)")
    parser.add_argument("--images-only", action="store_true", help="이미지 VL 분석만 (텍스트+표 스킵)")
    args = parser.parse_args()

    log.info(f"시작 (모드: {'파싱만' if args.parse_only else '전체'}"
             f"{', 재처리' if args.full else ''})")

    # 파일 목록
    if args.file:
        files = [args.file]
    else:
        files = find_docx_files(REPORT_ROOT)

    log.info(f"대상 파일: {len(files)}개")
    if not files:
        log.info("처리할 파일 없음 — 종료")
        return

    conn = None
    if not args.parse_only:
        conn = get_db_conn()

    total_stats = {"files": 0, "text_chunks": 0, "tables": 0, "images": 0, "embedded": 0, "skipped": 0, "errors": 0}

    for filepath in files:
        try:
            stats = process_file(filepath, conn=conn, parse_only=args.parse_only,
                                    skip_images=args.skip_images, images_only=args.images_only)
            total_stats["files"] += 1
            total_stats["text_chunks"] += stats.get("text_chunks", 0)
            total_stats["tables"] += stats.get("tables", 0)
            total_stats["images"] += stats.get("images", 0)
            total_stats["embedded"] += stats.get("embedded", 0)
            if stats.get("skipped"):
                total_stats["skipped"] += 1
        except Exception as e:
            log.error(f"파일 처리 실패: {os.path.basename(filepath)} — {e}")
            total_stats["errors"] += 1

    log.info("=" * 50)
    log.info(f"완료: {total_stats['files']}파일 처리")
    log.info(f"  텍스트 청크: {total_stats['text_chunks']}")
    log.info(f"  표: {total_stats['tables']}")
    log.info(f"  이미지: {total_stats['images']}")
    if not args.parse_only:
        log.info(f"  DB 적재: {total_stats['embedded']}건")
        log.info(f"  스킵(변경없음): {total_stats['skipped']}파일")
    log.info(f"  에러: {total_stats['errors']}파일")

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
