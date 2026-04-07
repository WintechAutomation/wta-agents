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

conn = psycopg2.connect(host='localhost', port=55432,
    dbname=env.get('DB_NAME','postgres'),
    user=env.get('DB_USER','postgres'),
    password=env.get('DB_PASSWORD',''))
cur = conn.cursor()

# ■ 1. 대구텍 F2 (task_id=5287) — 역순으로 코드 업데이트
print("=== 대구텍 F2 작업코드 재배번 (역순) ===")
himf2_updates = [
    (1950, 'CD-HIMF2-007'),
    (1949, 'CD-HIMF2-006'),
    (1948, 'CD-HIMF2-005'),
    (1947, 'CD-HIMF2-004'),
    (1946, 'CD-HIMF2-003'),
    (1945, 'CD-HIMF2-002'),
]
for sid, new_code in himf2_updates:
    cur.execute('UPDATE api_projectsubtask SET task_item_code = %s WHERE id = %s', (new_code, sid))
    print(f'  id={sid} → {new_code}')
conn.commit()

# 신규 추가 — order=1
resp = requests.post(
    f'{BASE}/api/production/project-detailed-schedules/append_subtask',
    headers=headers,
    json={
        'task_id': 5287,
        'project_id': 87,
        'task_item_code': 'CD-HIMF2-001',
        'task_item_name': '사양서확인',
        'estimated_hours': 0,
        'priority': 'medium',
        'status': 'pending',
        'order': 1,
    }
)
new_id_himf2 = resp.json().get('data', {}).get('subtask_id')
print(f'  신규 id={new_id_himf2} 사양서확인 (CD-HIMF2-001, order=1)')
cur.execute("UPDATE api_projectsubtask SET notes = %s WHERE id = %s",
            ('전장비 비교 및 특이사항 확인', new_id_himf2))
conn.commit()


# ■ 2. 한국야금 CVD (task_id=4143) — 역순으로 코드+order 업데이트
print("\n=== 한국야금 CVD 작업코드 재배번 (역순) ===")
cvd_updates = [
    (1956, 'CD-HS1HOR-007', 7),
    (1955, 'CD-HS1HOR-006', 6),
    (1954, 'CD-HS1HOR-005', 5),
    (1953, 'CD-HS1HOR-004', 4),
    (1952, 'CD-HS1HOR-003', 3),
    (1951, 'CD-HS1HOR-002', 2),
]
for sid, new_code, new_order in cvd_updates:
    cur.execute('UPDATE api_projectsubtask SET task_item_code = %s, "order" = %s WHERE id = %s',
                (new_code, new_order, sid))
    print(f'  id={sid} → {new_code}, order={new_order}')
conn.commit()

# 신규 추가 — order=1, 담당자 김준형(user_id=22)
resp = requests.post(
    f'{BASE}/api/production/project-detailed-schedules/append_subtask',
    headers=headers,
    json={
        'task_id': 4143,
        'project_id': 88,
        'task_item_code': 'CD-HS1HOR-001',
        'task_item_name': '사양서확인',
        'estimated_hours': 0,
        'priority': 'medium',
        'status': 'pending',
        'order': 1,
        'assigned_to_id': 22,
    }
)
new_id_cvd = resp.json().get('data', {}).get('subtask_id')
print(f'  신규 id={new_id_cvd} 사양서확인 (CD-HS1HOR-001, order=1, 담당자=김준형)')
cur.execute("UPDATE api_projectsubtask SET notes = %s WHERE id = %s",
            ('전장비 비교 및 특이사항 확인', new_id_cvd))
conn.commit()

cur.close()
conn.close()
print(f"\n완료: 대구텍 신규id={new_id_himf2}, CVD 신규id={new_id_cvd}")
