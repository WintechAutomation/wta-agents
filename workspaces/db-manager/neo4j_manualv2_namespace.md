# Neo4j `:ManualV2` 네임스페이스 — 사전 준비 완료 문서

작성: db-manager (2026-04-12)
승인: MAX / 부서장
대상: bolt://localhost:7688 (neo4j)

## 1. 라벨 정책
- manuals-v2 파이프라인이 생성하는 **모든 노드는 `:ManualV2` 라벨 필수**
- 기존 `:PhaseOllama`, `:Phase3` 네임스페이스와 완전 분리
- 서브라벨은 기능별로 병기: `:ManualV2:Chunk`, `:ManualV2:Document`, 등

## 2. 유니크 제약 (생성 완료)
```cypher
CREATE CONSTRAINT manualv2_id IF NOT EXISTS
FOR (n:ManualV2) REQUIRE n._id IS UNIQUE;
```
- 제약 이름: `manualv2_id`
- 속성: `_id` (모든 ManualV2 노드에 필수)

## 3. `_id` 규칙
| 노드 종류 | `_id` 형식 | 예 |
|---|---|---|
| Document | `doc:{file_id}` | `doc:1_robot_2d70fa79608e` |
| Chunk | `chunk:{file_id}:{chunk_id}` | `chunk:1_robot_2d70fa79608e:0002_0004` |
| Figure | `fig:{file_id}:p{page}:{figure_id}` | `fig:1_robot_2d70fa79608e:p2:fig_002_013` |
| Table | `tbl:{file_id}:p{page}:{table_id}` | `tbl:1_robot_2d70fa79608e:p1:tbl_001_00` |
| Section | `sec:{file_id}:{section_path_hash}` | `sec:1_robot_2d70fa79608e:a1b2c3d4` |
| Entity | `ent:{type}:{normalized_name}` | `ent:component:cr750_controller` |

`section_path_hash` = `section_path` JSON을 UTF-8 직렬화한 뒤 md5 앞 12자리.
`normalized_name` = 소문자 + 공백/구두점 `_` 치환 + NFC 정규화.

## 4. 관계 타입
- `(Chunk)-[:BELONGS_TO]->(Section)`
- `(Chunk)-[:REFERENCES]->(Figure|Table)`
- `(Figure)-[:DEPICTS]->(Component)` — Entity 서브라벨
- `(Document)-[:HAS_CHUNK]->(Chunk)`
- `(Document)-[:MANUFACTURED_BY]->(Manufacturer)` — Entity 서브라벨
- `(Document)-[:DESCRIBES]->(Model)` — Entity 서브라벨

## 5. 중복 방지 — MERGE 필수
모든 삽입은 `MERGE` 사용, `CREATE` 금지.

```cypher
// Document
MERGE (d:ManualV2:Document {_id: $doc_id})
SET d += $props

// Chunk
MERGE (c:ManualV2:Chunk {_id: $chunk_id})
SET c += $props

// 관계
MATCH (d:ManualV2:Document {_id: $doc_id})
MATCH (c:ManualV2:Chunk {_id: $chunk_id})
MERGE (d)-[:HAS_CHUNK]->(c)
```

## 6. 재실행 안전성 (idempotent)
같은 `file_id`를 두 번 적재해도 노드/관계 개수는 동일해야 한다.
적재 스크립트는 반드시:
1. MERGE만 사용
2. `SET n += $props`로 속성 덮어쓰기
3. 관계는 `MERGE (a)-[:REL]->(b)` (CREATE 금지)

검증 쿼리:
```cypher
// 적재 후 카운트
MATCH (n:ManualV2) WHERE n._id STARTS WITH 'chunk:1_robot_2d70fa79608e' RETURN count(n);
```
2회 연속 적재 후 동일 값이면 통과.

## 7. 적재 전 검증 결과
```
BEFORE: PhaseOllama=384, Phase3=513
AFTER : ManualV2=0, PhaseOllama=384, Phase3=513
Total nodes: 5458 (기존 보존)
```
- `:ManualV2` 노드 0개 (제약만 선생성)
- 기존 네임스페이스 수치 완전 보존
- 제약 등록 확인: `manualv2_id` on `[ManualV2]` property `_id`

## 8. 다음 단계
1. docs-agent PoC 10건 JSONL 적재 완료 후
2. 별도 스크립트로 JSONL → Neo4j ManualV2 노드/관계 생성
3. 첫 파일 적재 후 idempotent 재실행 테스트
4. MAX에 결과 보고
