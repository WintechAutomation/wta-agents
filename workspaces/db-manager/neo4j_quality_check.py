"""
Neo4j manuals-v2 GraphRAG 데이터 품질 점검
bolt://localhost:7688
"""
import json, re
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7688"
NEO4J_USER = "neo4j"
NEO4J_PASS = "WtaPoc2026!Graph"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def run(cypher, **params):
    with driver.session() as s:
        return list(s.run(cypher, **params))

print("=" * 60)
print("1. 노드/엣지 통계")
print("=" * 60)

# 전체 노드/엣지 수
total_nodes = run("MATCH (n) RETURN count(n) AS cnt")[0]["cnt"]
total_rels = run("MATCH ()-[r]->() RETURN count(r) AS cnt")[0]["cnt"]
print(f"총 노드: {total_nodes:,}")
print(f"총 엣지: {total_rels:,}")

# 레이블별 분포
label_dist = run("MATCH (n) UNWIND labels(n) AS lbl RETURN lbl, count(*) AS cnt ORDER BY cnt DESC")
print("\n레이블별 노드 분포:")
for r in label_dist:
    print(f"  {r['lbl']}: {r['cnt']:,}")

# ManualsV2Entity 전용 source_category 분포 (cat 필드)
print("\n")
try:
    cat_dist = run("MATCH (n:ManualsV2Entity) WHERE n.category IS NOT NULL RETURN n.category AS cat, count(*) AS cnt ORDER BY cnt DESC LIMIT 20")
    print("category 분포 (ManualsV2Entity):")
    for r in cat_dist:
        print(f"  {r['cat']}: {r['cnt']:,}")
except:
    pass

# source (file_id) 기준 분포
try:
    src_dist = run("MATCH (n:ManualsV2Entity) RETURN n.source AS src, count(*) AS cnt ORDER BY cnt DESC LIMIT 20")
    print("\nsource(file_id) 분포 TOP 20:")
    for r in src_dist:
        print(f"  {str(r['src'])[:50]}: {r['cnt']:,}")
except Exception as e:
    print(f"source 분포 조회 실패: {e}")

print("\n" + "=" * 60)
print("2. 엔티티 이름 품질 점검")
print("=" * 60)

# 이름 길이 분포
name_len = run("""
MATCH (n:ManualsV2Entity)
WITH size(n.name) AS l
RETURN
  count(CASE WHEN l <= 2 THEN 1 END) AS very_short,
  count(CASE WHEN l >= 3 AND l <= 10 THEN 1 END) AS short,
  count(CASE WHEN l >= 11 AND l <= 50 THEN 1 END) AS medium,
  count(CASE WHEN l > 50 AND l <= 200 THEN 1 END) AS long_name,
  count(CASE WHEN l > 200 THEN 1 END) AS very_long,
  avg(l) AS avg_len,
  max(l) AS max_len
""")
if name_len:
    r = name_len[0]
    print(f"이름 길이 분포:")
    print(f"  매우 짧음 (<=2자): {r['very_short']:,}")
    print(f"  짧음 (3-10자): {r['short']:,}")
    print(f"  적정 (11-50자): {r['medium']:,}")
    print(f"  긴 이름 (51-200자): {r['long_name']:,}")
    print(f"  매우 긴 이름 (>200자): {r['very_long']:,}")
    print(f"  평균 길이: {r['avg_len']:.1f}자, 최대: {r['max_len']}자")

# 매우 짧은 이름 샘플 (<=2자)
short_samples = run("MATCH (n:ManualsV2Entity) WHERE size(n.name) <= 2 RETURN n.name AS name, n.type AS type LIMIT 20")
print(f"\n매우 짧은 이름 샘플 (<=2자, {len(short_samples)}건):")
for r in short_samples[:15]:
    print(f"  [{r['type']}] '{r['name']}'")

# 매우 긴 이름 샘플 (>200자)
long_samples = run("MATCH (n:ManualsV2Entity) WHERE size(n.name) > 200 RETURN n.name AS name, n.type AS type LIMIT 5")
print(f"\n매우 긴 이름 샘플 (>200자, {len(long_samples)}건):")
for r in long_samples:
    print(f"  [{r['type']}] '{r['name'][:100]}...'")

# 숫자/특수문자만인 이름
junk_samples = run(r"""
MATCH (n:ManualsV2Entity)
WHERE n.name =~ '^[0-9\\s\\-\\.\\(\\)\\[\\]_/,]+$'
RETURN n.name AS name, n.type AS type LIMIT 20
""")
print(f"\n숫자/기호만인 이름 샘플 ({len(junk_samples)}건):")
for r in junk_samples[:10]:
    print(f"  [{r['type']}] '{r['name']}'")

# 타입 분포
type_dist = run("MATCH (n:ManualsV2Entity) WHERE n.type IS NOT NULL RETURN n.type AS t, count(*) AS cnt ORDER BY cnt DESC LIMIT 20")
print("\n엔티티 타입 분포 TOP 20:")
for r in type_dist:
    print(f"  {r['t']}: {r['cnt']:,}")

print("\n" + "=" * 60)
print("3. 관계(엣지) 품질 점검")
print("=" * 60)

# 관계 타입 분포
rel_dist = run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS cnt ORDER BY cnt DESC")
print("관계 타입 분포:")
for r in rel_dist:
    print(f"  {r['t']}: {r['cnt']:,}")

# 관계 샘플 (논리적 타당성 확인)
print("\n관계 샘플 (소스→타입→타겟):")
rel_samples = run("""
MATCH (a:ManualsV2Entity)-[r]->(b:ManualsV2Entity)
WHERE size(a.name) > 2 AND size(b.name) > 2
RETURN a.name AS src, type(r) AS rel, b.name AS tgt, a.type AS src_type, b.type AS tgt_type
LIMIT 30
""")
for r in rel_samples:
    print(f"  [{r['src_type']}]{r['src'][:30]} --{r['rel']}--> [{r['tgt_type']}]{r['tgt'][:30]}")

print("\n" + "=" * 60)
print("4. 고립 노드 (연결 없는 노드) 분석")
print("=" * 60)

isolated = run("MATCH (n:ManualsV2Entity) WHERE NOT (n)--() RETURN count(n) AS cnt")[0]["cnt"]
print(f"고립 노드 수: {isolated:,} / 전체 {total_nodes:,} ({isolated/max(total_nodes,1)*100:.1f}%)")

isolated_samples = run("""
MATCH (n:ManualsV2Entity) WHERE NOT (n)--()
RETURN n.name AS name, n.type AS type, n.source AS src LIMIT 10
""")
print("고립 노드 샘플:")
for r in isolated_samples:
    print(f"  [{r['type']}] '{r['name']}' (source: {str(r['src'])[:40]})")

print("\n" + "=" * 60)
print("5. 중복 노드 분석")
print("=" * 60)

dup = run("""
MATCH (n:ManualsV2Entity)
WITH n.name AS name, count(*) AS cnt
WHERE cnt > 1
RETURN name, cnt ORDER BY cnt DESC LIMIT 20
""")
print(f"중복 이름 TOP 20:")
for r in dup[:20]:
    print(f"  '{r['name']}': {r['cnt']}건")

print("\n" + "=" * 60)
print("6. source별 품질 비교 (1_robot vs 4_servo)")
print("=" * 60)

try:
    robot_stats = run("""
    MATCH (n:ManualsV2Entity) WHERE n.source STARTS WITH '1_robot'
    RETURN count(n) AS nodes, avg(size(n.name)) AS avg_name_len,
           count(CASE WHEN size(n.name) <= 2 THEN 1 END) AS junk_count
    """)
    servo_stats = run("""
    MATCH (n:ManualsV2Entity) WHERE n.source STARTS WITH '4_servo'
    RETURN count(n) AS nodes, avg(size(n.name)) AS avg_name_len,
           count(CASE WHEN size(n.name) <= 2 THEN 1 END) AS junk_count
    """)
    if robot_stats:
        r = robot_stats[0]
        junk_pct = r['junk_count']/max(r['nodes'],1)*100
        print(f"1_robot: 노드 {r['nodes']:,}개, 평균이름길이 {r['avg_name_len']:.1f}자, 쓰레기 {r['junk_count']}건({junk_pct:.1f}%)")
    if servo_stats:
        r = servo_stats[0]
        junk_pct = r['junk_count']/max(r['nodes'],1)*100
        print(f"4_servo: 노드 {r['nodes']:,}개, 평균이름길이 {r['avg_name_len']:.1f}자, 쓰레기 {r['junk_count']}건({junk_pct:.1f}%)")
except Exception as e:
    print(f"source 비교 실패: {e}")

# 1_robot 엔티티 샘플
print("\n1_robot 엔티티 샘플 (이름 길이 기준 정렬):")
robot_sample = run("""
MATCH (n:ManualsV2Entity) WHERE n.source STARTS WITH '1_robot'
RETURN n.name AS name, n.type AS type ORDER BY size(n.name) LIMIT 20
""")
for r in robot_sample:
    print(f"  [{r['type']}] '{r['name']}'")

# 4_servo 엔티티 샘플
print("\n4_servo 엔티티 샘플 (이름 길이 기준 정렬):")
servo_sample = run("""
MATCH (n:ManualsV2Entity) WHERE n.source STARTS WITH '4_servo'
RETURN n.name AS name, n.type AS type ORDER BY size(n.name) LIMIT 20
""")
for r in servo_sample:
    print(f"  [{r['type']}] '{r['name']}'")

driver.close()
print("\n점검 완료")
