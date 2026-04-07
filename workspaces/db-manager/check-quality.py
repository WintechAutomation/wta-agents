import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2

conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
    password='your-super-secret-and-long-postgres-password', dbname='postgres')
cur = conn.cursor()

print("=== #235, #236 문서 내용 ===")
cur.execute("SELECT id, source_file, category, content FROM manual.wta_documents WHERE id IN (235, 236)")
for r in cur.fetchall():
    print(f"ID: {r[0]}, file: {r[1]}, cat: {r[2]}")
    print(f"content({len(r[3])}자): {r[3]!r}")
    print("---")

print("\n=== 청크 길이 분포 ===")
cur.execute("""
SELECT
  CASE
    WHEN LENGTH(content) < 20 THEN '< 20자'
    WHEN LENGTH(content) < 50 THEN '20~50자'
    WHEN LENGTH(content) < 100 THEN '50~100자'
    WHEN LENGTH(content) < 200 THEN '100~200자'
    ELSE '200자 이상'
  END as len_range,
  COUNT(*) as cnt
FROM manual.wta_documents
GROUP BY 1 ORDER BY MIN(LENGTH(content))
""")
total = 0
rows = cur.fetchall()
cur.execute("SELECT COUNT(*) FROM manual.wta_documents")
total = cur.fetchone()[0]
for row in rows:
    print(f"  {row[0]}: {row[1]}건 ({round(row[1]*100/total,1)}%)")

print(f"\n전체: {total}건")

print("\n=== velocity 포함 문서 ===")
cur.execute("SELECT COUNT(*) FROM manual.wta_documents WHERE content ILIKE '%velocity%'")
print(f"velocity 포함: {cur.fetchone()[0]}건")

print("\n=== 짧은 청크 샘플 (< 20자) ===")
cur.execute("SELECT id, source_file, content FROM manual.wta_documents WHERE LENGTH(content) < 20 LIMIT 10")
for r in cur.fetchall():
    print(f"  ID:{r[0]} [{r[1]}] content={r[2]!r}")

conn.close()
