"""
포장혼입검사 지식그래프 Neo4j 적재
7개 Confluence 페이지에서 수동 추출한 엔티티/관계를 Cypher로 적재
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from neo4j import GraphDatabase

# env 파일에서 패스워드 읽기
env_file = Path("C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env")
for line in env_file.read_text().splitlines():
    if line.startswith("NEO4J_AUTH=neo4j/"):
        pw = line.split("/", 1)[1].strip()
        break

driver = GraphDatabase.driver("bolt://localhost:7688", auth=("neo4j", pw))

CYPHER_STATEMENTS = [
    # ===== 제약 및 인덱스 =====
    "CREATE CONSTRAINT equipment_name IF NOT EXISTS FOR (e:Equipment) REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT customer_name  IF NOT EXISTS FOR (c:Customer)  REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT issue_id       IF NOT EXISTS FOR (i:Issue)     REQUIRE i.page_id IS UNIQUE",
    "CREATE CONSTRAINT person_name    IF NOT EXISTS FOR (p:Person)    REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT process_name   IF NOT EXISTS FOR (pr:Process)  REQUIRE pr.name IS UNIQUE",
    "CREATE CONSTRAINT component_model IF NOT EXISTS FOR (comp:Component) REQUIRE comp.model IS UNIQUE",
    "CREATE INDEX issue_title         IF NOT EXISTS FOR (i:Issue)     ON (i.title)",
    "CREATE INDEX product_type        IF NOT EXISTS FOR (pd:Product)  ON (pd.type)",

    # ===== 고객(Customer) =====
    """
    MERGE (c:Customer {name: 'Korloy'})
    SET c.alias = '한국야금',
        c.country = '한국',
        c.region = '국내'
    """,

    # ===== 장비(Equipment) =====
    """
    MERGE (e1:Equipment {name: 'Korloy 포장기 #6'})
    SET e1.model = '#25-3',
        e1.type = '포장기',
        e1.location = '한국야금 현장'
    """,
    """
    MERGE (e2:Equipment {name: '혼입검사기'})
    SET e2.type = '검사기',
        e2.description = '혼입 분류 기능 내장 검사기'
    """,

    # ===== 제품(Product) =====
    """
    MERGE (p1:Product {type: 'C형 인서트'})
    SET p1.material = '경면',
        p1.description = '경면 제품, Nose-r부 측정 대상'
    """,
    """MERGE (p2:Product {type: 'W형 인서트'}) SET p2.material = '경면'""",
    """MERGE (p3:Product {type: 'T형 인서트'}) SET p3.rotation_count = 3""",
    """MERGE (p4:Product {type: 'S형 인서트'}) SET p4.rotation_count = 4""",
    """MERGE (p5:Product {type: 'V형 인서트'}) SET p5.description = '코그넥스 검사 대상'""",
    """MERGE (p6:Product {type: 'B형 인서트'})""",

    # ===== 부품/광학계(Component) =====
    """
    MERGE (cam:Component {model: 'acA2500-14gm'})
    SET cam.name = '카메라', cam.type = '카메라'
    """,
    """
    MERGE (lens:Component {model: 'M2514-MP2'})
    SET lens.name = '렌즈', lens.type = '렌즈'
    """,
    """
    MERGE (light:Component {model: 'DOMELIGHT100'})
    SET light.name = '조명', light.type = '조명',
        light.lwd_design = '169mm',
        light.fov_design = '38.251x28.856mm'
    """,

    # ===== 공정/기능(Process) =====
    """
    MERGE (pr1:Process {name: '혼입 분류'})
    SET pr1.description = '인서트 혼입 분류 전체 프로세스',
        pr1.page_id = '8725987333',
        pr1.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/VSNEDU/pages/8725987333'
    """,
    """
    MERGE (pr2:Process {name: 'CB 방향 구분'})
    SET pr2.description = '인서트 C/B 방향이 원하는 방향인지 확인',
        pr2.tool = 'C/B 방향 Tool',
        pr2.parent = '혼입 분류'
    """,
    """
    MERGE (pr3:Process {name: '앞뒷면 구분'})
    SET pr3.description = '인서트 앞면/뒷면 판별',
        pr3.tool = '앞뒷면 Tool',
        pr3.parent = '혼입 분류'
    """,
    """
    MERGE (pr4:Process {name: 'CB 혼입 비교'})
    SET pr4.description = '인서트 C/B 모양이 원하는 모양인지 확인',
        pr4.tool = 'C/B 혼입 Tool',
        pr4.parent = '혼입 분류'
    """,
    """
    MERGE (pr5:Process {name: 'NoseR 측정'})
    SET pr5.description = '인서트 Nose 반경 측정 및 OK/NG 판정',
        pr5.tool = 'FindCircleTool',
        pr5.parent = '혼입 분류'
    """,
    """
    MERGE (pr6:Process {name: '레시피 에디터'})
    SET pr6.description = '혼입 분류 기능을 레시피 파일로 저장/불러오기',
        pr6.page_id = '8726085635',
        pr6.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/VSNEDU/pages/8726085635',
        pr6.save_format = 'recipe.txt + TempTool.vpp + trainImage.png'
    """,
    """
    MERGE (pr7:Process {name: '위치 검사'})
    SET pr7.description = '인서트 위치(X,Y) 및 각도 탐색, 코그넥스 Align Tool 활용',
        pr7.tool = 'Align Tool + Polygon Tool'
    """,

    # ===== 이슈(Issue) =====
    """
    MERGE (i1:Issue {page_id: '9485484034'})
    SET i1.title = 'Korloy 포장기 #6 밝기 비대칭',
        i1.full_title = 'Korloy 포장기 #6(#25-3) 혼입 검사 특정 제품 밝기 비대칭',
        i1.date = '2026-01-20',
        i1.status = '조치완료',
        i1.severity = '주요',
        i1.symptom = 'C,W형 경면 제품 이미지에서 한쪽 부분 비정상적으로 밝게 시인, Nose-r부 치수 상이하게 측정',
        i1.root_cause = '광축 중심과 조명 중심 한쪽으로 치우침 (광축 중심이 조명 중심보다 좌측 하단)',
        i1.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/~278335737/pages/9485484034'
    """,
    """
    MERGE (i2:Issue {page_id: '8685453351'})
    SET i2.title = '혼입 검사 이슈',
        i2.date = '2025-02-10',
        i2.status = '조치완료',
        i2.symptom = '오검출, 경면 제품 순차 처리 후 비대칭',
        i2.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/2G7b9jRE5k9n/pages/8685453351'
    """,

    # ===== 조치방안(Resolution) =====
    """
    MERGE (r1:Resolution {id: 'R001'})
    SET r1.description = '광축 중심과 조명 중심 상하좌우 ±1mm 이내 세팅',
        r1.category = '광학계 세팅',
        r1.effectiveness = '중심 기준 ±1mm 내에서 C,W형 경면 제품 밝기 비대칭 개선 가능'
    """,
    """
    MERGE (r2:Resolution {id: 'R002'})
    SET r2.description = '컨베이어 벨트 기준 조명 높이 10mm 수준 세팅 권장',
        r2.category = '조명 높이 조정',
        r2.detail = '11mm~19mm 테스트 결과, 높아질수록 비대칭 현상 강해짐'
    """,
    """
    MERGE (r3:Resolution {id: 'R003'})
    SET r3.description = '측정 가능 제품군 제한',
        r3.category = '제품 운영 정책',
        r3.detail = '경면 제품 및 랜드부 경사가 큰 제품은 현상 재발 가능성으로 제한 필요'
    """,

    # ===== 담당자(Person) =====
    """
    MERGE (per1:Person {name: '정진원'})
    SET per1.dept = '소프트웨어팀',
        per1.role = '혼입분류 프로젝트 담당'
    """,

    # ===== 소프트웨어 도구(Tool) =====
    """
    MERGE (t1:Tool {name: '코그넥스'})
    SET t1.type = '비전 검사 플랫폼',
        t1.components = ['Align Tool', 'Polygon Tool', 'FindCircleTool', 'FindCornerTool', 'Tracker Tool']
    """,

    # ===== 관계 정의 =====

    # 고객-장비
    """
    MATCH (c:Customer {name: 'Korloy'})
    MATCH (e:Equipment {name: 'Korloy 포장기 #6'})
    MERGE (c)-[:OWNS]->(e)
    """,

    # 장비-이슈
    """
    MATCH (e:Equipment {name: 'Korloy 포장기 #6'})
    MATCH (i:Issue {page_id: '9485484034'})
    MERGE (e)-[:HAS_ISSUE {date: '2026-01-20'}]->(i)
    """,
    """
    MATCH (e:Equipment {name: '혼입검사기'})
    MATCH (i:Issue {page_id: '8685453351'})
    MERGE (e)-[:HAS_ISSUE {date: '2025-02-10'}]->(i)
    """,

    # 이슈-이슈 (유사사례) - TC-01 핵심 관계
    """
    MATCH (i1:Issue {page_id: '9485484034'})
    MATCH (i2:Issue {page_id: '8685453351'})
    MERGE (i1)-[:SIMILAR_TO {
        similarity_score: 0.82,
        basis: '동일 현상: 경면 제품 밝기 비대칭, 동일 장비 유형(포장기 혼입검사부)',
        identified_by: 'manual'
    }]->(i2)
    """,

    # 이슈-조치방안
    """
    MATCH (i:Issue {page_id: '9485484034'})
    MATCH (r1:Resolution {id: 'R001'})
    MERGE (i)-[:RESOLVED_BY]->(r1)
    """,
    """
    MATCH (i:Issue {page_id: '9485484034'})
    MATCH (r2:Resolution {id: 'R002'})
    MERGE (i)-[:RESOLVED_BY]->(r2)
    """,
    """
    MATCH (i:Issue {page_id: '9485484034'})
    MATCH (r3:Resolution {id: 'R003'})
    MERGE (i)-[:RESOLVED_BY]->(r3)
    """,

    # 이슈-광학계 부품
    """
    MATCH (i:Issue {page_id: '9485484034'})
    MATCH (cam:Component {model: 'acA2500-14gm'})
    MATCH (lens:Component {model: 'M2514-MP2'})
    MATCH (light:Component {model: 'DOMELIGHT100'})
    MERGE (i)-[:INVOLVES_COMPONENT]->(cam)
    MERGE (i)-[:INVOLVES_COMPONENT]->(lens)
    MERGE (i)-[:INVOLVES_COMPONENT]->(light)
    """,

    # 장비-광학계 구성
    """
    MATCH (e:Equipment {name: 'Korloy 포장기 #6'})
    MATCH (cam:Component {model: 'acA2500-14gm'})
    MATCH (lens:Component {model: 'M2514-MP2'})
    MATCH (light:Component {model: 'DOMELIGHT100'})
    MERGE (e)-[:USES_COMPONENT]->(cam)
    MERGE (e)-[:USES_COMPONENT]->(lens)
    MERGE (e)-[:USES_COMPONENT]->(light)
    """,

    # 제품-이슈
    """
    MATCH (p1:Product {type: 'C형 인서트'})
    MATCH (p2:Product {type: 'W형 인서트'})
    MATCH (i:Issue {page_id: '9485484034'})
    MERGE (p1)-[:INVOLVED_IN]->(i)
    MERGE (p2)-[:INVOLVED_IN]->(i)
    """,

    # 공정 계층 관계
    """
    MATCH (parent:Process {name: '혼입 분류'})
    MATCH (child1:Process {name: 'CB 방향 구분'})
    MATCH (child2:Process {name: '앞뒷면 구분'})
    MATCH (child3:Process {name: 'CB 혼입 비교'})
    MATCH (child4:Process {name: 'NoseR 측정'})
    MATCH (child5:Process {name: '레시피 에디터'})
    MATCH (child6:Process {name: '위치 검사'})
    MERGE (parent)-[:HAS_SUBPROCESS]->(child1)
    MERGE (parent)-[:HAS_SUBPROCESS]->(child2)
    MERGE (parent)-[:HAS_SUBPROCESS]->(child3)
    MERGE (parent)-[:HAS_SUBPROCESS]->(child4)
    MERGE (parent)-[:HAS_SUBPROCESS]->(child5)
    MERGE (parent)-[:HAS_SUBPROCESS]->(child6)
    """,

    # 레시피 에디터 개발 이슈
    """
    MATCH (pr:Process {name: '레시피 에디터'})
    MATCH (i:Issue {page_id: '8719663107'})
    MERGE (pr)-[:ADDRESSED_IN_DOC {page_id: '8719663107', title: '인서트 내부 글자 검출 결과 정리'}]->(i)
    """,

    # 담당자-공정
    """
    MATCH (per:Person {name: '정진원'})
    MATCH (pr:Process {name: '혼입 분류'})
    MERGE (per)-[:MAINTAINS {
        note: '혼입분류 프로젝트 개발 담당, 인수인계자료 작성'
    }]->(pr)
    """,

    # 인서트 내부 글자 검출 이슈 노드 추가
    """
    MERGE (i3:Issue {page_id: '8719663107'})
    SET i3.title = '인서트 내부 글자 검출 알고리즘',
        i3.date = '2025-01-01',
        i3.status = '개발완료',
        i3.symptom = '기존 툴을 레시피 에디터로 제작 필요, CB 방향 구분/앞뒷면/C/B혼입 분류/혼입 NoseR 기능 구현',
        i3.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/VSNEDU/pages/8719663107'
    """,

    # 코그넥스 도구 활용
    """
    MATCH (t1:Tool {name: '코그넥스'})
    MATCH (pr1:Process {name: 'CB 방향 구분'})
    MATCH (pr2:Process {name: '앞뒷면 구분'})
    MATCH (pr3:Process {name: 'CB 혼입 비교'})
    MATCH (pr4:Process {name: 'NoseR 측정'})
    MATCH (pr5:Process {name: '위치 검사'})
    MERGE (pr1)-[:USES_TOOL]->(t1)
    MERGE (pr2)-[:USES_TOOL]->(t1)
    MERGE (pr3)-[:USES_TOOL]->(t1)
    MERGE (pr4)-[:USES_TOOL]->(t1)
    MERGE (pr5)-[:USES_TOOL]->(t1)
    """,
]

print("=== Neo4j 그래프 적재 시작 ===")
success = 0
fail = 0

with driver.session() as session:
    for i, stmt in enumerate(CYPHER_STATEMENTS):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            result = session.run(stmt)
            result.consume()
            success += 1
        except Exception as e:
            print(f"  [오류 #{i}] {str(e)[:80]}")
            fail += 1

print(f"\n적재 완료: {success}개 성공, {fail}개 실패")

# 결과 확인
print("\n=== 그래프 통계 ===")
with driver.session() as session:
    node_count = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
    rel_count  = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
    print(f"전체 노드: {node_count}개")
    print(f"전체 관계: {rel_count}개")

    print("\n[노드 유형별]")
    for rec in session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC"):
        print(f"  {rec['label']}: {rec['cnt']}개")

    print("\n[관계 유형별]")
    for rec in session.run("MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC"):
        print(f"  {rec['rel']}: {rec['cnt']}개")

driver.close()
print("\n=== 적재 완료 ===")
