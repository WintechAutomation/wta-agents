"""
GraphRAG PoC: 4개 주제 텍스트 추출
confluence-분말검사 / 연삭측정제어 / 장비물류 / 호닝신뢰성
출력: poc-texts-all/{topic}/{pageId}-{title}.txt
"""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

BASE = Path("C:/MES/wta-agents/reports/MAX")
DST_BASE = Path("C:/MES/wta-agents/workspaces/research-agent/poc-texts-all")
DST_BASE.mkdir(exist_ok=True)

TOPICS = ["분말검사", "연삭측정제어", "장비물류", "호닝신뢰성", "포장혼입검사"]

all_index = []

for topic in TOPICS:
    src = BASE / f"confluence-{topic}"
    if not src.exists():
        print(f"[SKIP] {topic} — 폴더 없음")
        continue

    dst = DST_BASE / topic
    dst.mkdir(exist_ok=True)
    # 기존 파일 초기화
    for f in dst.glob("*.txt"):
        f.unlink()

    count = 0
    for page_dir in sorted(src.iterdir()):
        html_path = page_dir / "index.html"
        meta_path = page_dir / "images-meta.json"
        if not html_path.exists():
            continue

        html = html_path.read_text(encoding="utf-8")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

        body_match = re.search(r"<body>(.*?)</body>", html, re.DOTALL)
        if not body_match:
            continue

        text = re.sub(r"<style[^>]*>.*?</style>", " ", body_match.group(1), flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r'image-\d{8}-\d{6}\.png', '[이미지]', text)
        text = re.sub(r'\[이미지\](\s*\[이미지\])+', '[이미지들]', text)

        page_title = meta.get("page_title", page_dir.name)
        page_id = meta.get("page_id", "")
        cf_url = meta.get("confluence_url", "")
        breadcrumb = meta.get("breadcrumb", "")

        header = f"""=== Confluence 문서 ===
제목: {page_title}
페이지ID: {page_id}
주제: {topic}
경로: {breadcrumb}
URL: {cf_url}
이미지: {len(meta.get('downloaded', []))}개
========================

"""
        full_text = header + text
        safe_name = re.sub(r'[<>:"/\\|?*\s]', '_', page_title)[:55]
        out_file = dst / f"{page_id}-{safe_name}.txt"
        out_file.write_text(full_text, encoding="utf-8")

        all_index.append({
            "topic": topic,
            "page_id": page_id,
            "title": page_title,
            "file": str(out_file.relative_to(DST_BASE)),
            "chars": len(full_text),
        })
        count += 1
        print(f"  [{topic}] {page_title[:45]} ({len(full_text):,}자)")

    print(f"  → {topic}: {count}페이지 완료\n")

# 전체 인덱스 저장
index_file = DST_BASE / "_index.json"
index_file.write_text(json.dumps(all_index, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"총 {len(all_index)}페이지 추출 완료 → {DST_BASE}")
