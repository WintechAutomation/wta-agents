"""smart_chunk_markdown 함수 단독 테스트 스크립트."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
import re
import json
from collections import Counter

# batch-parse-docling.py에서 필요한 상수와 함수만 가져오기
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TABLE_MAX_SIZE = 2000
MIN_CHUNK_LEN = 50


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """텍스트를 size 단위로 분할 (overlap 겹침)."""
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
    """큰 표를 max_size 이하로 분할 (헤더+구분선 유지)."""
    lines = table_md.split("\n")
    if len(lines) < 3:
        return [table_md]

    header = lines[0]
    separator = lines[1]
    data_lines = lines[2:]

    header_block = f"{header}\n{separator}"
    header_len = len(header_block) + 1  # +1 for newline

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
    """min_len 미만 청크를 인접 청크에 병합."""
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
    """개선된 마크다운 청킹."""
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

    # 짧은 텍스트 청크 병합
    text_chunks = [c for c in chunks if c["chunk_type"] == "text"]
    table_chunks = [c for c in chunks if c["chunk_type"] != "text"]

    text_contents = [c["content"] for c in text_chunks]
    merged_contents = _merge_short_chunks(text_contents, MIN_CHUNK_LEN, CHUNK_SIZE)

    merged_text_chunks = []
    heading_map = {c["content"]: c["heading"] for c in text_chunks}
    for mc in merged_contents:
        heading = heading_map.get(mc, "")
        if not heading:
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

    # Contextual prefix + 빈 청크 필터
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


# -- 테스트 실행 --
def test_file(md_path):
    """MD 파일에 대해 smart_chunk_markdown 실행 후 통계 출력."""
    filename = os.path.basename(md_path)
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    chunks = smart_chunk_markdown(md_text, filename)

    # 통계
    types = Counter(c["chunk_type"] for c in chunks)
    lengths = [len(c["content"]) for c in chunks]

    print(f"\n{'='*60}")
    print(f"파일: {filename}")
    print(f"원본 MD 길이: {len(md_text):,}자")
    print(f"총 청크 수: {len(chunks)}")
    print(f"타입별: {dict(types)}")
    if lengths:
        print(f"평균 길이: {sum(lengths)/len(lengths):.0f}자")
        print(f"최소 길이: {min(lengths)}자")
        print(f"최대 길이: {max(lengths)}자")
        print(f"50자 미만 청크: {sum(1 for l in lengths if l < 50)}개")

    # 표 청크 샘플
    table_chunks = [c for c in chunks if c["chunk_type"] == "table"]
    if table_chunks:
        print(f"\n표 청크 ({len(table_chunks)}개) 길이:")
        for i, tc in enumerate(table_chunks[:5]):
            print(f"  [{i}] {len(tc['content'])}자 - heading: {tc.get('heading', '')[:30]}")

    # 첫 3개 청크 미리보기
    print(f"\n첫 3개 청크 미리보기:")
    for i, c in enumerate(chunks[:3]):
        preview = c["content"][:120].replace("\n", " ")
        print(f"  [{i}] ({c['chunk_type']}, {len(c['content'])}자) {preview}...")

    return chunks


if __name__ == "__main__":
    parsed_dir = "C:/MES/wta-agents/data/wta_parsed"

    # 테스트할 파일 선택 (4_servo 카테고리 파일 또는 일반 파일 2개)
    test_files = []
    for f in sorted(os.listdir(parsed_dir)):
        if f.endswith(".md"):
            test_files.append(os.path.join(parsed_dir, f))
        if len(test_files) >= 2:
            break

    if not test_files:
        print("테스트할 MD 파일 없음")
        sys.exit(1)

    all_chunks = []
    for tf in test_files:
        chunks = test_file(tf)
        all_chunks.extend(chunks)

    # 전체 요약
    print(f"\n{'='*60}")
    print(f"전체 요약: {len(test_files)}개 파일, {len(all_chunks)}개 청크")
    total_types = Counter(c["chunk_type"] for c in all_chunks)
    print(f"타입별: {dict(total_types)}")
    all_lens = [len(c["content"]) for c in all_chunks]
    if all_lens:
        print(f"평균: {sum(all_lens)/len(all_lens):.0f}자, 최소: {min(all_lens)}자, 최대: {max(all_lens)}자")
