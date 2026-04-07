import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
conn = psycopg2.connect(
    host='localhost', port=55432,
    user='postgres',
    password='your-super-secret-and-long-postgres-password',
    dbname='postgres'
)

# PVD 전체 CS 이력 + attachment_urls + cs_attachments
with conn.cursor() as cur:
    cur.execute("""
        SELECT 
            h.id, h.title, h.symptom_and_cause, h.action_result,
            h.cs_received_at, h.cs_completed_at,
            s.project_name, s.customer, s.serial_no,
            h.attachment_urls, h.result_attachment_urls,
            COALESCE(
                json_agg(
                    json_build_object(
                        'id', a.id,
                        'filename', a.filename,
                        'storage_url', a.storage_url,
                        'mime', a.mime
                    )
                ) FILTER (WHERE a.id IS NOT NULL),
                '[]'::json
            ) AS attachments
        FROM csagent.cs_history h
        JOIN public.shipment_table s ON s.id = h.shipment_id
        LEFT JOIN csagent.cs_attachments a ON a.cs_history_id = h.id
        WHERE s.project_name ILIKE '%pvd%'
        GROUP BY h.id, s.project_name, s.customer, s.serial_no
        ORDER BY h.id
    """)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    data = [dict(zip(cols, r)) for r in rows]

conn.close()

# Convert non-serializable types
for r in data:
    for k, v in r.items():
        if hasattr(v, 'isoformat'):
            r[k] = v.isoformat()
        elif isinstance(v, (bytes, bytearray)):
            r[k] = v.decode('utf-8', errors='replace')

# Check attachment stats
has_att = [r for r in data if r.get('attachment_urls') or (r.get('attachments') and r['attachments'] != '[]')]
print(f"총 PVD CS: {len(data)}건")
print(f"attachment_urls 있는 건: {sum(1 for r in data if r.get('attachment_urls'))}")
print(f"cs_attachments 있는 건: {sum(1 for r in data if r.get('attachments') and str(r['attachments']) not in ['[]', 'null', None])}")

# Sample attachment data
cnt = 0
for r in data:
    att = r.get('attachments')
    if att and str(att) not in ['[]', 'null', None] and att != [] :
        print(f"\nid={r['id']} title={r['title'][:40]}")
        print(f"  attachments sample: {str(att)[:200]}")
        cnt += 1
        if cnt >= 5:
            break

# Save
out_path = 'C:/MES/wta-agents/workspaces/cs-agent/pvd_cs_full.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, default=str)
print(f"\nSaved {len(data)} records to pvd_cs_full.json")
