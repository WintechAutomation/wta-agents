"""
CS 이력 텍스트에서 실제 등장하는 부품명/제조사명 추출
- 영문 토큰 빈도 분석
- 알려진 제조사/장비명 사전 매칭
"""
import os
import sys
import re
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from dotenv import load_dotenv

# DB 연결
load_dotenv("C:/MES/backend/.env")
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

# 직접 연결 시도
conn = psycopg2.connect(
    host="localhost", port=55432,
    dbname="postgres",
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres")
)

cur = conn.cursor()
cur.execute("""
    SELECT coalesce(title,'') || ' ' || coalesce(symptom_and_cause,'') || ' ' || coalesce(action_result,'')
    FROM csagent.cs_history
    WHERE symptom_and_cause IS NOT NULL OR action_result IS NOT NULL
""")
rows = cur.fetchall()
conn.close()

# 전체 텍스트 합치기
all_text = ' '.join(r[0] for r in rows)

# 영문 단어 추출 (2글자 이상, 숫자 포함 가능)
tokens = re.findall(r'[A-Za-z][A-Za-z0-9\-\.]{1,20}', all_text)

# 불용어 제거
STOPWORDS = {
    'and', 'the', 'for', 'not', 'are', 'was', 'has', 'but', 'from', 'with', 'this',
    'that', 'have', 'been', 'will', 'one', 'two', 'can', 'all', 'new', 'also',
    'use', 'used', 'set', 'type', 'mode', 'data', 'out', 'off', 'via', 'per',
    'ok', 'no', 'yes', 'on', 'in', 'is', 'it', 'to', 'of', 'at', 'or', 'by',
    'be', 'do', 'an', 'so', 'up', 'us', 'we', 'if', 'as', 'more', 'such',
    'after', 'during', 'over', 'under', 'into', 'each', 'about', 'same',
    'error', 'alarm', 'check', 'reset', 'power', 'cable', 'signal', 'test',
    'unit', 'side', 'axis', 'time', 'date', 'file', 'port', 'line', 'step',
    'move', 'work', 'done', 'note', 'item', 'main', 'back', 'home', 'stop',
    'run', 'end', 'start', 'auto', 'manual', 'input', 'output', 'status',
    'speed', 'position', 'current', 'voltage', 'motor', 'drive', 'servo',
    'robot', 'sensor', 'encoder', 'board', 'card', 'cpu', 'pc', 'io',
    'system', 'control', 'program', 'setting', 'parameter', 'address',
    'version', 'model', 'number', 'code', 'list', 'table', 'value',
    'max', 'min', 'ok', 'ng', 'rev', 'ver', 'no', 'yes',
    'com', 'net', 'tcp', 'ip', 'id', 'pw', 'db', 'api',
    'nc', 'hmi', 'plc', 'mes', 'erp', 'wta', 'wbm', 'pvd', 'cvd',
}

freq = Counter(t.lower() for t in tokens if t.lower() not in STOPWORDS and len(t) >= 3)

print("=== CS 이력 영문 토큰 상위 100개 ===")
for word, cnt in freq.most_common(100):
    print(f"  {word}: {cnt}")

# 알려진 제조사/장비 사전으로 매칭
KNOWN = {
    'yaskawa': 'Yaskawa', 'motoman': 'Yaskawa',
    'keyence': 'KEYENCE',
    'mitsubishi': 'Mitsubishi', 'melsec': 'Mitsubishi', 'melfa': 'Mitsubishi',
    'denso': 'Denso', 'rc8': 'Denso',
    'proface': 'Pro-Face', 'pro-face': 'Pro-Face',
    'beckhoff': 'Beckhoff', 'twincat': 'Beckhoff',
    'sick': 'SICK',
    'omron': 'Omron',
    'panasonic': 'Panasonic', 'minas': 'Panasonic',
    'acs': 'ACS', 'spiiplus': 'ACS', 'mc4u': 'ACS',
    'smc': 'SMC',
    'fastech': 'Fastech', 'ezi-servo': 'Fastech',
    'csd5': 'CSD5', 'csd-5': 'CSD5',
    'crevis': 'Crevis',
    'deltatau': 'DeltaTau', 'pmac': 'DeltaTau',
    'sankyo': 'Sankyo',
    'inovance': 'Inovance', 'is620': 'Inovance',
    'leadshine': 'Leadshine',
    'ethercat': 'EtherCAT',
    'modbus': 'Modbus',
    'codesys': 'Codesys',
    'abb': 'ABB',
    'sanmotion': 'Sanmotion',
    'softservo': 'SoftServo',
    'trio': 'TrioMotion', 'triomc': 'TrioMotion',
    'pilz': 'Pilz', 'pnoz': 'Pilz',
    'autonics': 'Autonics',
    'dalsa': 'Dalsa', 'teledyne': 'Dalsa',
    'euresys': 'Euresys',
    'fuji': 'Fuji',
}

print("\n=== 알려진 제조사/장비 언급 건수 ===")
known_cnt = Counter()
for word, cnt in freq.items():
    for kw, brand in KNOWN.items():
        if kw in word:
            known_cnt[brand] += cnt
            break

for brand, cnt in known_cnt.most_common():
    print(f"  {brand}: {cnt}")
