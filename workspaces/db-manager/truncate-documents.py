"""manual.documents 테이블 초기화 (부서장 승인 완료)"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import psycopg2

conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
    password='your-super-secret-and-long-postgres-password', dbname='postgres')
conn.autocommit = False
cur = conn.cursor()

# 초기화 전 건수 확인
cur.execute("SELECT COUNT(*) FROM manual.documents")
before = cur.fetchone()[0]
print(f"초기화 전: {before:,}건")

# manual.wta_documents, csagent.vector_embeddings 건수 확인 (건드리지 않음)
cur.execute("SELECT COUNT(*) FROM manual.wta_documents")
wta = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM csagent.vector_embeddings")
cs = cur.fetchone()[0]
print(f"manual.wta_documents (유지): {wta:,}건")
print(f"csagent.vector_embeddings (유지): {cs:,}건")

# TRUNCATE 실행
print("\nTRUNCATE TABLE manual.documents 실행 중...")
cur.execute("TRUNCATE TABLE manual.documents")
conn.commit()
print("완료")

# 초기화 후 건수 확인
cur.execute("SELECT COUNT(*) FROM manual.documents")
after = cur.fetchone()[0]
print(f"\n초기화 후: {after:,}건")

# 다른 테이블 건수 재확인 (변동 없어야 함)
cur.execute("SELECT COUNT(*) FROM manual.wta_documents")
wta2 = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM csagent.vector_embeddings")
cs2 = cur.fetchone()[0]
print(f"manual.wta_documents (확인): {wta2:,}건")
print(f"csagent.vector_embeddings (확인): {cs2:,}건")

conn.close()
print("\n=== 완료 ===")
