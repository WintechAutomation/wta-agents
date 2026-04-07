"""벡터 DB 전체 데이터 품질 종합 점검"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, re

conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
    password='your-super-secret-and-long-postgres-password', dbname='postgres')
cur = conn.cursor()

print("=" * 70)
print("1. manual.wta_documents 품질 점검")
print("=" * 70)

cur.execute("SELECT COUNT(*) FROM manual.wta_documents")
total_wta = cur.fetchone()[0]
print(f"전체: {total_wta:,}건")

# 짧은 청크
for threshold in [20, 50, 100]:
    cur.execute(f"SELECT COUNT(*) FROM manual.wta_documents WHERE LENGTH(content) < {threshold}")
    n = cur.fetchone()[0]
    print(f"  < {threshold}자: {n:,}건 ({n*100/total_wta:.1f}%)")

# 의미없는 청크 (공백+특수문자+숫자만)
cur.execute("SELECT COUNT(*) FROM manual.wta_documents WHERE content ~ '^[\\s\\d\\W]+$'")
meaningless = cur.fetchone()[0]
print(f"  의미없는 텍스트: {meaningless:,}건 ({meaningless*100/total_wta:.1f}%)")

# 빈 표 청크 (| --- | 패턴)
cur.execute("SELECT COUNT(*) FROM manual.wta_documents WHERE content ~ '^\\s*\\|[\\s\\-|]+\\|\\s*$'")
empty_table = cur.fetchone()[0]
print(f"  빈 표 청크: {empty_table:,}건 ({empty_table*100/total_wta:.1f}%)")

# 카테고리별 분포
print("\n카테고리별 분포:")
cur.execute("""
    SELECT COALESCE(NULLIF(category,''), '(없음)') as cat,
           COUNT(*) as cnt,
           ROUND(AVG(LENGTH(content))) as avg_len
    FROM manual.wta_documents
    GROUP BY category ORDER BY cnt DESC LIMIT 15
""")
for r in cur.fetchall():
    print(f"  {r[0]:<30} {r[1]:>7,}건  평균 {r[2]}자")

# velocity 검색
print("\nvelocity 텍스트 검색:")
cur.execute("SELECT id, source_file, category, LEFT(content,100) FROM manual.wta_documents WHERE content ILIKE '%velocity%' LIMIT 5")
for r in cur.fetchall():
    print(f"  ID:{r[0]} [{r[2]}] {r[1]} → {r[3]!r}")

print()
print("=" * 70)
print("2. manual.documents 품질 점검")
print("=" * 70)

cur.execute("SELECT COUNT(*) FROM manual.documents")
total_doc = cur.fetchone()[0]
print(f"전체: {total_doc:,}건")

for threshold in [20, 50, 100]:
    cur.execute(f"SELECT COUNT(*) FROM manual.documents WHERE LENGTH(content) < {threshold}")
    n = cur.fetchone()[0]
    print(f"  < {threshold}자: {n:,}건 ({n*100/total_doc:.1f}%)")

cur.execute("SELECT COUNT(*) FROM manual.documents WHERE content ~ '^[\\s\\d\\W]+$'")
meaningless = cur.fetchone()[0]
print(f"  의미없는 텍스트: {meaningless:,}건 ({meaningless*100/total_doc:.1f}%)")

cur.execute("SELECT COUNT(*) FROM manual.documents WHERE content LIKE '%cid:%'")
cid = cur.fetchone()[0]
print(f"  CID 깨진 청크: {cid:,}건 ({cid*100/total_doc:.1f}%)")

print("\n카테고리별 분포:")
cur.execute("""
    SELECT COALESCE(NULLIF(category,''), '(없음)') as cat,
           COUNT(*) as cnt,
           ROUND(AVG(LENGTH(content))) as avg_len
    FROM manual.documents
    GROUP BY category ORDER BY cnt DESC LIMIT 15
""")
for r in cur.fetchall():
    print(f"  {r[0]:<30} {r[1]:>7,}건  평균 {r[2]}자")

# CS 키워드 검색
print("\n'서보 에러코드' 텍스트 검색:")
cur.execute("SELECT id, source_file, category, LEFT(content,120) FROM manual.documents WHERE content ILIKE '%에러코드%' OR content ILIKE '%error code%' LIMIT 5")
for r in cur.fetchall():
    print(f"  ID:{r[0]} [{r[2]}] {r[1]}")
    print(f"    {r[3]!r}")

print("\n'알람 해결' 텍스트 검색:")
cur.execute("SELECT id, source_file, category, LEFT(content,120) FROM manual.documents WHERE content ILIKE '%알람%' OR content ILIKE '%alarm%' LIMIT 5")
for r in cur.fetchall():
    print(f"  ID:{r[0]} [{r[2]}] {r[1]}")
    print(f"    {r[3]!r}")

print()
print("=" * 70)
print("3. csagent.vector_embeddings 품질 점검")
print("=" * 70)

cur.execute("SELECT COUNT(*) FROM csagent.vector_embeddings")
total_cs = cur.fetchone()[0]
print(f"전체: {total_cs:,}건")

cur.execute("SELECT ROUND(AVG(LENGTH(text))) FROM csagent.vector_embeddings")
avg_len = cur.fetchone()[0]
print(f"평균 text 길이: {avg_len}자")

for threshold in [20, 50, 100]:
    cur.execute(f"SELECT COUNT(*) FROM csagent.vector_embeddings WHERE LENGTH(text) < {threshold}")
    n = cur.fetchone()[0]
    print(f"  < {threshold}자: {n:,}건 ({n*100/total_cs:.1f}%)")

print("\nsource_type별 분포:")
cur.execute("""
    SELECT source_type, COUNT(*) as cnt,
           ROUND(AVG(LENGTH(text))) as avg_len
    FROM csagent.vector_embeddings
    GROUP BY source_type ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:<20} {r[1]:>6,}건  평균 {r[2]}자")

print("\n'에러코드' 텍스트 검색:")
cur.execute("SELECT id, source_type, LEFT(text,150) FROM csagent.vector_embeddings WHERE text ILIKE '%에러%' OR text ILIKE '%error%' LIMIT 5")
for r in cur.fetchall():
    print(f"  ID:{r[0]} [{r[1]}]")
    print(f"    {r[2]!r}")

print("\n'알람' 텍스트 검색:")
cur.execute("SELECT id, source_type, LEFT(text,150) FROM csagent.vector_embeddings WHERE text ILIKE '%알람%' OR text ILIKE '%alarm%' LIMIT 5")
for r in cur.fetchall():
    print(f"  ID:{r[0]} [{r[1]}]")
    print(f"    {r[2]!r}")

conn.close()
print("\n=== 점검 완료 ===")
