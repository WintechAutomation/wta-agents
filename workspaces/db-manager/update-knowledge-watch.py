"""update-knowledge-watch.py — wta-docling-all.log를 감시하여 카테고리 완료 시 knowledge.json 갱신."""
import json
import os
import re
import time
import psycopg2
from datetime import datetime, timezone, timedelta

LOG_PATH = r"C:\MES\wta-agents\logs\wta-docling-all.log"
KNOWLEDGE_PATH = r"C:\MES\wta-agents\config\knowledge.json"
WTA_TOTAL = 572

DB_CONFIG = {
    "host": "localhost", "port": 55432, "user": "postgres",
    "password": "your-super-secret-and-long-postgres-password", "dbname": "postgres",
}

KST = timezone(timedelta(hours=9))

def get_embedded_count():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT source_file) FROM manual.wta_documents")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"[watch] DB 조회 실패: {e}")
        return None

def update_knowledge(embedded):
    try:
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
        data["updated_at"] = now_str

        for cat in data.get("categories", []):
            if cat.get("id") == "cs-rag":
                for item in cat.get("items", []):
                    if item.get("label") == "WTA 매뉴얼":
                        status = "done" if embedded >= WTA_TOTAL else "in_progress"
                        item["parsed"] = embedded
                        item["embedded"] = embedded
                        item["total"] = WTA_TOTAL
                        item["status"] = status
                        break
                break

        with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[watch] {now_str} — knowledge.json 갱신: {embedded}/{WTA_TOTAL}")
    except Exception as e:
        print(f"[watch] knowledge.json 갱신 실패: {e}")

def watch():
    print(f"[watch] 로그 감시 시작: {LOG_PATH}")
    last_size = 0
    last_embedded = 0
    last_category_done = ""

    # 종료 패턴: "[N/18] OK CategoryName"
    cat_done_pat = re.compile(r"\[(\d+)/18\] OK (\w+)")

    while True:
        try:
            size = os.path.getsize(LOG_PATH)
        except FileNotFoundError:
            time.sleep(5)
            continue

        if size > last_size:
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            last_size = size

            # 새로 완료된 카테고리 탐색
            matches = cat_done_pat.findall(content)
            if matches:
                last_match = matches[-1]
                cat_name = last_match[1]
                if cat_name != last_category_done:
                    last_category_done = cat_name
                    embedded = get_embedded_count()
                    if embedded and embedded != last_embedded:
                        last_embedded = embedded
                        update_knowledge(embedded)

            # 전체 완료 감지
            if "wta-docling-all] All done" in content:
                embedded = get_embedded_count()
                if embedded:
                    update_knowledge(embedded)
                print("[watch] 전체 완료 — 감시 종료")
                break

        time.sleep(10)

if __name__ == "__main__":
    watch()
