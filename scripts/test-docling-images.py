"""test-docling-images.py — Docling 이미지 추출 옵션 테스트.

generate_picture_images=True + ImageRefMode.REFERENCED 로 PDF 재테스트.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import time
from pathlib import Path

from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode

SAMPLE_PDF = Path("C:/MES/wta-agents/data/wta-manuals-final/소결취출기/1. User Manual (Sintering Sorter Handling MC).pdf")
OUTPUT_DIR = Path("C:/MES/wta-agents/data/docling-test-output")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 이미지 추출 옵션 설정
    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_page_images = False  # 페이지 전체 이미지는 불필요
    pipeline_options.generate_table_images = True   # 테이블 이미지도 추출
    pipeline_options.images_scale = 2.0  # 이미지 해상도 스케일

    print(f"설정:")
    print(f"  generate_picture_images: {pipeline_options.generate_picture_images}")
    print(f"  generate_table_images: {pipeline_options.generate_table_images}")
    print(f"  images_scale: {pipeline_options.images_scale}")

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )

    print(f"\n파일: {SAMPLE_PDF.name} ({SAMPLE_PDF.stat().st_size / 1024:.0f} KB)")
    print("변환 시작...")

    t0 = time.time()
    result = converter.convert(str(SAMPLE_PDF))
    elapsed = time.time() - t0

    doc = result.document
    print(f"변환 완료: {elapsed:.1f}초")

    # 1) REFERENCED 모드 Markdown (이미지 파일 경로 포함)
    md_ref = doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED)
    md_ref_path = OUTPUT_DIR / "manual_referenced.md"
    md_ref_path.write_text(md_ref, encoding='utf-8')

    # 2) EMBEDDED 모드 (base64 인라인)
    md_emb = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
    md_emb_path = OUTPUT_DIR / "manual_embedded.md"
    md_emb_path.write_text(md_emb, encoding='utf-8')

    # 3) PLACEHOLDER 모드 (기존 테스트와 동일)
    md_ph = doc.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)

    # 통계
    ref_imgs = md_ref.count('![')
    emb_imgs = md_emb.count('![')
    ph_imgs = md_ph.count('<!-- image')

    print(f"\n■ Markdown 통계:")
    print(f"  REFERENCED: {len(md_ref)} chars, 이미지 참조 {ref_imgs}개")
    print(f"  EMBEDDED:   {len(md_emb)} chars, 이미지 인라인 {emb_imgs}개")
    print(f"  PLACEHOLDER: {len(md_ph)} chars, placeholder {ph_imgs}개")

    # 이미지 파일 저장 (REFERENCED 모드용)
    # docling은 이미지를 document 객체 내에 보관
    img_count = 0
    if hasattr(doc, 'pictures'):
        for i, pic in enumerate(doc.pictures):
            if hasattr(pic, 'image') and pic.image is not None:
                img_path = OUTPUT_DIR / f"picture_{i}.png"
                pic.image.pil_image.save(str(img_path))
                img_count += 1
    print(f"  추출된 picture 객체: {img_count}개")

    # 테이블 이미지
    tbl_count = 0
    if hasattr(doc, 'tables'):
        for i, tbl in enumerate(doc.tables):
            if hasattr(tbl, 'image') and tbl.image is not None:
                img_path = OUTPUT_DIR / f"table_{i}.png"
                tbl.image.pil_image.save(str(img_path))
                tbl_count += 1
    print(f"  추출된 table 이미지: {tbl_count}개")

    # JSON 내보내기
    json_out = doc.export_to_dict()
    import json
    json_path = OUTPUT_DIR / "manual.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  JSON 저장: {json_path} ({json_path.stat().st_size / 1024:.0f} KB)")

    # REFERENCED 마크다운에서 이미지 경로 샘플
    print(f"\n■ REFERENCED 마크다운 이미지 참조 샘플 (처음 5개):")
    for line in md_ref.split('\n'):
        if '![' in line:
            print(f"  {line[:150]}")
            ref_imgs -= 1
            if ref_imgs <= len(md_ref.split('\n')) - 5:
                break

    print(f"\n저장 위치: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
