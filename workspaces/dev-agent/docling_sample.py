"""Docling 파싱 예시 출력 스크립트."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.settings import ImageRefMode

INPUT_PDF = r"C:\MES\wta-agents\data\manuals-ready\4_servo\Fastech_SERVOII_Manual_KO.pdf"
OUTPUT_MD = r"C:\MES\wta-agents\workspaces\dev-agent\docling-sample-output.md"

print(f"파싱 시작: {INPUT_PDF}")

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.do_table_structure = True

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: {"pipeline_options": pipeline_options}
    }
)

result = converter.convert(INPUT_PDF)
doc = result.document
md_text = doc.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)

print(f"전체 Markdown 길이: {len(md_text)}자")

# 전체 저장
with open(OUTPUT_MD, "w", encoding="utf-8") as f:
    f.write(md_text)

print(f"저장 완료: {OUTPUT_MD}")

# 5페이지 분량 추정 (전체의 앞부분 ~15000자 또는 섹션 기준)
import re
sections = re.split(r"(?=^#{1,3}\s)", md_text, flags=re.MULTILINE)
print(f"섹션 수: {len(sections)}")

# 표 개수
tables = re.findall(r"((?:^\|.*\n?)+)", md_text, flags=re.MULTILINE)
print(f"표 개수: {len(tables)}")

# 이미지 플레이스홀더
images = re.findall(r"<!-- image -->", md_text)
print(f"이미지 플레이스홀더: {len(images)}")

# 헤딩 목록 (처음 20개)
headings = re.findall(r"^(#{1,4}\s+.+)", md_text, flags=re.MULTILINE)
print(f"\n헤딩 목록 (처음 20개):")
for h in headings[:20]:
    print(f"  {h}")
