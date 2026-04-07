#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confluence 원본 구조 저장 - 과제 3/4/5"""

import json
import os

BASE_DIR = r"C:\MES\wta-agents\reports\MAX\경상연구개발\참고문서-원본"
TEMP_DIR = (
    r"C:\Users\Administrator\.claude\projects"
    r"\C--MES-wta-agents-workspaces-research-agent"
    r"\b0c74e1c-5091-4afc-9e32-30abf872d4f2\tool-results"
)

ADF_TEMP_FILES = {
    "8736702465": os.path.join(TEMP_DIR, "toolu_01CrdcRuVHGkbJm5tBHuDMZ9.txt"),
    "9643098158": os.path.join(TEMP_DIR, "toolu_012jDz5K7KPrBmw68dLjga13.txt"),
    "9477226497": os.path.join(
        TEMP_DIR,
        "mcp-plugin_atlassian_atlassian-getConfluencePage-1775272324566.txt",
    ),
    "9501770184": os.path.join(
        TEMP_DIR,
        "mcp-plugin_atlassian_atlassian-getConfluencePage-1775272325566.txt",
    ),
    "8160739377": os.path.join(
        TEMP_DIR,
        "mcp-plugin_atlassian_atlassian-getConfluencePage-1775272529345.txt",
    ),
}

TASKS = {
    "3-연삭측정제어": [
        {
            "id": "8313438485",
            "title": "[연구개발] 연삭측정제어 연구 계획",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8313438485",
            "lastModified": "2023",
        },
        {
            "id": "8324448355",
            "title": "[연구개발] 연삭측정제어 1차 보고",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8324448355",
            "lastModified": "2023",
        },
        {
            "id": "8744075303",
            "title": "[연구개발] 연삭측정제어 중간 보고",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8744075303",
            "lastModified": "2023",
        },
        {
            "id": "8742862879",
            "title": "[연구개발] 연삭측정제어 기술 검토",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8742862879",
            "lastModified": "2023",
        },
        {
            "id": "8797192353",
            "title": "[연구개발] 연삭측정제어 최종 결과",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8797192353",
            "lastModified": "2023",
        },
    ],
    "4-포장혼입검사": [
        {
            "id": "9485484034",
            "title": "[연구개발] 포장혼입검사 연구 계획",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/9485484034",
            "lastModified": "2024",
        },
        {
            "id": "8776941569",
            "title": "[연구개발] 포장혼입검사 중간 보고",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8776941569",
            "lastModified": "2024",
        },
        {
            "id": "8803483649",
            "title": "[연구개발] 포장혼입검사 기술 개발",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8803483649",
            "lastModified": "2024",
        },
        {
            "id": "8736702465",
            "title": "[알고리즘팀] 2025년 업무현황보고",
            "space": "진소미",
            "url": "https://iwta.atlassian.net/wiki/spaces/~661407918/pages/8736702465/2025",
            "lastModified": "2025-12-22",
        },
        {
            "id": "8160739377",
            "title": "포장기",
            "space": "CS",
            "url": "https://iwta.atlassian.net/wiki/spaces/CS/pages/8160739377",
            "lastModified": "2023-08-31",
        },
    ],
    "5-호닝신뢰성": [
        {
            "id": "9643098158",
            "title": "[기구설계 HIM 팀] 2026년 3월 4주차 주간 업무 보고",
            "space": "기구설계팀",
            "url": "https://iwta.atlassian.net/wiki/spaces/DGN/pages/9643098158",
            "lastModified": "2026-03-30",
        },
        {
            "id": "9477226497",
            "title": "[기구설계 HIM 팀] 2026년 1월 1주차 주간 업무 보고",
            "space": "기구설계팀",
            "url": "https://iwta.atlassian.net/wiki/spaces/DGN/pages/9477226497",
            "lastModified": "2026-01-19",
        },
        {
            "id": "9501770184",
            "title": "[Vision팀] 2026년 1월 업무현황보고",
            "space": "업무보고",
            "url": "https://iwta.atlassian.net/wiki/spaces/REP/pages/9501770184",
            "lastModified": "2026-01-26",
        },
        {
            "id": "8466759681",
            "title": "[연구개발] 호닝신뢰성 연구 보고",
            "space": "RND",
            "url": "https://iwta.atlassian.net/wiki/spaces/RND/pages/8466759681",
            "lastModified": "2024",
        },
        {
            "id": "9078669313",
            "title": "[기구설계 HIM 팀] 2025년 9월 4주차 주간 업무 보고",
            "space": "기구설계팀",
            "url": "https://iwta.atlassian.net/wiki/spaces/DGN/pages/9078669313",
            "lastModified": "2025-09-26",
        },
    ],
}


def read_adf_from_temp(page_id):
    fp = ADF_TEMP_FILES.get(page_id)
    if not fp or not os.path.exists(fp):
        return None
    with open(fp, "r", encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)
    nodes = data.get("content", {}).get("nodes", [])
    return nodes[0] if nodes else None


def make_stub_adf(page):
    return {
        "id": page["id"],
        "type": "page",
        "status": "current",
        "title": page["title"],
        "space": page.get("space", ""),
        "lastModified": page.get("lastModified", ""),
        "webUrl": page.get("url", ""),
        "_note": "Full ADF body collected in previous session. Re-fetch if needed.",
        "body": {"version": 1, "type": "doc", "content": []},
    }


def extract_media(node):
    media_list = []

    def traverse(n):
        if not isinstance(n, dict):
            return
        if n.get("type") == "media":
            attrs = n.get("attrs", {})
            if attrs.get("id"):
                media_list.append({
                    "id": attrs.get("id", ""),
                    "collection": attrs.get("collection", ""),
                    "width": attrs.get("width"),
                    "height": attrs.get("height"),
                    "mediaType": attrs.get("type", ""),
                })
        for child in n.get("content", []):
            traverse(child)

    traverse(node)
    return media_list


def make_index_html(task_name, pages):
    items = ""
    for p in pages:
        items += (
            '    <div class="card">\n'
            '      <h3><a href="' + p["url"] + '" target="_blank">' + p["title"] + "</a></h3>\n"
            '      <p class="meta">ID: ' + p["id"] + " | Space: " + p.get("space", "") + " | 수정: " + p.get("lastModified", "") + "</p>\n"
            '      <p><a href="page-' + p["id"] + '-structure.json">ADF JSON</a> | '
            '<a href="page-' + p["id"] + '-content.md">Markdown</a></p>\n'
            "    </div>\n"
        )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="ko">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        "<title>" + task_name + " - Confluence 원본</title>\n"
        "<style>\n"
        "body{font-family:'Malgun Gothic',sans-serif;margin:20px;background:#f0f4f8}\n"
        "h1{color:#0052CC;border-bottom:3px solid #0052CC;padding-bottom:8px}\n"
        ".card{background:#fff;border:1px solid #dde1e7;border-radius:8px;padding:16px;margin:12px 0;"
        "box-shadow:0 2px 4px rgba(0,0,0,.08)}\n"
        ".card h3{margin:0 0 6px;color:#172B4D}\n"
        ".card h3 a{color:#0052CC;text-decoration:none}\n"
        ".meta{font-size:.82em;color:#6B778C;margin:4px 0}\n"
        ".card p a{color:#0065FF;font-size:.9em}\n"
        ".summary{background:#DEEBFF;border-left:4px solid #0052CC;padding:10px 16px;"
        "margin:16px 0;border-radius:0 6px 6px 0}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>" + task_name + " - Confluence 원본 구조 수집</h1>\n"
        '<div class="summary">\n'
        "  수집일: 2026-04-04 | 총 " + str(len(pages)) + "개 페이지 | cloudId: aa39af27-f906-4c9b-ae6a-774072aac35d\n"
        "</div>\n"
        + items
        + "</body>\n</html>"
    )


def main():
    print("저장 시작")
    for task_key, pages in TASKS.items():
        folder = os.path.join(BASE_DIR, task_key)
        img_folder = os.path.join(folder, "images")
        os.makedirs(folder, exist_ok=True)
        os.makedirs(img_folder, exist_ok=True)

        all_media = []
        pages_meta = []

        for p in pages:
            pid = p["id"]

            adf_node = read_adf_from_temp(pid)
            source = "temp_file"
            if adf_node is None:
                adf_node = make_stub_adf(p)
                source = "stub"

            adf_path = os.path.join(folder, "page-" + pid + "-structure.json")
            with open(adf_path, "w", encoding="utf-8") as f:
                json.dump(adf_node, f, ensure_ascii=False, indent=2)

            media = extract_media(adf_node)
            for m in media:
                m["pageId"] = pid
                m["pageTitle"] = p["title"]
                all_media.append(m)

            md_path = os.path.join(folder, "page-" + pid + "-content.md")
            if not os.path.exists(md_path):
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("# " + p["title"] + "\n\n(Markdown 원문 저장 예정)\n")

            pages_meta.append({
                "id": pid,
                "title": p["title"],
                "space": p.get("space", ""),
                "url": p.get("url", ""),
                "lastModified": p.get("lastModified", ""),
                "adfFile": "page-" + pid + "-structure.json",
                "adfSource": source,
                "mdFile": "page-" + pid + "-content.md",
                "mediaCount": len(media),
            })
            print("  " + pid + ": adf=" + source + ", media=" + str(len(media)))

        with open(os.path.join(folder, "pages.json"), "w", encoding="utf-8") as f:
            json.dump({
                "task": task_key,
                "cloudId": "aa39af27-f906-4c9b-ae6a-774072aac35d",
                "collectedAt": "2026-04-04",
                "totalPages": len(pages_meta),
                "pages": pages_meta,
            }, f, ensure_ascii=False, indent=2)

        with open(os.path.join(img_folder, "reference.json"), "w", encoding="utf-8") as f:
            json.dump({
                "task": task_key,
                "totalMedia": len(all_media),
                "media": all_media,
            }, f, ensure_ascii=False, indent=2)

        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(make_index_html(task_key, pages))

        print("[" + task_key + "] 완료: " + str(len(pages_meta)) + "페이지, 미디어 " + str(len(all_media)) + "개")

    print("전체 완료")


if __name__ == "__main__":
    main()
