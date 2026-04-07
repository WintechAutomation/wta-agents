import requests
import psycopg2

env = {}
with open('C:/MES/backend/.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

BASE = 'http://localhost:8100'
token = requests.post(f'{BASE}/api/auth/login', json={
    'username': env['MES_SERVICE_USERNAME'],
    'password': env['MES_SERVICE_PASSWORD']
}).json()['data']['access']
headers = {'Authorization': f'Bearer {token}'}

TASK_ID = 4143
PROJECT_ID = 88

subtasks = [
    {'task_item_name': '프로젝트생성',    'task_item_code': 'CD-HS1HOR-001', 'notes': '공유폴더생성', 'order': 1},
    {'task_item_name': '서류정리',        'task_item_code': 'CD-HS1HOR-002', 'notes': '사양서, IO맵 등', 'order': 2},
    {'task_item_name': 'CAD 전장배치도',  'task_item_code': 'CD-HS1HOR-003', 'notes': None, 'order': 3},
    {'task_item_name': 'EPLAN (전장도면)', 'task_item_code': 'CD-HS1HOR-004', 'notes': None, 'order': 4},
    {'task_item_name': 'EPLAN (HARNESS)', 'task_item_code': 'CD-HS1HOR-005', 'notes': None, 'order': 5},
    {'task_item_name': 'EPLAN (BOM정리)', 'task_item_code': 'CD-HS1HOR-006', 'notes': None, 'order': 6},
]

results = []
for s in subtasks:
    payload = {
        'task_id': TASK_ID,
        'project_id': PROJECT_ID,
        'task_item_code': s['task_item_code'],
        'task_item_name': s['task_item_name'],
        'estimated_hours': 0,
        'priority': 'medium',
        'status': 'pending',
        'order': s['order'],
    }
    resp = requests.post(
        f'{BASE}/api/production/project-detailed-schedules/append_subtask',
        headers=headers,
        json=payload
    )
    data = resp.json()
    subtask_id = data.get('data', {}).get('subtask_id')
    results.append({'name': s['task_item_name'], 'id': subtask_id, 'notes': s['notes']})
    print(f"[{resp.status_code}] {s['task_item_name']} → id={subtask_id}")

# notes 업데이트
conn = psycopg2.connect(host='localhost', port=55432,
    dbname=env.get('DB_NAME','postgres'),
    user=env.get('DB_USER','postgres'),
    password=env.get('DB_PASSWORD',''))
cur = conn.cursor()
for r in results:
    if r['notes'] and r['id']:
        cur.execute("UPDATE api_projectsubtask SET notes = %s WHERE id = %s", (r['notes'], r['id']))
        print(f"  notes: id={r['id']} → {r['notes']}")
conn.commit()
cur.close()
conn.close()

print("\n완료:")
for r in results:
    print(f"  id={r['id']} | {r['name']}")
