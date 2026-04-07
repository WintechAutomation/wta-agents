import requests, os, json, time

token = open('C:/MES/wta-agents/config/atlassian-api-token.txt').read().strip()
auth = ('hjcho@wta.kr', token)
base = 'https://iwta.atlassian.net'

tasks = [
    ('1-장비물류', ['8079409174','9128738819','9623371777','8742862879','9327411201','8330838017']),
    ('2-분말검사', ['8048672826','9509830687','9577070593','9603547139']),
    ('3-연삭측정제어', ['8313438485','8324448355','8744075303','8742862879','8797192353']),
    ('4-포장혼입검사', ['9485484034','8776941569','8803483649','8736702465','8160739377']),
    ('5-호닝신뢰성', ['9643098158','9477226497','9501770184','8466759681','9078669313']),
]

TIMEOUT = 60  # seconds per request
MAX_RETRIES = 3

def get_with_retry(url, auth, allow_redirects=True, timeout=TIMEOUT, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            r = requests.get(url, auth=auth, allow_redirects=allow_redirects, timeout=timeout)
            return r
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f'    RETRY ({attempt+1}/{retries}) after {wait}s: {e}')
                time.sleep(wait)
            else:
                raise
    return None

all_results = {}

for folder_name, page_ids in tasks:
    save_dir = f'C:/MES/wta-agents/reports/MAX/경상연구개발/참고문서-이미지/{folder_name}'
    os.makedirs(save_dir, exist_ok=True)

    # Load existing metadata to skip already-downloaded files
    meta_path = f'{save_dir}/images-meta.json'
    if os.path.exists(meta_path):
        folder_results = json.load(open(meta_path, encoding='utf-8'))
        done_pages = {item['page_id'] for item in folder_results}
    else:
        folder_results = []
        done_pages = set()

    for page_id in page_ids:
        if page_id in done_pages:
            print(f'  SKIP (already done) {page_id}')
            continue

        # Get attachment list
        url = f'{base}/wiki/rest/api/content/{page_id}/child/attachment?limit=100'
        try:
            r = get_with_retry(url, auth)
        except Exception as e:
            print(f'  SKIP {page_id}: {e}')
            continue

        if r.status_code != 200:
            print(f'  SKIP {page_id}: {r.status_code}')
            continue

        attachments = r.json().get('results', [])
        print(f'  Page {page_id}: {len(attachments)} attachments')

        page_imgs = []
        for i, att in enumerate(attachments, 1):
            media_type = att.get('metadata', {}).get('mediaType', '')
            if not media_type.startswith('image/'):
                continue  # skip non-images

            att_id = att['id']
            filename = att['title']
            save_path = f'{save_dir}/p{page_id}-img{i:03d}-{filename}'

            # Skip if already downloaded
            if os.path.exists(save_path):
                size = os.path.getsize(save_path)
                page_imgs.append({'file': f'p{page_id}-img{i:03d}-{filename}', 'size': size})
                print(f'    SKIP (exists) {filename}')
                continue

            download_url = f'{base}/wiki/rest/api/content/{page_id}/child/attachment/{att_id}/download'
            try:
                resp = get_with_retry(download_url, auth)
            except Exception as e:
                print(f'    FAIL {filename}: {e}')
                continue

            if resp.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
                size = len(resp.content)
                page_imgs.append({'file': f'p{page_id}-img{i:03d}-{filename}', 'size': size})
                print(f'    OK {filename} ({size//1024}KB)')
            else:
                print(f'    FAIL {filename}: {resp.status_code}')

        folder_results.append({'page_id': page_id, 'images': page_imgs})
        # Save incrementally after each page
        json.dump(folder_results, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    all_results[folder_name] = folder_results
    print(f'{folder_name} 완료')

print('전체 완료')
