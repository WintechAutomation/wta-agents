"""
GraphRAG PoC: 4개 주제 수동 엔티티 매핑 → Neo4j 적재
대상: 장비물류(9) + 분말검사(2) + 연삭측정제어(4) + 호닝신뢰성(9)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from neo4j import GraphDatabase

env_file = Path("C:/MES/wta-agents/workspaces/research-agent/neo4j-poc.env")
for line in env_file.read_text().splitlines():
    if line.startswith("NEO4J_AUTH=neo4j/"):
        pw = line.split("/", 1)[1].strip()
        break

driver = GraphDatabase.driver("bolt://localhost:7688", auth=("neo4j", pw))

CYPHER_ALL = [

    # ================================================================
    # 주제 태그 추가 — 기존 포장혼입검사 노드에 topic 속성
    # ================================================================
    "MATCH (n) WHERE n.page_id IN ['8685453351','8719663107','8725987333','8726085635','8743878914','9485484034','9596731397'] SET n.topic = '포장혼입검사'",

    # ================================================================
    # 주제: 장비물류 (9페이지)
    # ================================================================

    # 고객
    """
    MERGE (c2:Customer {name: '교세라'})
    SET c2.alias = 'Kyocera', c2.country = '일본', c2.region = '해외'
    """,

    # 장비
    """
    MERGE (eq1:Equipment {name: '후지산기 핸들러'})
    SET eq1.type = '연삭 핸들러', eq1.manufacturer = '후지산기', eq1.topic = '장비물류'
    """,
    """
    MERGE (eq2:Equipment {name: '교세라 양면연삭 핸들러'})
    SET eq2.type = '연삭 핸들러', eq2.customer = '교세라', eq2.topic = '장비물류연삭측정제어'
    """,
    """
    MERGE (eq3:Equipment {name: 'AGV 물류 장비'})
    SET eq3.type = 'AGV', eq3.description = '자동 반송 장치, 팔레트 공급·취출 엘리베이터', eq3.topic = '장비물류'
    """,
    """
    MERGE (eq4:Equipment {name: 'ATC 장비'})
    SET eq4.type = 'ATC', eq4.description = 'Automatic Tool Changer', eq4.topic = '장비물류'
    """,

    # 공정
    """
    MERGE (pr10:Process {name: '팔레트 교체'})
    SET pr10.description = '팔레트 공급·취출 물류 교체', pr10.topic = '장비물류',
        pr10.cycle_time_100pct = '17.673s', pr10.ref_qty = 182
    """,
    """
    MERGE (pr11:Process {name: '툴 교체'})
    SET pr11.description = '금형 툴 자동 교체', pr11.topic = '장비물류',
        pr11.cycle_time_100pct = '10.98s'
    """,
    """
    MERGE (pr12:Process {name: 'ATC 작업'})
    SET pr12.description = 'ATC Tool 자동 교환 공정', pr12.topic = '장비물류'
    """,
    """
    MERGE (pr13:Process {name: 'AGV 원점 설정'})
    SET pr13.description = '엘리베이터 공급/취출 원점, 팔레트 감지센서 위치 설정',
        pr13.topic = '장비물류'
    """,

    # 부품
    """
    MERGE (comp10:Component {model: 'KP3 팔레트'})
    SET comp10.name = '팔레트', comp10.type = '팔레트', comp10.ref_customer = '한국야금',
        comp10.capacity = 182, comp10.topic = '장비물류'
    """,

    # 이슈
    """
    MERGE (iss10:Issue {page_id: '8517419053'})
    SET iss10.title = '신규 물류 개발건 이슈',
        iss10.date = '2025-01-01',
        iss10.status = '일부완료',
        iss10.symptom = '상부 카메라 간격링 누락, 팔레트 감지센서 미부착, 클램프 센서 불확실',
        iss10.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/~7120207fa205aaa3954c049293ecc72667daba/pages/8517419053',
        iss10.topic = '장비물류'
    """,
    """
    MERGE (iss11:Issue {page_id: 'WTAGRND2025-13'})
    SET iss11.title = '로딩 받침 클램프 센서 이슈',
        iss11.status = '미완료',
        iss11.symptom = '팔레트 클램핑 상태 확신 불가 (클램핑/중간 걸림 구분 불가)',
        iss11.jira_key = 'WTAGRND2025-13',
        iss11.topic = '장비물류'
    """,
    """
    MERGE (iss12:Issue {page_id: 'WTAGRND2025-8'})
    SET iss12.title = '작업위치 스토퍼 헐거움',
        iss12.status = '확인중',
        iss12.jira_key = 'WTAGRND2025-8',
        iss12.topic = '장비물류'
    """,

    # 조치방안
    """
    MERGE (res10:Resolution {id: 'R010'})
    SET res10.description = '상부 카메라 간격링 부착 조치완료',
        res10.category = '부품 누락 조치', res10.topic = '장비물류'
    """,
    """
    MERGE (res11:Resolution {id: 'R011'})
    SET res11.description = '작업위치 A/B 팔레트 감지센서 부착 완료',
        res11.category = '센서 추가', res11.topic = '장비물류'
    """,

    # 관계
    "MATCH (e:Equipment {name:'후지산기 핸들러'})(i:Issue {page_id:'8517419053'}) MERGE (e)-[:HAS_ISSUE]->(i)",
    """MATCH (e:Equipment {name:'후지산기 핸들러'}), (i:Issue {page_id:'8517419053'})
       MERGE (e)-[:HAS_ISSUE]->(i)""",
    """MATCH (i:Issue {page_id:'8517419053'}), (r:Resolution {id:'R010'})
       MERGE (i)-[:RESOLVED_BY]->(r)""",
    """MATCH (i:Issue {page_id:'8517419053'}), (r:Resolution {id:'R011'})
       MERGE (i)-[:RESOLVED_BY]->(r)""",
    """MATCH (e:Equipment {name:'교세라 양면연삭 핸들러'}), (c:Customer {name:'교세라'})
       MERGE (c)-[:OWNS]->(e)""",
    """MATCH (e:Equipment {name:'AGV 물류 장비'}), (pr:Process {name:'AGV 원점 설정'})
       MERGE (e)-[:USES_PROCESS]->(pr)""",

    # ================================================================
    # 주제: 분말검사 (2페이지)
    # ================================================================

    # 장비
    """
    MERGE (eq20:Equipment {name: 'Press-IM CELL LINE 장비'})
    SET eq20.type = '압분 검사기', eq20.customer = 'Korloy',
        eq20.description = '측면 광학계 포함 CELL LINE 검사 장비', eq20.topic = '분말검사'
    """,

    # 광학계 부품
    """
    MERGE (comp20:Component {model: '동축조명'})
    SET comp20.name = '동축조명', comp20.type = '조명', comp20.topic = '분말검사'
    """,
    """
    MERGE (comp21:Component {model: 'T-BLU'})
    SET comp21.name = '텔레센트릭 백라이트', comp21.type = '조명',
        comp21.full_name = 'Telecentric BLU', comp21.topic = '분말검사'
    """,
    """
    MERGE (comp22:Component {model: 'FlatDome'})
    SET comp22.name = 'FlatDome 조명', comp22.type = '조명',
        comp22.spec = '24V Strobe Mode 1000', comp22.topic = '분말검사'
    """,

    # 이슈
    """
    MERGE (iss20:Issue {page_id: '9004482562'})
    SET iss20.title = '측면 광학계 Burr 측정 불가',
        iss20.date = '2025-01-01',
        iss20.status = '검토중',
        iss20.symptom = '측면 광학계 동축조명·T-BLU 구성으로 Burr 측정 불가. Both부에 가려 실루엣 미시인',
        iss20.root_cause = '동축조명: Burr 경사로 미시인 / T-BLU: Both부 돌출부에 가려짐',
        iss20.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/~7120207fa205aaa3954c049293ecc72667daba/pages/9004482562',
        iss20.topic = '분말검사'
    """,
    """
    MERGE (iss21:Issue {page_id: '9061335043'})
    SET iss21.title = 'FlatDome 광량 부족 — 소성체 샘플 테스트',
        iss21.date = '2025-01-01',
        iss21.status = '검토중',
        iss21.symptom = '일반 FlatDome으로 밝기 부족, 소성체 Both부 대비 개선 필요',
        iss21.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/~7120207fa205aaa3954c049293ecc72667daba/pages/9061335043',
        iss21.topic = '분말검사'
    """,

    # 조치방안
    """
    MERGE (res20:Resolution {id: 'R020'})
    SET res20.description = 'FlatDome 미러 적용으로 광량 개선',
        res20.category = '광학계 개선', res20.topic = '분말검사'
    """,
    """
    MERGE (res21:Resolution {id: 'R021'})
    SET res21.description = '24V Strobe Mode 1000 조명 적용 (48V Strobe Mode 1000으로 광량 2배)',
        res21.category = '조명 사양 변경', res21.topic = '분말검사'
    """,
    """
    MERGE (res22:Resolution {id: 'R022'})
    SET res22.description = 'imageJ 다중 합성으로 밝기 개선 (FlatDome 여러 장 합성)',
        res22.category = '소프트웨어 처리', res22.topic = '분말검사'
    """,

    # 관계
    """MATCH (e:Equipment {name:'Press-IM CELL LINE 장비'}), (c:Customer {name:'Korloy'})
       MERGE (c)-[:OWNS]->(e)""",
    """MATCH (e:Equipment {name:'Press-IM CELL LINE 장비'}), (i:Issue {page_id:'9004482562'})
       MERGE (e)-[:HAS_ISSUE]->(i)""",
    """MATCH (e:Equipment {name:'Press-IM CELL LINE 장비'}), (i:Issue {page_id:'9061335043'})
       MERGE (e)-[:HAS_ISSUE]->(i)""",
    """MATCH (i:Issue {page_id:'9004482562'}), (i2:Issue {page_id:'9061335043'})
       MERGE (i)-[:SIMILAR_TO {similarity_score:0.90, basis:'동일 장비 동일 현상: 측면 광학계 조명 불충분', identified_by:'manual'}]->(i2)""",
    """MATCH (i:Issue {page_id:'9061335043'}), (r:Resolution {id:'R020'})
       MERGE (i)-[:RESOLVED_BY]->(r)""",
    """MATCH (i:Issue {page_id:'9061335043'}), (r:Resolution {id:'R021'})
       MERGE (i)-[:RESOLVED_BY]->(r)""",
    """MATCH (i:Issue {page_id:'9061335043'}), (r:Resolution {id:'R022'})
       MERGE (i)-[:RESOLVED_BY]->(r)""",
    """MATCH (i:Issue {page_id:'9004482562'}), (c:Component {model:'동축조명'})
       MERGE (i)-[:INVOLVES_COMPONENT]->(c)""",
    """MATCH (i:Issue {page_id:'9004482562'}), (c:Component {model:'T-BLU'})
       MERGE (i)-[:INVOLVES_COMPONENT]->(c)""",
    """MATCH (i:Issue {page_id:'9004482562'}), (c:Component {model:'FlatDome'})
       MERGE (i)-[:INVOLVES_COMPONENT]->(c)""",

    # ================================================================
    # 주제: 연삭측정제어 (4페이지)
    # ================================================================

    """
    MERGE (eq30:Equipment {name: 'WTA 양면 연삭 핸들러'})
    SET eq30.type = '연삭 핸들러', eq30.manufacturer = 'WTA',
        eq30.manual_page_id = '8705507345', eq30.topic = '연삭측정제어'
    """,

    # 그리퍼 / 축 부품
    """
    MERGE (comp30:Component {model: 'G1Z-그리퍼'})
    SET comp30.name = '그리퍼 1 Z축', comp30.type = '그리퍼', comp30.topic = '연삭측정제어'
    """,
    """
    MERGE (comp31:Component {model: 'G2Z-그리퍼'})
    SET comp31.name = '그리퍼 2 Z축', comp31.type = '그리퍼', comp31.topic = '연삭측정제어'
    """,
    """
    MERGE (comp32:Component {model: 'G3Z-그리퍼'})
    SET comp32.name = '그리퍼 3 Z축', comp32.type = '그리퍼', comp32.topic = '연삭측정제어'
    """,
    """
    MERGE (comp33:Component {model: 'CAM_Z-축'})
    SET comp33.name = '상부 카메라 Z축', comp33.type = '카메라 축', comp33.topic = '연삭측정제어'
    """,

    # 공정
    """
    MERGE (pr30:Process {name: '연삭 핸들러 원점 복귀'})
    SET pr30.description = 'X/Y/G1Z/G2Z/G3Z/CAM_Z/LO_LIFT/ULO_LIFT 축 원점 설정',
        pr30.page_id = '8705507345', pr30.topic = '연삭측정제어'
    """,
    """
    MERGE (pr31:Process {name: '비전 측정 공정'})
    SET pr31.description = '연삭 후 초음파세척 → 건조 → 비전 측정 자동화',
        pr31.page_id = '9463300099', pr31.topic = '연삭측정제어',
        pr31.requirement = '연삭기↔핸들러 공정 중단 없이 측정'
    """,
    """
    MERGE (pr32:Process {name: '초음파 세척'})
    SET pr32.description = '연삭 후 슬러지 제거, 수온 80℃ 이하 주의 (인서트 팽창 방지)',
        pr32.parent = '비전 측정 공정', pr32.topic = '연삭측정제어'
    """,

    # 관계
    """MATCH (e:Equipment {name:'WTA 양면 연삭 핸들러'}), (pr:Process {name:'연삭 핸들러 원점 복귀'})
       MERGE (e)-[:USES_PROCESS]->(pr)""",
    """MATCH (pr_parent:Process {name:'비전 측정 공정'}), (pr_child:Process {name:'초음파 세척'})
       MERGE (pr_parent)-[:HAS_SUBPROCESS]->(pr_child)""",
    """MATCH (e:Equipment {name:'WTA 양면 연삭 핸들러'}), (c:Component {model:'G1Z-그리퍼'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'WTA 양면 연삭 핸들러'}), (c:Component {model:'G2Z-그리퍼'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'WTA 양면 연삭 핸들러'}), (c:Component {model:'G3Z-그리퍼'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'WTA 양면 연삭 핸들러'}), (c:Component {model:'CAM_Z-축'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",

    # ================================================================
    # 주제: 호닝신뢰성 (9페이지)
    # ================================================================

    # 고객
    """
    MERGE (c30:Customer {name: '간저우 하이썽'})
    SET c30.country = '중국', c30.region = '해외법인'
    """,

    # 장비
    """
    MERGE (eq40:Equipment {name: '호닝 형상 검사기'})
    SET eq40.type = '검사기', eq40.description = '호닝 형상 비전 검사 장비', eq40.topic = '호닝신뢰성'
    """,
    """
    MERGE (eq41:Equipment {name: '간저우 하이썽 호닝 형상 검사기 1호기'})
    SET eq41.type = '검사기', eq41.customer = '간저우 하이썽', eq41.topic = '호닝신뢰성',
        eq41.page_id = '9266757633'
    """,

    # 부품
    """
    MERGE (comp40:Component {model: 'NA-9289'})
    SET comp40.name = '크래비스 모듈', comp40.type = 'I/O 통신 모듈',
        comp40.topic = '호닝신뢰성'
    """,
    """
    MERGE (comp41:Component {model: 'IPC-610-BTO'})
    SET comp41.name = '산업용 PC', comp41.type = 'IPC',
        comp41.manufacturer = '어드밴텍케이알(주)', comp41.topic = '호닝신뢰성'
    """,
    """
    MERGE (comp42:Component {model: '제진대'})
    SET comp42.name = '제진대', comp42.type = '진동 절연 장치', comp42.topic = '호닝신뢰성'
    """,

    # 공정
    """
    MERGE (pr40:Process {name: '호닝 형상 재현성 검증'})
    SET pr40.description = '호닝 형상 검사기 측정 재현성 검증 (C type/TNMA 제품)',
        pr40.page_id = '8277131337', pr40.topic = '호닝신뢰성'
    """,
    """
    MERGE (pr41:Process {name: '호닝 검사기 DR 회의'})
    SET pr41.description = '호닝 형상 검사기 설계 검토 회의 (2023-12-11)',
        pr41.page_id = '8315830532', pr41.topic = '호닝신뢰성',
        pr41.date = '2023-12-11'
    """,

    # 이슈
    """
    MERGE (iss40:Issue {page_id: '8350073025'})
    SET iss40.title = '크래비스 모듈 통신 불가',
        iss40.date = '2023-01-01',
        iss40.status = '조치완료',
        iss40.symptom = 'PC와 크래비스 모듈(NA-9289) 이더넷 통신 불가',
        iss40.root_cause = '모듈 자체 결함 (다른 PC에서 정상 확인, 케이블/포트 문제 아님)',
        iss40.confluence_url = 'https://iwta.atlassian.net/wiki/spaces/EKMMI/pages/8350073025',
        iss40.topic = '호닝신뢰성'
    """,
    """
    MERGE (iss41:Issue {page_id: '8277131337-C-type'})
    SET iss41.title = 'C type 제품 둔각부 오측정',
        iss41.status = '확인됨',
        iss41.symptom = 'Nose부 Teaching 후 둔각부가 위에 있을 때 둔각부를 측정지점으로 잡는 에러',
        iss41.topic = '호닝신뢰성'
    """,

    # 조치방안
    """
    MERGE (res40:Resolution {id: 'R040'})
    SET res40.description = '크래비스 모듈(NA-9289) 교체 — 모듈 자체 결함 확인 후 교체',
        res40.category = '부품 교체', res40.topic = '호닝신뢰성'
    """,
    """
    MERGE (res41:Resolution {id: 'R041'})
    SET res41.description = 'TNMA 제품 먼지 제거 후 재측정 — 오류 데이터 제외 처리',
        res41.category = '측정 절차 보완', res41.topic = '호닝신뢰성'
    """,

    # 관계
    """MATCH (c:Customer {name:'간저우 하이썽'}), (e:Equipment {name:'간저우 하이썽 호닝 형상 검사기 1호기'})
       MERGE (c)-[:OWNS]->(e)""",
    """MATCH (e:Equipment {name:'호닝 형상 검사기'}), (i:Issue {page_id:'8350073025'})
       MERGE (e)-[:HAS_ISSUE]->(i)""",
    """MATCH (i:Issue {page_id:'8350073025'}), (r:Resolution {id:'R040'})
       MERGE (i)-[:RESOLVED_BY]->(r)""",
    """MATCH (i:Issue {page_id:'8350073025'}), (c:Component {model:'NA-9289'})
       MERGE (i)-[:INVOLVES_COMPONENT]->(c)""",
    """MATCH (i:Issue {page_id:'8350073025'}), (c:Component {model:'IPC-610-BTO'})
       MERGE (i)-[:INVOLVES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'호닝 형상 검사기'}), (c:Component {model:'NA-9289'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'호닝 형상 검사기'}), (c:Component {model:'IPC-610-BTO'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'호닝 형상 검사기'}), (c:Component {model:'제진대'})
       MERGE (e)-[:USES_COMPONENT]->(c)""",
    """MATCH (e:Equipment {name:'호닝 형상 검사기'}), (pr:Process {name:'호닝 형상 재현성 검증'})
       MERGE (e)-[:USES_PROCESS]->(pr)""",

    # ================================================================
    # 크로스 주제 SIMILAR_TO 관계
    # ================================================================

    # 광학계 조명 문제: 포장혼입검사 밝기비대칭 ↔ 분말검사 측면 Burr 불가
    """
    MATCH (i1:Issue {page_id:'9485484034'}), (i2:Issue {page_id:'9004482562'})
    MERGE (i1)-[:SIMILAR_TO {
        similarity_score: 0.70,
        basis: '동일 현상 유형: 광학계 조명 불균형/미시인 → 측정 오류',
        identified_by: 'manual',
        cross_topic: true
    }]->(i2)
    """,
]

print("=== 4개 주제 그래프 적재 시작 ===")
success, fail = 0, 0

with driver.session() as session:
    for i, stmt in enumerate(CYPHER_ALL):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            result = session.run(stmt)
            result.consume()
            success += 1
        except Exception as e:
            print(f"  [오류 #{i}] {str(e)[:100]}")
            fail += 1

print(f"\n적재 완료: {success}개 성공, {fail}개 실패")

# 전체 통계
print("\n=== 전체 그래프 통계 ===")
with driver.session() as session:
    node_count = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
    rel_count  = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
    print(f"전체 노드: {node_count}개")
    print(f"전체 관계: {rel_count}개")

    print("\n[노드 유형별]")
    for rec in session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC"):
        print(f"  {rec['label']}: {rec['cnt']}개")

    print("\n[주제별 이슈 수]")
    for rec in session.run("MATCH (i:Issue) RETURN i.topic AS topic, count(i) AS cnt ORDER BY cnt DESC"):
        print(f"  {rec['topic'] or '포장혼입검사'}: {rec['cnt']}개")

    print("\n[SIMILAR_TO 관계]")
    for rec in session.run("MATCH (i1:Issue)-[s:SIMILAR_TO]->(i2:Issue) RETURN i1.title, i2.title, s.similarity_score, s.cross_topic"):
        cross = "(크로스주제)" if rec["s.cross_topic"] else ""
        print(f"  {rec['i1.title'][:35]} ↔ {rec['i2.title'][:35]} [{rec['s.similarity_score']}] {cross}")

driver.close()
print("\n=== 적재 완료 ===")
