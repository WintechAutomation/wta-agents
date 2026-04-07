"""PDF 파서 비교 테스트 — CID 깨짐 분석"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

pdf_path = 'C:/MES/wta-agents/data/manuals-ready/4_servo/Fastech_SERVO-ST_Manual_KO.pdf'
pages_to_test = 3

print("=" * 60)
print("1. PyMuPDF (fitz) 테스트")
print("=" * 60)
try:
    import fitz
    doc = fitz.open(pdf_path)
    print(f"총 페이지: {doc.page_count}")
    for i in range(min(pages_to_test, doc.page_count)):
        text = doc[i].get_text()
        cid_count = text.count('(cid:')
        print(f"[페이지 {i+1}] {len(text)}자, CID 수: {cid_count}")
        print(text[:400])
        print("---")
    doc.close()
except Exception as e:
    print(f"오류: {e}")

print()
print("=" * 60)
print("2. pdfplumber 테스트")
print("=" * 60)
try:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        print(f"총 페이지: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages[:pages_to_test]):
            text = page.extract_text() or ''
            cid_count = text.count('(cid:')
            print(f"[페이지 {i+1}] {len(text)}자, CID 수: {cid_count}")
            print(text[:400])
            print("---")
except Exception as e:
    print(f"오류: {e}")

print()
print("=" * 60)
print("3. PyMuPDF HTML 모드 (폰트 정보 포함)")
print("=" * 60)
try:
    import fitz, re
    doc = fitz.open(pdf_path)
    for i in range(min(2, doc.page_count)):
        html = doc[i].get_text("html")
        # HTML 태그 제거
        clean = re.sub(r'<[^>]+>', ' ', html)
        clean = re.sub(r'\s+', ' ', clean).strip()
        cid_count = clean.count('(cid:')
        print(f"[페이지 {i+1}] {len(clean)}자, CID 수: {cid_count}")
        print(clean[:400])
        print("---")
    doc.close()
except Exception as e:
    print(f"오류: {e}")

print()
print("=" * 60)
print("4. PyMuPDF rawdict 모드 (원시 문자 데이터)")
print("=" * 60)
try:
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]
    blocks = page.get_text("rawdict")["blocks"]
    sample_chars = []
    for b in blocks[:3]:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                font = span.get("font", "")
                for c in span.get("chars", [])[:5]:
                    sample_chars.append(f"char={repr(c.get('c',''))}, unicode={c.get('c','')!r}, font={font}")
    print("샘플 문자 정보:")
    for s in sample_chars[:10]:
        print(" ", s)
    doc.close()
except Exception as e:
    print(f"오류: {e}")

print()
print("=" * 60)
print("5. OCR 가능 여부 확인 (pdf2image 설치 확인)")
print("=" * 60)
try:
    import pdf2image
    print("pdf2image: 설치됨")
except ImportError:
    print("pdf2image: 미설치 (pip install pdf2image 필요)")

try:
    import pytesseract
    print("pytesseract: 설치됨")
    ver = pytesseract.get_tesseract_version()
    print(f"tesseract 버전: {ver}")
except ImportError:
    print("pytesseract: 미설치")
except Exception as e:
    print(f"pytesseract 오류: {e}")
