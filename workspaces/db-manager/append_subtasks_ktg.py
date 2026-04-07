import requests

# .env에서 인증 정보 읽기
env = {}
with open('C:/MES/backend/.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

BASE = 'http://localhost:8100'

# 로그인
token_resp = requests.post(f'{BASE}/api/auth/login', json={
    'username': env['MES_SERVICE_USERNAME'],
    'password': env['MES_SERVICE_PASSWORD']
})
token = token_resp.json()['data']['access']
headers = {'Authorization': f'Bearer {token}'}

TASK_ID = 5287
PROJECT_ID = 87

# 추가할 서브태스크 목록 (order는 기존 1 다음부터)
subtasks = [
    {'task_item_name': '프로젝트생성', 'notes': '공유폴더생성', 'order': 2},
    {'task_item_name': '서류정리',    'notes': '사양서, IO맵 등', 'order': 3},
    {'task_item_name': 'CAD 전장배치도', 'notes': None, 'order': 4},
    {'task_item_name': 'EPLAN (전장도면)', 'notes': None, 'order': 5},
    {'task_item_name': 'EPLAN (HARNESS)', 'notes': None, 'order': 6},
    {'task_item_name': 'EPLAN (BOM정리)', 'notes': None, 'order': 7},
]

results = []
for s in subtasks:
    payload = {
        'task_id': TASK_ID,
        'project_id': PROJECT_ID,
        'task_item_code': '',
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
    results.append({'name': s['task_item_name'], 'id': subtask_id, 'notes': s['notes'], 'status': resp.status_code})
    print(f"[{resp.status_code}] {s['task_item_name']} → id={subtask_id}")

# notes가 있는 항목은 DB 직접 UPDATE
import psycopg2

db_env = env
conn = psycopg2.connect(
    host='localhost',
    port=55432,
    dbname=db_env.get('DB_NAME', 'postgres'),
    user=db_env.get('DB_USER', 'postgres'),
    password=db_env.get('DB_PASSWORD', ''),
)
cur = conn.cursor()
for r in results:
    if r['notes'] and r['id']:
        cur.execute(
            "UPDATE api_projectsubtask SET notes = %s WHERE id = %s",
            (r['notes'], r['id'])
        )
        print(f"  notes 업데이트: id={r['id']} → {r['notes']}")
conn.commit()
cur.close()
conn.close()

print("\n완료:")
for r in results:
    print(f"  id={r['id']} | {r['name']} | notes={r['notes']}")
