# -*- coding: utf-8 -*-
"""
Supabase Storage API로 실패한 파일 직접 다운로드 (projects/ 경로)
"""
import sys, json, os, requests, importlib.util
sys.stdout.reconfigure(encoding='utf-8')

SUPABASE_URL = 'http://localhost:8000'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjIzNTQ4MDAsImV4cCI6MTkyMDEyMTIwMH0.WJx7hKyaTu0Gat_SRpccnFZAME7QZDMueA_K6-yco1U'
HEADERS = {'Authorization': f'Bearer {SERVICE_KEY}', 'apikey': SERVICE_KEY}
BASE_DIR = 'C:/MES/wta-agents/data/tech'

spec = importlib.util.spec_from_file_location('dbq', 'C:/MES/wta-agents/workspaces/db-manager/db-query.py')
dq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dq)

with open('C:/MES/wta-agents/data/tech/file-manifest.json', encoding='utf-8') as f:
    manifest = json.load(f)

failed_ids = [f['id'] for f in manifest['files'] if 'error' in f]
ids_clause = ','.join([repr(i) for i in failed_ids])
r = dq.query_mes(f'SELECT id, project_id, category, original_filename, safe_filename, file_path, file_size FROM project_technical_files WHERE id IN ({ids_clause})')
cols = r['columns']
records = [dict(zip(cols, row)) for row in r['rows']]

supabase_records = [rec for rec in records if rec['file_path'].startswith('projects/')]
print(f'Supabase Storage 다운로드 대상: {len(supabase_records)}건')

success, fail = 0, 0
recovered = []

for i, rec in enumerate(supabase_records, 1):
    storage_path = rec['file_path']  # projects/{id}/category/filename
    save_dir = os.path.join(BASE_DIR, str(rec['project_id']), rec['category'])
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, rec['original_filename'])
    if os.path.exists(save_path):
        base, ext = os.path.splitext(rec['original_filename'])
        save_path = os.path.join(save_dir, f"{base}_{rec['id'][:8]}{ext}")

    url = f"{SUPABASE_URL}/storage/v1/object/technical/{storage_path}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        resp.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size = os.path.getsize(save_path)
        recovered.append({
            'id': rec['id'],
            'project_id': rec['project_id'],
            'category': rec['category'],
            'original_filename': rec['original_filename'],
            'saved_path': save_path.replace(BASE_DIR + '/', ''),
            'actual_size': size,
            'source': 'supabase_direct',
        })
        success += 1
    except Exception as e:
        print(f'  [실패] {rec["original_filename"]}: {e}')
        fail += 1

print(f'\nSupabase 직접 다운로드: {success}건 성공, {fail}건 실패')

# manifest 업데이트
recovered_map = {r['id']: r for r in recovered}
updated = []
for f in manifest['files']:
    if f['id'] in recovered_map:
        updated.append(recovered_map[f['id']])
    else:
        updated.append(f)

remaining_errors = len([f for f in updated if 'error' in f])
manifest['success'] = manifest.get('success', 0) + success
manifest['fail'] = remaining_errors
manifest['files'] = updated

with open('C:/MES/wta-agents/data/tech/file-manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
print(f'manifest 업데이트 완료 (잔여 실패: {remaining_errors}건)')
