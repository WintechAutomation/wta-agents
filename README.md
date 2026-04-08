# WTA Agents — AI Multi-Agent System

(주)윈텍오토메이션 전사 업무를 지원하는 AI 멀티에이전트 시스템.
Claude Code 기반 17명(오케스트레이터 1 + 팀원 16)이 텔레그램/슬랙으로 실시간 협업합니다.

## Agent Team

| Emoji | Agent | Role | Model | Category |
|-------|-------|------|-------|----------|
| 👑 | **MAX** | 총괄 오케스트레이터 — 요청 분류, 팀원 위임, 결과 검증, 보고 | Opus | 운영 |
| 🔧 | **crafter** | MES/인프라 개발, 시스템 구축, 배포 | Opus | 개발 |
| 💻 | **dev-agent** | MES 프론트엔드 개발, UI/UX 구현 | Opus | 개발 |
| ⚡ | **control-agent** | 소프트 모션제어, 전장설계, HMI, 서보 CS | Opus | 개발 |
| 📝 | **docs-agent** | 문서 작성, 매뉴얼 표준화, 번역, RAG 데이터 관리 | Opus | 운영 |
| 📊 | **db-manager** | MES/ERP/벡터DB 데이터 조회, 매뉴얼 검색 | Sonnet | 데이터 |
| 🔎 | **research-agent** | 기술 조사, 시장 분석, 리서치, 자료 수집 | Sonnet | 데이터 |
| 🛠️ | **cs-agent** | 대외 고객 CS 응대, 기술지원 | Haiku | CS |
| 💰 | **sales-agent** | 경쟁사 조사, 디자인, 특허 | Sonnet | CS |
| 📅 | **schedule-agent** | 프로젝트 납기, 셋업 일정 관리 | Sonnet | CS |
| 🔍 | **nc-manager** | 부적합 데이터 관리/분석 | Sonnet | 품질관리 |
| 🔬 | **qa-agent** | 출하검사, 품질보증, Playwright E2E 검증 | Sonnet | 품질관리 |
| 🚨 | **issue-manager** | 제품개선 이슈 트래킹 (Jira) | Sonnet | 개발 |
| 📐 | **design-agent** | 기구설계, 도면/BOM/ECN 관리 | Sonnet | 개발 |
| 📋 | **admin-agent** | 인프라 운영 모니터링, 헬스체크, 로그 관리 | Sonnet | 운영 |
| 🛒 | **purchase-agent** | 구매 발주, 입고 관리, 협력업체 관리 | Sonnet | 운영 |
| 💬 | **slack-bot** | 슬랙 메시지 게이트웨이, 채널 라우팅 | Haiku | 운영 |

## System Architecture

```
                    Telegram / Slack
                         │
                    ┌────┴────┐
                    │   MAX   │  (Orchestrator)
                    │ Opus 4  │
                    └────┬────┘
                         │ MCP agent-channel
          ┌──────┬───────┼───────┬──────┐
          │      │       │       │      │
      crafter  dev    db-mgr   cs    ...15 agents
      (Opus)  (Opus) (Sonnet) (Haiku)
          │      │       │       │
          └──────┴───────┴───────┘
                    │
     ┌──────────────┼──────────────┐
     │              │              │
  PostgreSQL    SQL Server     External
  (Supabase)   (ERP, R/O)    (Jira/Confluence)
```

### Communication

- **Telegram**: 부서장 ↔ MAX 간 지시/보고 채널
- **Slack**: 직원 ↔ AI 팀원 간 업무 채널 (채널별 담당 에이전트 라우팅)
- **MCP agent-channel**: 에이전트 간 내부 메시지 (TypeScript MCP 서버, 포트 5600~5618)

### Integrations

| Service | Purpose |
|---------|---------|
| **Jira** | 제품개선 이슈, 부적합 에스컬레이션 |
| **Confluence** | 지식베이스, RAG 파이프라인 소스 |
| **PostgreSQL (pgvector)** | 벡터DB — 매뉴얼/문서 RAG 검색 |
| **Neo4j** | GraphRAG 지식그래프 (하이브리드 검색) |
| **IMAP/SMTP (gw.wta.kr)** | 다우오피스 메일 모니터링/발송 |
| **Cloudflare Tunnel** | 대시보드 외부 접속 (agent.mes-wta.com) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Engine | Claude Code (Anthropic) — Opus 4 / Sonnet 4 / Haiku 4.5 |
| Agent Communication | MCP (Model Context Protocol) — TypeScript MCP Server |
| Dashboard | Flask + SocketIO (backend) / React + TypeScript (frontend) |
| Database | PostgreSQL 17 (Supabase, localhost:55432) |
| ERP | SQL Server (192.168.1.201:1433, read-only) |
| Slack Integration | Slack Bolt (Python) |
| Scheduler | APScheduler (대시보드 내장, jobs.json) |
| Server | Windows Server 2022 |

## Dashboard

**URL**: https://agent.mes-wta.com (Cloudflare Tunnel)

- 에이전트 실시간 상태 모니터링 (온라인/오프라인, 응답시간)
- 작업큐 관리 (할당, 진행, 완료 추적)
- 크론 스케줄 관리 (APScheduler)
- 벡터 검색 테스트
- 지식그래프 시각화 (Neo4j)
- 시스템 분석 (응답시간, 작업 통계)

## Project Structure

```
wta-agents/
├── agents/              — 에이전트 정의 (agent.md, skills/)
│   ├── MAX/
│   ├── crafter/
│   ├── dev-agent/
│   ├── db-manager/
│   ├── cs-agent/
│   └── ... (16 agents)
├── workspaces/          — 에이전트별 작업 공간
│   ├── crafter/         — CLAUDE.md + 작업 파일
│   ├── dev-agent/
│   └── ...
├── config/              — agents.json, task-queue.json, security.md
├── dashboard/           — Flask+React 대시보드 (포트 5555)
├── scripts/             — slack-bot.py, mcp-agent-channel.ts, 유틸리티
├── reports/             — 생성 문서, 일일보고, 분석 결과
├── data/                — 매뉴얼 파싱 데이터, 벡터DB 소스
├── logs/                — 에이전트 활동 로그
├── docs/                — 아키텍처, 매뉴얼
├── charter/             — 팀 헌장, 협업 규칙
└── slack_chatlog/       — 슬랙 채널별 대화 로그
```

## Key Principles

1. **모든 변경은 Git에 기록** — 에이전트 임의 수정/삭제 대비 롤백 가능
2. **에이전트 간 직접 협업** — send_message로 자유 소통, MAX는 조율 시에만 개입
3. **보안 경계** — DB 비밀번호 CLI 노출 금지, .env 기반, 외부 에이전트 민감 데이터 차단
4. **APScheduler 통일** — 모든 스케줄은 대시보드 APScheduler로만, 별도 프로세스 금지
5. **작업큐 추적** — 모든 팀원 지시는 task-queue 등록, 대시보드에서 진행 상황 추적

## Related Systems

| System | Location | Description |
|--------|----------|-------------|
| MES | C:\MES (Go + TypeScript) | 생산관리 시스템, https://mes-wta.com |
| wELEC | C:\wELEC (React + Go) | 웹 기반 전장설계 툴 (EPLAN 대체) |
| CS Website | AWS EC2 | 고객 CS 포털, https://cs-wta.com |

---

**(주)윈텍오토메이션** — 초경합금 인서트 자동화/검사/연삭 장비 전문, HIM 검사기 글로벌 1위
