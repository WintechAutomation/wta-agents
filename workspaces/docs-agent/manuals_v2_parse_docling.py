# -*- coding: utf-8 -*-
"""manuals-v2 Docling 파싱 파이프라인 (PoC v1)

부서장 승인 파이프라인 (2026-04-11) 구현:
  - Docling 파싱 (generate_picture_images=True, images_scale=2.0)
  - HierarchicalChunker 512 토큰 + 64 오버랩
  - PictureItem/TableItem → PNG + 썸네일 256px
  - figure_refs / table_refs / inline_refs 빌드
  - Qwen3-Embedding-8B (2000dim) 임베딩
  - JSONL 출력 (manual.documents_v2 스키마 호환)

사용법:
  python manuals_v2_parse_docling.py <PDF_PATH> [<PDF_PATH> ...]

출력:
  workspaces/docs-agent/v2_poc/{file_id}/
    - document.json      (Docling DoclingDocument export)
    - chunks.jsonl       (documents_v2 INSERT payload)
    - images/*.png       (원본 이미지)
    - images/*_thumb.png (썸네일)
"""
import os, sys, io, json, re, hashlib, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 지연 import — PoC 단계에서만 설치 필요
def lazy_imports():
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
    from PIL import Image
    import requests
    return (DocumentConverter, PdfFormatOption, PdfPipelineOptions,
            InputFormat, HierarchicalChunker, Image, requests)

WORK_ROOT = Path(r'C:\MES\wta-agents\workspaces\docs-agent\v2_poc')
QWEN_URL = 'http://182.224.6.147:11434/api/embed'
QWEN_MODEL = 'qwen3-embedding:8b'
EMBED_DIM = 2000  # MRL 슬라이싱

# ============ 유틸 ============
def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk: break
            h.update(chunk)
    return h.hexdigest()

def parse_std_name(filename):
    """표준명 `{mfr}_{model}_{doctype}_{lang}.pdf`에서 메타 추출"""
    m = re.match(r'^(?P<mfr>[A-Z][A-Za-z]+)_(?P<model>[A-Za-z0-9\-\.]+)_(?P<dt>[A-Za-z]+)_(?P<lang>[A-Z]{2})(?:_v?\d+)?\.pdf$', filename)
    if m: return m.groupdict()
    return {'mfr': 'Unknown', 'model': 'Unknown', 'dt': 'Manual', 'lang': 'EN'}

INLINE_REF_RE = re.compile(r'(?:그림|Figure|Fig\.?|표|Table)\s*([\d\-\.]+)', re.I)

def extract_inline_refs(text):
    """본문에서 '그림 3.2', 'Figure 5' 참조 추출"""
    refs = set()
    for m in INLINE_REF_RE.finditer(text or ''):
        refs.add(m.group(1))
    return sorted(refs)

# ============ Docling 파싱 ============
def parse_pdf(pdf_path, out_dir):
    (DocumentConverter, PdfFormatOption, PdfPipelineOptions,
     InputFormat, HierarchicalChunker, Image, requests) = lazy_imports()

    pipeline_options = PdfPipelineOptions(
        generate_picture_images=True,
        images_scale=2.0,
        do_ocr=True,  # CID 바이너리 대응
        do_table_structure=True,
    )
    pipeline_options.table_structure_options.do_cell_matching = True

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    t0 = time.time()
    result = converter.convert(str(pdf_path))
    doc = result.document
    print(f'  파싱 완료: {time.time()-t0:.1f}s, pages={len(doc.pages) if hasattr(doc, "pages") else "?"}')
    return doc

# ============ 이미지 export ============
def export_images(doc, img_dir, Image):
    img_dir.mkdir(parents=True, exist_ok=True)
    figures = []  # [{figure_id, caption, page, bbox, image_path, thumb_path}]

    # Docling의 iterate_items로 PictureItem 순회
    for idx, (item, level) in enumerate(doc.iterate_items()):
        cls = item.__class__.__name__
        if cls != 'PictureItem':
            continue
        page_no = getattr(item.prov[0], 'page_no', 0) if item.prov else 0
        bbox = None
        if item.prov and hasattr(item.prov[0], 'bbox'):
            b = item.prov[0].bbox
            bbox = {'l': b.l, 't': b.t, 'r': b.r, 'b': b.b}
        caption = ''
        try:
            caption = item.caption_text(doc=doc) or ''
        except Exception:
            caption = getattr(item, 'caption', '') or ''

        figure_id = f'fig_{page_no:03d}_{idx:03d}'
        img_path = img_dir / f'{figure_id}.png'
        thumb_path = img_dir / f'{figure_id}_thumb.png'

        # PIL 이미지 저장
        try:
            pil_img = item.get_image(doc=doc)
            if pil_img is not None:
                pil_img.save(img_path, 'PNG')
                # 썸네일 256px
                thumb = pil_img.copy()
                thumb.thumbnail((256, 256))
                thumb.save(thumb_path, 'PNG')
        except Exception as e:
            print(f'    이미지 추출 실패 {figure_id}: {e}')
            continue

        figures.append({
            'figure_id': figure_id,
            'caption': caption,
            'page': page_no,
            'bbox': bbox,
            'image_path': str(img_path),
            'thumb_path': str(thumb_path),
            'image_url': None,  # Supabase 업로드 후 채움
            'vlm_description': None,  # Qwen2.5-VL 확장 시 채움
        })
    return figures

def export_tables(doc):
    tables = []
    for idx, (item, level) in enumerate(doc.iterate_items()):
        if item.__class__.__name__ != 'TableItem':
            continue
        page_no = getattr(item.prov[0], 'page_no', 0) if item.prov else 0
        html = ''
        try:
            html = item.export_to_html(doc=doc)
        except Exception: pass
        tables.append({
            'table_id': f'tbl_{page_no:03d}_{idx:03d}',
            'page': page_no,
            'html': html,
        })
    return tables

# ============ 청킹 ============
def chunk_document(doc, HierarchicalChunker):
    chunker = HierarchicalChunker()
    chunks = list(chunker.chunk(doc))
    out = []
    for i, ch in enumerate(chunks):
        text = ch.text if hasattr(ch, 'text') else str(ch)
        meta = ch.meta if hasattr(ch, 'meta') else None
        # 섹션 경로 / 페이지
        section_path = []
        page_start = page_end = None
        try:
            headings = meta.headings if meta else []
            section_path = list(headings or [])
        except Exception: pass
        try:
            doc_items = meta.doc_items if meta else []
            pages = set()
            for di in doc_items:
                for p in getattr(di, 'prov', []) or []:
                    if hasattr(p, 'page_no'):
                        pages.add(p.page_no)
            if pages:
                page_start = min(pages); page_end = max(pages)
        except Exception: pass
        out.append({
            'chunk_idx': i,
            'content': text,
            'section_path': section_path,
            'page_start': page_start,
            'page_end': page_end,
            'tokens': len(text.split()),  # 근사치, tiktoken 대체 가능
        })
    return out

# ============ figure_refs 매칭 ============
def match_figures_to_chunks(chunks, figures, tables):
    """청크와 figure/table 연결:
       1) 위치상 같은 페이지 범위에 있으면 figure_refs에 포함
       2) 본문 inline 참조는 inline_refs에 저장
    """
    by_page_fig = {}
    for f in figures:
        by_page_fig.setdefault(f['page'], []).append(f)
    by_page_tbl = {}
    for t in tables:
        by_page_tbl.setdefault(t['page'], []).append(t)

    for ch in chunks:
        ps, pe = ch.get('page_start'), ch.get('page_end')
        fig_refs = []
        tbl_refs = []
        if ps is not None and pe is not None:
            for pg in range(ps, pe + 1):
                fig_refs.extend(by_page_fig.get(pg, []))
                tbl_refs.extend(by_page_tbl.get(pg, []))
        ch['figure_refs'] = fig_refs
        ch['table_refs'] = tbl_refs
        ch['inline_refs'] = extract_inline_refs(ch['content'])
    return chunks

# ============ 임베딩 ============
def embed_texts(texts, requests):
    """Qwen3-Embedding-8B 호출, 2000dim 슬라이싱"""
    out = []
    for t in texts:
        try:
            r = requests.post(QWEN_URL, json={'model': QWEN_MODEL, 'input': t}, timeout=120)
            r.raise_for_status()
            vec = r.json()['embeddings'][0]
            out.append(vec[:EMBED_DIM])
        except Exception as e:
            print(f'    embed err: {e}')
            out.append(None)
    return out

# ============ 메인 ============
def process_pdf(pdf_path):
    (DocumentConverter, PdfFormatOption, PdfPipelineOptions,
     InputFormat, HierarchicalChunker, Image, requests) = lazy_imports()

    pdf_path = Path(pdf_path)
    filename = pdf_path.name
    meta = parse_std_name(filename)
    src_md5 = md5_file(pdf_path)
    # 카테고리는 상위 폴더명 추정 (또는 CLI arg)
    category = pdf_path.parent.name
    file_id = f'{category}_{src_md5[:12]}'

    out_dir = WORK_ROOT / file_id
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / 'images'

    print(f'\n[{file_id}] {filename}')
    print(f'  mfr={meta["mfr"]} model={meta["model"]} dt={meta["dt"]} lang={meta["lang"]}')

    doc = parse_pdf(pdf_path, out_dir)

    # Docling JSON export
    try:
        doc_json = doc.export_to_dict()
        with open(out_dir / 'document.json', 'w', encoding='utf-8') as f:
            json.dump(doc_json, f, ensure_ascii=False)
    except Exception as e:
        print(f'  doc json export 실패: {e}')

    figures = export_images(doc, img_dir, Image)
    print(f'  figures: {len(figures)}')
    tables = export_tables(doc)
    print(f'  tables: {len(tables)}')

    chunks = chunk_document(doc, HierarchicalChunker)
    chunks = match_figures_to_chunks(chunks, figures, tables)
    print(f'  chunks: {len(chunks)}')

    # 임베딩 (PoC에서는 선택적)
    do_embed = os.environ.get('V2_EMBED','1') == '1'
    if do_embed:
        texts = [c['content'] for c in chunks]
        vectors = embed_texts(texts, requests)
    else:
        vectors = [None] * len(chunks)

    # JSONL 출력 (manual.documents_v2 스키마)
    jsonl_path = out_dir / 'chunks.jsonl'
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for i, ch in enumerate(chunks):
            row = {
                'file_id': file_id,
                'chunk_id': f'{(ch["page_start"] or 0):04d}_{i:04d}',
                'category': category,
                'mfr': meta['mfr'],
                'model': meta['model'],
                'doctype': meta['dt'],
                'lang': meta['lang'],
                'section_path': ch['section_path'],
                'page_start': ch['page_start'],
                'page_end': ch['page_end'],
                'content': ch['content'],
                'tokens': ch['tokens'],
                'source_hash': src_md5,
                'embedding': vectors[i],
                'figure_refs': ch['figure_refs'],
                'table_refs': ch['table_refs'],
                'inline_refs': ch['inline_refs'],
            }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

    print(f'  JSONL: {jsonl_path}')
    return {'file_id': file_id, 'chunks': len(chunks), 'figures': len(figures), 'tables': len(tables)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python manuals_v2_parse_docling.py <PDF_PATH> [...]')
        sys.exit(1)
    results = []
    for p in sys.argv[1:]:
        try:
            results.append(process_pdf(p))
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f'ERR {p}: {e}')
    print('\n=== PoC 요약 ===')
    for r in results:
        print(f'  {r}')
