"""실제 CS 키워드 벡터검색 품질 테스트"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import requests, psycopg2, json

EMBED_URL = 'http://182.224.6.147:11434/api/embed'
EMBED_MODEL = 'qwen3-embedding:8b'

conn = psycopg2.connect(host='localhost', port=55432, user='postgres',
    password='your-super-secret-and-long-postgres-password', dbname='postgres')
cur = conn.cursor()

def get_embedding(text):
    r = requests.post(EMBED_URL, json={'model': EMBED_MODEL, 'input': [text]}, timeout=60)
    if r.status_code == 200:
        emb = r.json()['embeddings'][0]
        return emb[:2000]  # DB 저장 차원(2000)에 맞춰 truncate
    return None

def search_table(table, vec_col, content_col, emb, top_k=3, extra_where=''):
    vec_str = '[' + ','.join(str(x) for x in emb) + ']'
    where = f'AND {extra_where}' if extra_where else ''
    cur.execute(f"""
        SELECT id, 1 - ({vec_col} <=> '{vec_str}'::vector) as sim,
               {content_col}
        FROM {table}
        WHERE {vec_col} IS NOT NULL {where}
        ORDER BY {vec_col} <=> '{vec_str}'::vector
        LIMIT {top_k}
    """)
    return cur.fetchall()

queries = [
    "미쓰비시 로봇 배터리 교체방법",
    "파스텍 E-004 에러",
    "파나소닉 A6B 브레이크 파라미터",
    "Z축 이동 실패 알람",
    "PVD 로딩 막대 높이 측정센서 위치 설정",
]

tables = [
    ('csagent.vector_embeddings', 'embedding', 'text', ''),
    ('manual.documents',          'embedding', 'content', "LENGTH(content) >= 50 AND content NOT LIKE '%cid:%'"),
    ('manual.wta_documents',      'embedding', 'content', 'LENGTH(content) >= 50'),
]

results_summary = []

for q in queries:
    print(f"\n{'='*65}")
    print(f"질문: {q}")
    print('='*65)

    emb = get_embedding(q)
    if not emb:
        print("  임베딩 실패")
        continue

    q_result = {'query': q, 'tables': {}}

    for table, vcol, ccol, extra in tables:
        rows = search_table(table, vcol, ccol, emb, extra_where=extra)
        short_name = table.split('.')[-1]
        print(f"\n  [{short_name}]")
        useful = False
        for i, (rid, sim, content) in enumerate(rows, 1):
            snippet = str(content)[:120].replace('\n', ' ')
            is_useful = sim >= 0.75
            useful = useful or is_useful
            mark = 'O' if is_useful else 'X'
            print(f"    #{i} sim={sim:.3f} {mark} | {snippet}")
        q_result['tables'][short_name] = {'top_sim': rows[0][1] if rows else 0, 'useful': useful}

    results_summary.append(q_result)

print(f"\n{'='*65}")
print("종합 요약")
print('='*65)
print(f"{'질문':<35} {'CS이력':>7} {'부품매뉴얼':>10} {'WTA매뉴얼':>10}")
print('-'*65)
for r in results_summary:
    q_short = r['query'][:33]
    cs  = r['tables'].get('vector_embeddings', {})
    doc = r['tables'].get('documents', {})
    wta = r['tables'].get('wta_documents', {})
    def fmt(d): return f"{d.get('top_sim',0):.2f}{'O' if d.get('useful') else 'X'}"
    print(f"{q_short:<35} {fmt(cs):>7} {fmt(doc):>10} {fmt(wta):>10}")

conn.close()
