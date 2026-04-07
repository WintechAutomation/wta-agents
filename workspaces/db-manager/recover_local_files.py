# -*- coding: utf-8 -*-
"""
로컬 파일 시스템(D:/wMES_FILES)에서 실패한 기술파일 복구
"""
import sys, json, os, shutil, importlib.util
sys.stdout.reconfigure(encoding='utf-8')

spec = importlib.util.spec_from_file_location('dbq', 'C:/MES/wta-agents/workspaces/db-manager/db-query.py')
dq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dq)

with open('C:/MES/wta-agents/data/tech/file-manifest.json', encoding='utf-8') as f:
    manifest = json.load(f)

failed_ids = [f['id'] for f in manifest['files'] if 'error' in f]
print(f'실패 파일 수: {len(failed_ids)}')

ids_clause = ','.join([f"'{i}'" for i in failed_ids])
r = dq.query_mes(f"SELECT id, project_id, category, original_filename, safe_filename, file_path, file_size FROM project_technical_files WHERE id IN ({ids_clause})")
cols = r['columns']
records = [dict(zip(cols, row)) for row in r['rows']]

BASE_DIR = 'C:/MES/wta-agents/data/tech'
success, fail = 0, 0
recovered = []
not_found = []

for rec in records:
    fp = rec['file_path']
    # D:\wMES_FILES\... 형태를 Unix 경로로 변환
    local_path = fp.replace('D:', '/d').replace('\\', '/')

    save_dir = os.path.join(BASE_DIR, str(rec['project_id']), rec['category'])
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, rec['original_filename'])

    if os.path.exists(save_path):
        base, ext = os.path.splitext(rec['original_filename'])
        save_path = os.path.join(save_dir, f"{base}_{rec['id'][:8]}{ext}")

    if os.path.exists(local_path):
        try:
            shutil.copy2(local_path, save_path)
            size = os.path.getsize(save_path)
            recovered.append({
                'id': rec['id'],
                'project_id': rec['project_id'],
                'category': rec['category'],
                'original_filename': rec['original_filename'],
                'saved_path': save_path.replace(BASE_DIR + '/', ''),
                'actual_size': size,
                'source': 'local',
            })
            success += 1
        except Exception as e:
            print(f'  [복사 실패] {local_path}: {e}')
            fail += 1
    else:
        not_found.append({'id': rec['id'], 'path': local_path, 'filename': rec['original_filename']})
        fail += 1

print(f'\n복구 완료: {success}건 성공, {fail}건 실패')
if not_found:
    print(f'\n파일 없음 {len(not_found)}건:')
    for nf in not_found[:5]:
        print(f'  {nf["filename"]}: {nf["path"]}')

# manifest 업데이트: 실패 항목을 성공으로 교체
manifest_files = manifest['files']
recovered_map = {r['id']: r for r in recovered}

updated = []
for f in manifest_files:
    if f['id'] in recovered_map:
        updated.append(recovered_map[f['id']])
    else:
        updated.append(f)

manifest['success'] = manifest.get('success', 0) + success
manifest['fail'] = len([f for f in updated if 'error' in f])
manifest['files'] = updated

with open('C:/MES/wta-agents/data/tech/file-manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
print('\nmanifest 업데이트 완료')
