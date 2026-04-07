"""
포장혼입검사 7페이지 HTML → 텍스트 추출
출력: workspaces/research-agent/poc-texts/*.txt
"""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

SRC = Path("C:/MES/wta-agents/reports/MAX/confluence-포장혼입검사")
DST = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts")
DST.mkdir(exist_ok=True)

# 기존 파일 초기화
for f in DST.glob("*.txt"):
    f.unlink()

pages_info = []
for page_dir in sorted(SRC.iterdir()):
    html_path = page_dir / "index.html"
    meta_path = page_dir / "images-meta.json"
    if not html_path.exists():
        continue

    html = html_path.read_text(encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    # body 내용 추출
    body_match = re.search(r"<body>(.*?)</body>", html, re.DOTALL)
    if not body_match:
        continue

    # HTML 태그 제거
    text = re.sub(r"<style[^>]*>.*?</style>", " ", body_match.group(1), flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 이미지 파일명 제거 (image-20250xxx.png 패턴)
    text = re.sub(r'image-\d{8}-\d{6}\.png', '[이미지]', text)
    text = re.sub(r'\[이미지\](\s*\[이미지\])+', '[이미지들]', text)

    page_title = meta.get("page_title", page_dir.name)
    page_id = meta.get("page_id", "")
    cf_url = meta.get("confluence_url", "")
    breadcrumb = meta.get("breadcrumb", "")

    header = f"""=== Confluence 문서 ===
제목: {page_title}
페이지ID: {page_id}
경로: {breadcrumb}
URL: {cf_url}
이미지: {len(meta.get('downloaded', []))}개
========================

"""
    full_text = header + text

    # 파일명 안전화
    safe_name = re.sub(r'[<>:"/\\|?*\s]', '_', page_title)[:60]
    out_file = DST / f"{page_id}-{safe_name}.txt"
    out_file.write_text(full_text, encoding="utf-8")

    pages_info.append({
        "page_id": page_id,
        "title": page_title,
        "file": out_file.name,
        "chars": len(full_text),
    })
    print(f"  추출: {page_title[:50]} ({len(full_text):,}자)")

# 추출 목록 JSON 저장
index_file = DST / "_index.json"
index_file.write_text(json.dumps(pages_info, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n총 {len(pages_info)}개 파일 추출 완료 → {DST}")
