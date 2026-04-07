"""소결취출기 비전티칭 매뉴얼 검색"""
import sys, os, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# DB 접속
sys.path.insert(0, 'C:/MES/wta-agents/workspaces/db-manager')
import importlib.util
spec = importlib.util.spec_from_file_location("dbq", "C:/MES/wta-agents/workspaces/db-manager/db-query.py")

import psycopg2

def get_conn():
    env_path = "C:/MES/backend/.env"
    password = None
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                password = line.strip().split("=",1)[1]
    return psycopg2.connect(
        host="localhost", port=55432,
        user="postgres", dbname="postgres",
        password=password
    )

# 임베딩 생성
query = "소결취출기 비전티칭 vision teaching 카메라 보정 캘리브레이션"
print(f"검색 쿼리: {query}")
resp = requests.post('http://182.224.6.147:11434/api/embed',
    json={'model': 'qwen3-embedding:8b', 'input': query},
    timeout=60)
emb = resp.json()['embeddings'][0][:2000]
emb_str = '[' + ','.join(str(x) for x in emb) + ']'
print("임베딩 완료\n")

conn = get_conn()
cur = conn.cursor()

# 1. wta_documents 검색
print("=== manual.wta_documents 검색 ===")
cur.execute("""
SELECT source_file, category, chunk_index, content,
       1 - (embedding <=> %s::vector) AS similarity
FROM manual.wta_documents
ORDER BY embedding <=> %s::vector
LIMIT 8
""", (emb_str, emb_str))
for r in cur.fetchall():
    print(f"[{r[4]:.4f}] {r[0]} | {r[1]} | chunk:{r[2]}")
    print(f"  {r[3][:300]}")
    print()

# 2. manual.documents 검색 (부품 매뉴얼)
print("=== manual.documents 검색 ===")
cur.execute("""
SELECT source_file, category, chunk_index, page_number, content,
       1 - (embedding <=> %s::vector) AS similarity
FROM manual.documents
ORDER BY embedding <=> %s::vector
LIMIT 5
""", (emb_str, emb_str))
for r in cur.fetchall():
    print(f"[{r[5]:.4f}] {r[0]} | {r[1]} | chunk:{r[2]} | p.{r[3]}")
    print(f"  {r[4][:300]}")
    print()

# 3. 키워드 전문 검색 (wta_documents)
print("=== 키워드 전문검색 (소결취출기 OR 비전티칭) ===")
cur.execute("""
SELECT source_file, category, chunk_index, content
FROM manual.wta_documents
WHERE content ILIKE '%소결취출기%' OR content ILIKE '%비전티칭%'
   OR content ILIKE '%vision teaching%' OR content ILIKE '%비전 티칭%'
LIMIT 10
""")
rows = cur.fetchall()
print(f"키워드 매치: {len(rows)}건")
for r in rows:
    print(f"  {r[0]} | {r[1]} | chunk:{r[2]}")
    print(f"  {r[3][:300]}")
    print()

cur.close()
conn.close()
