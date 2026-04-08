"""
추출된 엔티티/관계 JSON → Neo4j 적재
라벨: 엔티티 타입 라벨만 사용 (Phase4_CM 제거)
출처: 노드 속성 source='CM'으로 구분
사용: python neo4j-load-entities.py <entities_json_file>
"""
import sys, json, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NEO4J_ENV = Path('C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env')
NEO4J_PASS = ''
for line in NEO4J_ENV.read_text().splitlines():
    if line.startswith('NEO4J_AUTH=neo4j/'):
        NEO4J_PASS = line.split('/', 1)[1].strip()
        break

VALID_NODE_TYPES = {'Customer','Equipment','Product','Component','Process',
                    'Issue','Resolution','Person','Tool','Manual'}
VALID_REL_TYPES  = {'OWNS','HAS_ISSUE','SIMILAR_TO','RESOLVED_BY',
                    'INVOLVES_COMPONENT','USES_COMPONENT','INVOLVED_IN',
                    'HAS_SUBPROCESS','USES_TOOL','MAINTAINS','DOCUMENTS'}

from neo4j import GraphDatabase

def load_batch(pages: list):
    driver = GraphDatabase.driver('bolt://localhost:7688', auth=('neo4j', NEO4J_PASS))
    total_nodes, total_rels = 0, 0
    with driver.session() as s:
        for page in pages:
            page_id = page.get('page_id', '')
            title   = page.get('title', '')
            entities = page.get('entities', [])
            relations = page.get('relations', [])
            id_map = {}
            for ent in entities:
                etype = ent.get('type', '')
                if etype not in VALID_NODE_TYPES:
                    continue
                orig_id = ent.get('id', '')
                if not orig_id:
                    continue
                safe_id = f"cm4_{page_id}_{re.sub(r'[^a-zA-Z0-9_]','_', orig_id)}"
                id_map[orig_id] = safe_id
                props = {k: v for k, v in (ent.get('properties') or {}).items()
                         if v is not None and v != ''}
                props.update({'_id': safe_id, '_page_id': page_id, '_space': 'CM',
                              '_title': title[:100], 'source': 'CM'})
                try:
                    s.run(
                        f"MERGE (n:{etype} {{_id: $_id}}) "
                        f"SET n += $props, n.name = $name",
                        _id=safe_id, props=props, name=ent.get('name', orig_id)
                    )
                    total_nodes += 1
                except Exception as e:
                    print(f'  노드 오류: {e}')
            for rel in relations:
                src = id_map.get(rel.get('source', ''))
                tgt = id_map.get(rel.get('target', ''))
                rtype = rel.get('type', '')
                if not src or not tgt or rtype not in VALID_REL_TYPES:
                    continue
                try:
                    s.run(
                        f"MATCH (a {{_id: $src}}), (b {{_id: $tgt}}) "
                        f"MERGE (a)-[r:{rtype}]->(b)",
                        src=src, tgt=tgt
                    )
                    total_rels += 1
                except Exception as e:
                    print(f'  관계 오류: {e}')
    driver.close()
    return total_nodes, total_rels

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('사용: python neo4j-load-entities.py <entities_json_file>')
        sys.exit(1)
    with open(sys.argv[1], encoding='utf-8') as f:
        data = json.load(f)
    pages = data if isinstance(data, list) else [data]
    nodes, rels = load_batch(pages)
    print(f'적재 완료: {nodes}노드, {rels}관계')
