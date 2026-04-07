"""test-docling.py — Docling 파싱 품질 테스트.

PDF 1개 + DOCX 1개 샘플로 Docling 변환 결과 확인.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import time
from pathlib import Path
from docling.document_converter import DocumentConverter

SAMPLES = [
    Path("C:/MES/wta-agents/data/wta-manuals-final/소결취출기/1. User Manual (Sintering Sorter Handling MC).pdf"),
    Path("C:/MES/wta-agents/data/wta-manuals-final/소결취출기/OKE 소결취출기 #1 유지 보수.docx"),
]


def test_sample(converter: DocumentConverter, fpath: Path):
    print(f"\n{'='*60}")
    print(f"파일: {fpath.name}")
    print(f"크기: {fpath.stat().st_size / 1024:.0f} KB")
    print(f"{'='*60}")

    t0 = time.time()
    result = converter.convert(str(fpath))
    elapsed = time.time() - t0

    doc = result.document

    # Markdown 변환
    md = doc.export_to_markdown()

    # 통계
    print(f"변환 시간: {elapsed:.1f}초")
    print(f"Markdown 길이: {len(md)} chars")
    print(f"줄 수: {md.count(chr(10))}")

    # 테이블 수 (Markdown에서 | 패턴)
    table_lines = [l for l in md.split('\n') if l.strip().startswith('|')]
    print(f"테이블 라인: {len(table_lines)}")

    # 이미지 참조
    img_refs = md.count('![')
    print(f"이미지 참조: {img_refs}")

    # 첫 500자 미리보기
    print(f"\n--- 미리보기 (첫 1000자) ---")
    print(md[:1000])
    print(f"--- 끝 ---")

    # 마크다운 파일로 저장
    out = fpath.with_suffix('.docling.md')
    out.write_text(md, encoding='utf-8')
    print(f"\n전체 결과 저장: {out}")

    return {
        'file': fpath.name,
        'time_sec': round(elapsed, 1),
        'md_chars': len(md),
        'lines': md.count('\n'),
        'table_lines': len(table_lines),
        'img_refs': img_refs,
    }


def main():
    print("Docling 파싱 테스트 시작")
    converter = DocumentConverter()

    results = []
    for fpath in SAMPLES:
        if not fpath.exists():
            print(f"파일 없음: {fpath}")
            continue
        try:
            r = test_sample(converter, fpath)
            results.append(r)
        except Exception as e:
            print(f"오류: {fpath.name} → {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("요약")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['file']}: {r['time_sec']}초, {r['md_chars']}자, 테이블 {r['table_lines']}줄, 이미지 {r['img_refs']}개")


if __name__ == "__main__":
    main()
