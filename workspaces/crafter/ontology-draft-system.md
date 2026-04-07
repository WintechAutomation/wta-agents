# GraphRAG 온톨로지 초안 — 시스템 관점 (crafter)

작성: 2026-04-05 / 대상: MAX 통합용 / 범위: 에이전트·연동·시스템 리소스

---

## 1. 에이전트 영역

### 엔티티
- **Agent** (id, name, emoji, port, category, status)
  - 16개 인스턴스: MAX, crafter, dev-agent, db-manager, cs-agent, nc-manager, qa-agent, issue-manager, admin-agent, sales-agent, schedule-agent, control-agent, purchase-agent, design-agent, docs-agent, slack-bot, research-agent
- **SlackChannel** (id, name, purpose)
- **TaskType** (name, domain) — 예: "부적합 처리", "출하검사", "DB 조회", "문서 작성"
- **Artifact** (id, type, path, created_by) — 에이전트가 생성한 산출물 (보고서·슬라이드·스크립트 등)

### 관계
- `Agent -[OWNS]-> SlackChannel` (담당 채널)
- `Agent -[HANDLES]-> TaskType` (처리 업무 유형)
- `Agent -[PRODUCES]-> Artifact` (산출 문서/파일)
- `Agent -[REPORTS_TO]-> Agent` (팀원 → MAX 위임 체인)
- `Agent -[COLLABORATES_WITH]-> Agent` (상시 협력 관계, 예: crafter↔dev-agent, nc-manager↔qa-agent)

---

## 2. 외부 시스템 연동 영역

### 엔티티
- **Document** (id, source, title, url, modified_at) — 통합 문서 엔티티
  - ConfluencePage (space, page_id)
  - JiraIssue (project, issue_key, status, assignee)
  - MESRecord (table, pk) — 부적합/CS/프로젝트 등
  - SlackMessage (channel, ts)
- **Entity** (id, type, name) — 도메인 엔티티 (장비, 모델, 부품, 고객사, 프로젝트 등)
- **Issue** (id, type, severity, status) — 제품개선/장비/품질 이슈 단위

### 관계
- `Document -[MENTIONS]-> Entity` (문서 내 엔티티 참조)
- `Document -[REFERS_TO]-> Document` (문서 간 상호참조, 예: Jira→Confluence)
- `SlackChannel -[ROUTED_TO]-> Agent` (채널별 담당 에이전트 라우팅)
- `SlackMessage -[TRIGGERS]-> Issue` (슬랙 보고 → 이슈 생성)
- `Issue -[TRACKED_IN]-> JiraIssue` (이슈의 Jira 추적)
- `Issue -[DOCUMENTED_IN]-> ConfluencePage` (이슈 기술문서)

---

## 3. 시스템 리소스 영역

### 엔티티
- **Service** (name, version, runtime) — MES-backend, MES-frontend, cs-wta, dashboard, upload-server, slack-bot, hub(agent-channel)
- **Host** (name, ip, os, role) — localhost(Windows Server), AWS EC2(cs-wta.com), 192.168.0.220(design-agent 서버)
- **Port** (number, protocol, service) — 3100/8100(MES), 5555(dashboard), 5600~5618(agent-channel), 5612(slack-bot)
- **Tunnel** (id, provider, domain) — Cloudflare Tunnel (agent.mes-wta.com, mes-wta.com)
- **DataStore** (name, type, schema) — PostgreSQL(Supabase 55432), SQL Server(192.168.1.201, read-only), pgvector 테이블, JSONL 파일큐

### 관계
- `Service -[HOSTED_ON]-> Host`
- `Service -[LISTENS_ON]-> Port`
- `Tunnel -[ROUTES_TO]-> Service` (도메인 → 내부 서비스)
- `Service -[READS_FROM]-> DataStore` / `Service -[WRITES_TO]-> DataStore`
- `Service -[DEPENDS_ON]-> Service` (예: dashboard→hub, cs-wta→slack-bot→hub→cs-agent)
- `Agent -[CONNECTS_TO]-> Service` (에이전트↔서비스 런타임 의존)

---

## 통합 관계 요약 (크로스 도메인)

| # | 관계 체인 | 의미 |
|---|-----------|------|
| 1 | Agent → OWNS → SlackChannel → ROUTED_TO → Agent | 채널 라우팅 무결성 |
| 2 | SlackMessage → TRIGGERS → Issue → TRACKED_IN → JiraIssue → DOCUMENTED_IN → ConfluencePage | 이슈 생애주기 |
| 3 | Agent → PRODUCES → Artifact → MENTIONS → Entity | 산출물 지식그래프 |
| 4 | Tunnel → ROUTES_TO → Service → HOSTED_ON → Host → LISTENS_ON → Port | 외부 접근 경로 추적 |
| 5 | Agent → CONNECTS_TO → Service → READS_FROM → DataStore | 에이전트 데이터 접근 권한/감사 |

---

## 메모

- **Document** 엔티티는 source 필드로 소속 시스템 구분 (confluence/jira/mes/slack). GraphRAG 쿼리 시 일관된 조회 가능.
- **Entity**(도메인)는 db-manager 초안과 겹칠 가능성 높음 — MAX가 통합 시 조율 필요.
- **Agent↔Service** 관계는 crafter 담당 MES 시스템 매뉴얼(network-architecture.html)과 대응.
- 버전/상태 속성은 최소화 (온톨로지 초안 단계에서는 구조만 확정).
