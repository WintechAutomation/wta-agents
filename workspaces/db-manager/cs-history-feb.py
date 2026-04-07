"""2026년 2월 CS 이력 조회"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2

conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
    password='your-super-secret-and-long-postgres-password', dbname='postgres')
cur = conn.cursor()

# 전체 건수 먼저
cur.execute("""
SELECT COUNT(*) FROM csagent.cs_history
WHERE cs_received_at >= '2026-02-01' AND cs_received_at < '2026-03-01'
""")
total = cur.fetchone()[0]
print(f"2026년 2월 CS 이력 총 {total}건\n")

# 상위 30건 조회
cur.execute("""
SELECT
    h.id,
    u.customer_name,
    m.model_name,
    h.title,
    h.cs_received_at::date AS received_date,
    h.cs_handler
FROM csagent.cs_history h
LEFT JOIN csagent.equipment_units u ON u.id = h.shipment_id
LEFT JOIN csagent.equipment_models m ON m.id = u.model_id
WHERE h.cs_received_at >= '2026-02-01' AND h.cs_received_at < '2026-03-01'
ORDER BY h.cs_received_at
LIMIT 30
""")
rows = cur.fetchall()
print(f"{'ID':>5}  {'수신일':<12}  {'고객사':<20}  {'장비':<20}  {'증상(제목)':<40}  담당자")
print("-" * 130)
for r in rows:
    cid, customer, model, title, date, handler = r
    customer = customer or '-'
    model = model or '-'
    title = (title or '')[:38]
    handler = (handler or '-').split('(')[0].strip()
    print(f"{cid:>5}  {str(date):<12}  {customer:<20}  {model:<20}  {title:<40}  {handler}")

conn.close()
