import json, sys
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
conn = psycopg2.connect(
    host='localhost', port=55432,
    user='postgres',
    password='your-super-secret-and-long-postgres-password',
    dbname='postgres'
)

# 1. Check cs_history columns
with conn.cursor() as cur:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema='csagent' AND table_name='cs_history'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    print("cs_history columns:")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")

print()

# 2. Check cs_attachments table  
with conn.cursor() as cur:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema='csagent' AND table_name='cs_attachments'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    if cols:
        print("cs_attachments columns:")
        for c in cols:
            print(f"  {c[0]}: {c[1]}")
        
        # Sample data
        cur.execute("SELECT cs_id, file_name, file_type, file_url FROM csagent.cs_attachments LIMIT 5")
        rows = cur.fetchall()
        print("Sample cs_attachments:")
        for r in rows:
            print(f"  cs_id={r[0]}, name={r[1]}, type={r[2]}, url={str(r[3])[:60]}")
    else:
        print("cs_attachments table not found")

conn.close()
