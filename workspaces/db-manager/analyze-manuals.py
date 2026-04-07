"""부품매뉴얼 원본 파일 언어 판별 및 불필요 문서 선별 분석"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, re, json
from pathlib import Path

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("PyMuPDF 없음 — 파일명 기반으로만 분석")

BASE = Path('C:/MES/wta-agents/data/manuals-ready')
REPORT_FILE = Path('C:/MES/wta-agents/workspaces/db-manager/manuals-analysis.json')

# 언어 판별 함수
def detect_lang_from_text(text):
    """텍스트에서 언어 판별"""
    if not text or len(text.strip()) < 10:
        return 'unknown'

    korean = len(re.findall(r'[\uAC00-\uD7A3]', text))
    chinese = len(re.findall(r'[\u4E00-\u9FFF]', text))
    japanese = len(re.findall(r'[\u3040-\u30FF]', text))
    total_chars = max(len(text.strip()), 1)

    kr_ratio = korean / total_chars
    zh_ratio = chinese / total_chars
    jp_ratio = japanese / total_chars

    if kr_ratio > 0.05:
        return 'ko'
    elif jp_ratio > 0.03:
        return 'ja'
    elif zh_ratio > 0.05:
        return 'zh'
    else:
        return 'en'

def detect_lang_from_filename(filename):
    """파일명에서 언어 힌트 추출"""
    fn = filename.upper()
    if '_KO' in fn or '_KR' in fn or 'KOREAN' in fn or '한국' in fn:
        return 'ko'
    if '_EN' in fn or '_ENG' in fn or 'ENGLISH' in fn:
        return 'en'
    if '_CN' in fn or '_ZH' in fn or '_CHN' in fn or 'CHINESE' in fn or '_CH_' in fn:
        return 'zh'
    if '_JP' in fn or '_JPN' in fn or 'JAPANESE' in fn or '_JA' in fn:
        return 'ja'
    return None

def is_catalog_or_sales(filename):
    """카탈로그/영업자료 여부"""
    fn = filename.upper()
    keywords = ['CATALOG', 'CATALOGUE', 'BROCHURE', 'DATASHEET', 'DATA_SHEET',
                'FLYER', 'SPEC_SHEET', '카탈로그', '제품소개', 'PRODUCT_OVERVIEW',
                'INTRODUCTION', 'OVERVIEW', 'SELECTION_GUIDE', 'SELECTION GUIDE']
    return any(k in fn for k in keywords)

# 카테고리별 분석
results = {}
summary = {
    'total': 0,
    'by_lang': {'ko': 0, 'en': 0, 'zh': 0, 'ja': 0, 'unknown': 0},
    'by_cat': {},
    'unnecessary': []
}

categories = sorted(d for d in os.listdir(BASE) if os.path.isdir(BASE / d))

for cat in categories:
    cat_path = BASE / cat
    files = sorted(f for f in os.listdir(cat_path) if f.lower().endswith('.pdf'))

    cat_result = {
        'count': len(files),
        'files': [],
        'lang_dist': {'ko': 0, 'en': 0, 'zh': 0, 'ja': 0, 'unknown': 0}
    }

    print(f"\n[{cat}] {len(files)}개 처리 중...")

    for i, fname in enumerate(files):
        fpath = cat_path / fname

        # 파일명 기반 언어 힌트
        lang_hint = detect_lang_from_filename(fname)

        # PDF 첫 페이지 텍스트 추출
        lang = 'unknown'
        page_count = 0
        file_size_kb = round(fpath.stat().st_size / 1024)
        text_sample = ''

        if HAS_FITZ:
            try:
                doc = fitz.open(str(fpath))
                page_count = doc.page_count
                # 첫 2페이지에서 텍스트 추출
                for pn in range(min(2, page_count)):
                    page_text = doc[pn].get_text()
                    text_sample += page_text[:500]
                doc.close()
                lang = detect_lang_from_text(text_sample)
            except Exception as e:
                lang = 'unknown'

        # 파일명 힌트가 있으면 우선 (텍스트 추출 실패 케이스 보완)
        if lang_hint and (lang == 'unknown' or lang == 'en'):
            lang = lang_hint

        # 불필요 문서 판별
        is_catalog = is_catalog_or_sales(fname)
        is_unnecessary = is_catalog or lang == 'zh' or lang == 'ja'

        file_info = {
            'name': fname,
            'lang': lang,
            'pages': page_count,
            'size_kb': file_size_kb,
            'is_catalog': is_catalog,
            'is_unnecessary': is_unnecessary,
            'reason': []
        }

        if lang == 'zh':
            file_info['reason'].append('중국어 문서')
        if lang == 'ja':
            file_info['reason'].append('일본어 문서')
        if is_catalog:
            file_info['reason'].append('카탈로그/영업자료')

        cat_result['files'].append(file_info)
        cat_result['lang_dist'][lang] = cat_result['lang_dist'].get(lang, 0) + 1

        if is_unnecessary:
            summary['unnecessary'].append(f"{cat}/{fname}")

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(files)} 처리 완료")

    results[cat] = cat_result
    summary['total'] += len(files)
    for lang, cnt in cat_result['lang_dist'].items():
        summary['by_lang'][lang] = summary['by_lang'].get(lang, 0) + cnt
    summary['by_cat'][cat] = {
        'count': len(files),
        'lang_dist': cat_result['lang_dist'],
        'unnecessary_count': sum(1 for f in cat_result['files'] if f['is_unnecessary'])
    }

    print(f"  언어 분포: {cat_result['lang_dist']}")

# 저장
with open(REPORT_FILE, 'w', encoding='utf-8') as f:
    json.dump({'summary': summary, 'details': results}, f, ensure_ascii=False, indent=2)

print(f"\n\n=== 전체 요약 ===")
print(f"총 파일: {summary['total']}개")
print(f"언어 분포: {summary['by_lang']}")
print(f"불필요 문서 후보: {len(summary['unnecessary'])}개")
print(f"\n카테고리별:")
for cat, info in summary['by_cat'].items():
    print(f"  {cat}: {info['count']}개, 불필요={info['unnecessary_count']}개, 언어={info['lang_dist']}")
print(f"\n결과 저장: {REPORT_FILE}")
