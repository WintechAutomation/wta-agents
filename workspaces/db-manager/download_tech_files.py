# -*- coding: utf-8 -*-
"""
Supabase Storage technical 버킷 기술파일 다운로드 스크립트
저장 경로: C:\MES\wta-agents\data\tech\
"""
import sys, os, json, time, importlib.util
import requests

sys.stdout.reconfigure(encoding='utf-8')

# db-query 모듈 로드
spec = importlib.util.spec_from_file_location('dbq', 'C:/MES/wta-agents/workspaces/db-manager/db-query.py')
dq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dq)

BASE_DIR = 'C:/MES/wta-agents/data/tech'
MES_BASE = 'http://localhost:8100'

# MES 로그인
def get_token():
    env_path = 'C:/MES/backend/.env'
    username, password = 'max', None
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('MES_SERVICE_PASSWORD='):
                password = line.strip().split('=', 1)[1]
    resp = requests.post(f'{MES_BASE}/api/auth/login', json={'username': username, 'password': password}, timeout=10)
    resp.raise_for_status()
    return resp.json()['data']['access']

# DB에서 전체 파일 목록 조회
def fetch_records():
    r = dq.query_mes('''
        SELECT f.id, f.project_id, f.category, f.original_filename, f.safe_filename,
               f.file_path, f.file_size, f.file_extension, f.version, f.description,
               f.uploaded_at, f.updated_at, p.project_code, p.name as project_name
        FROM project_technical_files f
        JOIN api_project p ON p.id = f.project_id
        WHERE f.is_active = true
        ORDER BY f.project_id, f.category, f.id
    ''')
    cols = r['columns']
    return [dict(zip(cols, row)) for row in r['rows']]

def main():
    print('=== 기술파일 다운로드 시작 ===')
    print(f'저장 경로: {BASE_DIR}')

    # 1. 레코드 조회
    print('\n[1/4] DB 레코드 조회 중...')
    records = fetch_records()
    print(f'  총 {len(records)}건')

    # db-records.json 저장
    db_records_path = os.path.join(BASE_DIR, 'db-records.json')
    with open(db_records_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)
    print(f'  DB 레코드 저장: {db_records_path}')

    # 2. 토큰 발급
    print('\n[2/4] MES API 인증 중...')
    token = get_token()
    headers = {'Authorization': f'Bearer {token}'}
    print('  인증 완료')

    # 3. 파일 다운로드
    print('\n[3/4] 파일 다운로드 중...')
    manifest = []
    success, fail = 0, 0

    for i, rec in enumerate(records, 1):
        project_id = rec['project_id']
        category = rec['category']
        file_id = rec['id']
        original_filename = rec['original_filename']

        # 저장 경로: data/tech/{project_id}/{category}/{파일명}
        save_dir = os.path.join(BASE_DIR, str(project_id), category)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, original_filename)

        # 동일 파일명 중복 처리
        if os.path.exists(save_path):
            base, ext = os.path.splitext(original_filename)
            save_path = os.path.join(save_dir, f'{base}_{file_id[:8]}{ext}')

        url = f'{MES_BASE}/api/production/projects/{project_id}/technical-files/{file_id}/download'

        try:
            resp = requests.get(url, headers=headers, timeout=60, stream=True)
            resp.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            actual_size = os.path.getsize(save_path)
            manifest.append({
                'id': file_id,
                'project_id': project_id,
                'project_code': rec['project_code'],
                'project_name': rec['project_name'],
                'category': category,
                'original_filename': original_filename,
                'saved_path': save_path.replace('C:/MES/wta-agents/data/tech/', ''),
                'file_size': rec['file_size'],
                'actual_size': actual_size,
                'file_extension': rec['file_extension'],
                'version': rec['version'],
                'description': rec['description'],
                'uploaded_at': rec['uploaded_at'],
            })
            success += 1
            if i % 20 == 0 or i == len(records):
                print(f'  진행: {i}/{len(records)} ({success}성공, {fail}실패)')

        except Exception as e:
            print(f'  [실패] {project_id}/{category}/{original_filename}: {e}')
            manifest.append({
                'id': file_id,
                'project_id': project_id,
                'project_code': rec['project_code'],
                'category': category,
                'original_filename': original_filename,
                'error': str(e),
            })
            fail += 1

    # 4. manifest 저장
    print('\n[4/4] 매핑 정보 저장 중...')
    manifest_path = os.path.join(BASE_DIR, 'file-manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S KST'),
            'total': len(records),
            'success': success,
            'fail': fail,
            'files': manifest,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f'  manifest 저장: {manifest_path}')

    print(f'\n=== 완료: {success}건 성공, {fail}건 실패 ===')
    return success, fail

if __name__ == '__main__':
    main()
