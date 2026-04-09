# -*- coding: utf-8 -*-
"""MCA210T 발주현황 1년치 전체 필드 CSV 추출"""
import sys, io, os, json, csv, requests
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv(r'C:\MES\backend\.env')
user = os.getenv('MES_SERVICE_USERNAME')
pw = os.getenv('MES_SERVICE_PASSWORD')

# JWT 토큰 발급
r = requests.post('http://localhost:8100/api/auth/login', json={'username': user, 'password': pw})
token = r.json()['data']['access']
headers = {'Authorization': f'Bearer {token}'}
print('토큰 발급 성공')

# 페이징으로 전체 데이터 수집
all_items = []
page = 1
limit = 500
while True:
    r = requests.get(
        f'http://localhost:8100/api/erp/purchase/mca210t?limit={limit}&page={page}',
        headers=headers
    )
    resp = r.json()
    items = resp.get('data', {}).get('items', [])
    if not items:
        break
    all_items.extend(items)
    print(f'  페이지 {page}: {len(items)}건 (누적 {len(all_items)}건)')
    if len(items) < limit:
        break
    page += 1

print(f'\n총 수집: {len(all_items)}건')

if not all_items:
    print('데이터 없음')
    sys.exit(1)

# CSV 저장
outpath = r'C:\MES\wta-agents\reports\김근형\MCA210T_발주현황_1년.csv'
fields = list(all_items[0].keys())
with open(outpath, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(all_items)

print(f'CSV 저장: {outpath}')
print(f'필드: {fields}')
print(f'건수: {len(all_items)}건')
