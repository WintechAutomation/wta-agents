"""
PTF 파일명 마이그레이션 v2: 해시 파일명 -> 한글 원본 파일명
- DB에서 직접 마이그레이션 대상 조회 (파일경로에 한글 없는 Supabase 파일)
- original_filename != safe_filename 이거나 file_path에 original_filename이 없는 경우
- 신규 파일명: {date}_{time}_{uuid}_{sanitized_original}
- DB: file_path, file_url, safe_filename 업데이트
"""

import json, os, re, sys, urllib.request, urllib.error, urllib.parse, psycopg2

# ── 환경 변수 로드 ──────────────────────────────────────────────────────────
def load_env(path):
    env = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip()
    return env

ENV = load_env('C:/MES/backend/.env')
SUPABASE_URL = ENV['SUPABASE_URL']   # http://localhost:8000
SERVICE_KEY  = ENV['SERVICE_ROLE_KEY']
DB_CONN = dict(
    host=ENV['DB_HOST'], port=int(ENV['DB_PORT']),
    user=ENV['DB_USER'], password=ENV['DB_PASSWORD'],
    database=ENV['DB_NAME']
)
BUCKET = 'technical'

# ── 파일명 정제 (공백 -> 언더스코어, 경로 문자 제거) ────────────────────────
def sanitize(name):
    name = os.path.basename(name)
    name = name.replace(' ', '_')
    name = re.sub(r'[/\\:*?"<>|]', '_', name)
    return name

# ── Supabase Storage 헬퍼 ─────────────────────────────────────────────────
def download_file(storage_path):
    encoded = urllib.parse.quote(storage_path, safe='/')
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{encoded}"
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {SERVICE_KEY}', 'apikey': SERVICE_KEY})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get('Content-Type', 'application/octet-stream')

def upload_file(storage_path, file_bytes, content_type):
    encoded = urllib.parse.quote(storage_path, safe='/')
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{encoded}"
    req = urllib.request.Request(url, data=file_bytes, headers={
        'Authorization': f'Bearer {SERVICE_KEY}', 'apikey': SERVICE_KEY,
        'Content-Type': content_type, 'x-upsert': 'false',
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def delete_file(storage_path):
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}"
    body = json.dumps({'prefixes': [storage_path]}).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Authorization': f'Bearer {SERVICE_KEY}', 'apikey': SERVICE_KEY,
        'Content-Type': 'application/json',
    }, method='DELETE')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def get_public_url(storage_path):
    encoded = urllib.parse.quote(storage_path, safe='/')
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{encoded}"

# ── 마이그레이션 대상 쿼리 ─────────────────────────────────────────────────
QUERY = """
    SELECT id, original_filename, safe_filename, file_path, file_url
    FROM project_technical_files
    WHERE is_active = true
      AND file_url LIKE 'http://localhost:8000%'
      AND original_filename IS NOT NULL
      AND original_filename != ''
    ORDER BY uploaded_at
"""

def needs_migration(original_filename, file_path):
    """file_path의 파일명에 original_filename의 핵심 부분이 없으면 마이그레이션 필요"""
    fname = file_path.rsplit('/', 1)[-1]  # 파일명만 추출
    safe_orig = sanitize(original_filename)
    # 파일명에 이미 원본이 포함된 경우 skip
    return safe_orig not in fname

def build_new_path(old_path, original_filename):
    """기존 경로에서 날짜+시간+UUID 접두사 + 한글 원본 파일명으로 새 경로 생성"""
    dir_part = old_path.rsplit('/', 1)[0]
    old_fname = old_path.rsplit('/', 1)[1]
    parts = old_fname.split('_')
    # date(8자리) + time(6자리) + uuid 추출
    if len(parts) >= 3 and len(parts[0]) == 8 and len(parts[1]) == 6:
        uuid_raw = parts[2].split('.')[0]  # 확장자 제거
        dt_prefix = f"{parts[0]}_{parts[1]}_{uuid_raw}"
    else:
        return None, None
    safe_orig = sanitize(original_filename)
    new_fname = f"{dt_prefix}_{safe_orig}"
    return f"{dir_part}/{new_fname}", new_fname

# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    dry_run = '--dry-run' in sys.argv

    conn = psycopg2.connect(**DB_CONN)
    cur = conn.cursor()
    cur.execute(QUERY)
    all_rows = cur.fetchall()

    # 마이그레이션 필요한 것만 필터
    targets = []
    for row in all_rows:
        rid, orig_name, safe_name, file_path, file_url = row
        if needs_migration(orig_name, file_path):
            targets.append(row)

    print(f"전체 Supabase(8000) 파일: {len(all_rows)}개")
    print(f"마이그레이션 대상: {len(targets)}개 (이미 완료: {len(all_rows)-len(targets)}개)")
    if dry_run:
        print("[DRY RUN mode - no DB/Storage changes]")

    ok_count = skip_count = err_count = 0

    for i, row in enumerate(targets):
        rid, orig_name, safe_name, old_path, file_url = row
        new_path, new_fname = build_new_path(old_path, orig_name)
        if not new_path:
            print(f"[SKIP] 날짜 접두사 추출 실패: {old_path}")
            skip_count += 1
            continue

        old_fname = old_path.rsplit('/', 1)[1]
        print(f"[{i+1}/{len(targets)}] {old_fname}")
        print(f"  orig: {orig_name}")
        print(f"  new:  {new_fname}")

        if dry_run:
            ok_count += 1
            continue

        # 1. 다운로드
        try:
            file_bytes, content_type = download_file(old_path)
        except Exception as e:
            print(f"  [ERR] 다운로드 실패: {e}")
            err_count += 1
            continue

        # 2. 신규 경로에 업로드
        status, resp = upload_file(new_path, file_bytes, content_type)
        if status not in (200, 201):
            print(f"  [ERR] 업로드 실패 ({status}): {resp[:200]}")
            err_count += 1
            continue

        # 3. DB 업데이트
        new_url = get_public_url(new_path)
        cur.execute(
            """UPDATE project_technical_files
               SET file_path = %s, file_url = %s, safe_filename = %s, updated_at = NOW()
               WHERE id = %s""",
            (new_path, new_url, new_fname, rid)
        )

        # 4. 구 파일 삭제
        del_status, del_resp = delete_file(old_path)
        if del_status not in (200, 204):
            print(f"  [WARN] 구 파일 삭제 실패 ({del_status}): {del_resp[:100]}")

        conn.commit()
        ok_count += 1
        print(f"  [OK]")

    conn.close()
    print()
    print(f"=== 완료 === OK:{ok_count} / SKIP:{skip_count} / ERR:{err_count}")
    if err_count > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
