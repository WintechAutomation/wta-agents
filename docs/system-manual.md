# WTA 네트워크/인프라 구성도

**CONFIDENTIAL — INTERNAL USE ONLY**

(주)윈텍오토메이션 생산관리팀 (AI운영팀) | 최종 업데이트: 2026-04-03

---

## 1. 서버 구성

### 사내 메인 서버 — `192.168.0.210`

| 포트 | 서비스 | 비고 |
|------|--------|------|
| :8100 | MES Go 백엔드 (Gin REST API + WebSocket) | |
| :5555 | 에이전트 대시보드 (Python Flask) | |
| :5600 | MAX 오케스트레이터 (MCP) | |
| :5601~5613 | MCP 에이전트 채널 (15명) | |
| :5612 | slack-bot (Slack Socket Mode) | |
| :8080 | upload-server (파일 업로드) | |

### AWS EC2 — `cs-wta.com`

| 포트 | 서비스 | 비고 |
|------|--------|------|
| :443 | csagent 프론트엔드 (React SPA) | |
| :8080 | csagent 백엔드 (Go API) | |
| Qdrant | 벡터DB (cs-agent 전용, 로컬dev+prod) | |

> 개발/빌드/배포 전부 dev-agent 단독 담당

### 사외 GPU 서버 — `182.224.6.147`

| 포트 | 서비스 | 비고 |
|------|--------|------|
| :11434 | Ollama API (모델 서빙) | |
| Qwen3 | Qwen3-Embedding-8B (2000차원) | |

> 부품매뉴얼 + CS이력 + WTA매뉴얼 임베딩 전용

### 사내 설계 서버 — `192.168.0.220`

| 포트 | 서비스 | 비고 |
|------|--------|------|
| :5615 | design-agent (MCP 채널) | |

> 메인 서버와 별도 머신, localhost 접근 불가

### PostgreSQL (Supabase) — `localhost:55432`

| 스키마 | 용도 | 비고 |
|--------|------|------|
| public | MES 메인 스키마 (119 페이지 데이터) | |
| csagent | CS 전용 47 테이블 (5,160건) | |
| manual | 벡터DB — documents, wta_documents, qc_documents | |
| hardware | 설비 스키마 15 테이블 | |

> 벡터 총 9.3GB+ | TLS 전송 암호화

### ERP SQL Server — `192.168.1.201:1433`

| 스키마 | 용도 | 비고 |
|--------|------|------|
| mirae | ERP 스키마 (수주, 재고, 원가, 거래처) | |
| - | **읽기전용** — SELECT만 허용 | |

> 사내망 전용, 인터넷 접근 불가 | AI INSERT/UPDATE/DELETE 금지

---

## 2. 네트워크 다이어그램

```mermaid
flowchart TB
    subgraph EXTERNAL["☁️ EXTERNAL — 인터넷"]
        WEB_USER["🌐 웹 사용자<br/>mes-wta.com / cs-wta.com"]
        SLACK_API["💬 Slack API<br/>Socket Mode (Outbound)"]
        TG_API["📱 Telegram API<br/>Bot: MAX (Polling)"]
        CLAUDE_API["🧠 Claude API<br/>Anthropic (TLS 1.3)"]
        ATLASSIAN["📋 Atlassian<br/>Jira + Confluence"]
        AWS["☁️ AWS EC2<br/>cs-wta.com"]
        GPU["🔬 사외 GPU 서버<br/>182.224.6.147 (Ollama)"]
    end

    subgraph DMZ["🔒 DMZ — Cloudflare Tunnel (암호화)"]
        T_MES["🌐 mes-wta.com<br/>→ localhost:8100"]
        T_DASH["📊 agent.mes-wta.com<br/>→ localhost:5555"]
        T_CS["🛠️ cs-api.mes-wta.com<br/>→ localhost:5602"]
        T_UPLOAD["📁 Quick Tunnel (임시)<br/>→ localhost:8080"]
    end

    subgraph INTERNAL["🏢 INTERNAL — 사내 네트워크 (192.168.0.x)"]
        MAIN["🖥️ 메인 서버 (.210)<br/>MES + 대시보드 + 에이전트 15명"]
        DESIGN["📐 설계 서버 (.220)<br/>design-agent :5615"]
        PG["🐘 PostgreSQL<br/>localhost:55432 (Supabase)"]
        ERP["🗄️ ERP SQL Server<br/>192.168.1.201 (R/O)"]
    end

    WEB_USER -->|HTTPS| T_MES
    WEB_USER -->|HTTPS| T_DASH
    AWS -->|HTTPS| T_CS
    T_MES -->|HTTP| MAIN
    T_DASH -->|HTTP| MAIN
    T_CS -->|HTTP| MAIN
    T_UPLOAD -->|HTTP| MAIN
    SLACK_API <-->|Socket Mode| MAIN
    TG_API <-->|Polling| MAIN
    CLAUDE_API <-->|TLS 1.3| MAIN
    ATLASSIAN <-->|REST API| MAIN
    MAIN -->|SQL| PG
    MAIN -->|SQL R/O| ERP
    MAIN <-->|MCP :5615| DESIGN
    GPU <-->|HTTP :11434| MAIN

    style EXTERNAL fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style DMZ fill:#FFF3E0,stroke:#E65100,stroke-width:2px,stroke-dasharray:5 5
    style INTERNAL fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    style MAIN fill:#FFEBEE,stroke:#CC0000,stroke-width:2px
```

**범례**
- 🔵 외부/인터넷
- 🟠 DMZ/Tunnel (암호화 경계)
- 🟢 사내 네트워크 (보호 영역)
- 🔴 핵심 서비스
- 🟣 데이터베이스

---

## 3. Cloudflare Tunnel 구성

### MES 터널 (Named Tunnel)

| 도메인 | 목적지 | 용도 | 타입 |
|--------|--------|------|------|
| `mes-wta.com` | `localhost:8100` | MES 프로덕션 (Go 백엔드 + React SPA) | Named |
| `agent.mes-wta.com` | `localhost:5555` | 에이전트 대시보드 (팀 현황/작업큐/모니터링) | Named |
| `cs-api.mes-wta.com` | `localhost:5602` | cs-agent API (cs-wta.com 웹채팅 연동) | Named |
| `*.trycloudflare.com` | `localhost:8080` | upload-server (파일 업로드/다운로드, 임시 URL) | Quick |

> - **Named Tunnel**: 고정 도메인 매핑, Cloudflare DNS 자동 관리
> - **Quick Tunnel**: 임시 URL, 재시작 시 변경됨

---

## 4. 외부 서비스 연동

| 서비스 | 용도 |
|--------|------|
| **Cloudflare** | DNS 관리, Tunnel (HTTPS 프록시), Zero Trust 접근제어 |
| **Slack** | Bot: WTA-AI, Socket Mode (Outbound), 채널별 AI 라우팅 |
| **Telegram** | Bot: MAX, 부서장 ↔ MAX 소통, 명령어 제어 (/stop, /start) |
| **Jira / Confluence** | 이슈 트래킹, 문서 관리, REST API 연동 |
| **Claude Code** | Anthropic API, 에이전트 15명 두뇌, TLS 1.3 / 30일 삭제 |

---

## 5. 통신 흐름도

### 흐름 1: CS 웹채팅 (cs-wta.com → 사내 cs-agent)

```mermaid
sequenceDiagram
    participant U as 🧑 웹 사용자
    participant AWS as ☁️ cs-wta.com<br/>(AWS EC2)
    participant CF as 🔒 cs-api.mes-wta.com<br/>(Cloudflare Tunnel)
    participant CS as 🛠️ mcp-agent-channel<br/>(:5602, 사내 서버)
    participant RAG as 📊 RAG 벡터검색<br/>(pgvector 9.3GB+)

    U->>AWS: 채팅 메시지 전송
    AWS->>CF: POST /api/chat (HTTPS)
    CF->>CS: 터널 통과 → ticket ID 즉시 반환
    CS-->>CF: { ticket_id: "xxx" }
    CF-->>AWS: ticket_id 응답
    AWS-->>U: ticket_id 수신, 폴링 시작

    loop 3초 간격 폴링
        U->>AWS: GET /api/chat/status/{ticket_id}
        AWS->>CF: 상태 조회
        CF->>CS: ticket 상태 확인
        CS->>RAG: 벡터 검색 + Claude 응답 생성
        RAG-->>CS: 검색 결과
        CS-->>CF: 답변 완료 시 응답 반환
        CF-->>AWS: 답변 데이터
        AWS-->>U: 답변 표시
    end

    Note over U,CS: Cloudflare 100초 타임아웃 우회를 위한<br/>비동기 ticket 기반 폴링 구조
```

> **비동기 폴링 구조 (2026-04-03 적용)**
> - cs-wta.com(AWS) → Cloudflare Tunnel → mcp-agent-channel(:5602) 로 요청
> - 서버가 ticket ID를 즉시 반환하고, 백그라운드에서 RAG 검색 + Claude 응답 생성
> - 프론트엔드는 3초 간격으로 ticket 상태를 폴링하여 답변 수신
> - Cloudflare의 100초 응답 타임아웃을 우회하기 위한 설계

### 흐름 2: 슬랙 AI 라우팅 (Slack → slack-bot → 에이전트)

```mermaid
sequenceDiagram
    participant U as 🧑 슬랙 사용자
    participant S as 💬 Slack API<br/>(Socket Mode)
    participant BOT as 🤖 slack-bot :5612<br/>(Haiku 라우팅)
    participant CH as 📡 agent-channel<br/>(MCP P2P)
    participant AG as 🛠️ 담당 에이전트
    participant SLACK as 💬 슬랙 응답

    U->>S: @WTA-AI 멘션 메시지
    S->>BOT: Socket Mode 이벤트 수신
    BOT->>BOT: Haiku로 채널/내용 분석, 담당 에이전트 결정
    BOT->>CH: send_message(to=에이전트, message=요청)
    CH->>AG: MCP 채널 메시지 전달
    AG->>AG: 요청 처리 (RAG/DB/분석 등)
    AG->>CH: send_message(to=slack-bot, message="slack:#채널 응답")
    CH->>BOT: 응답 수신
    BOT->>SLACK: files_upload_v2 또는 chat.postMessage
    SLACK->>U: 슬랙 채널에 응답 표시

    Note over BOT,AG: 채널별 라우팅 규칙:<br/>#cs→cs-agent, #부적합→nc-manager<br/>#영업→sales-agent, #docs→docs-agent<br/>#제어-*→control-agent
```

> **에이전트 간 통신 구조**
> - slack-bot이 Slack Socket Mode로 메시지 수신
> - agent-channel (MCP HTTP) 기반으로 에이전트 간 P2P 메시지 전송
> - 각 에이전트는 자체 MCP 포트(:5601~:5615)에서 메시지 대기
> - 응답은 slack-bot을 통해 원래 슬랙 채널로 회신

### 흐름 3: MES 외부 접속 (웹 → Cloudflare → 사내 백엔드)

```mermaid
sequenceDiagram
    participant U as 🧑 외부 사용자
    participant CF as 🔒 mes-wta.com<br/>(Cloudflare Tunnel)
    participant GO as 🔧 Go 백엔드 :8100<br/>(Gin REST API)
    participant PG as 🐘 PostgreSQL<br/>(:55432)
    participant ERP as 🗄️ ERP SQL Server<br/>(R/O :1433)

    U->>CF: HTTPS 요청
    CF->>GO: Tunnel → localhost:8100
    GO->>PG: MES 데이터 조회/수정
    PG-->>GO: 결과
    GO->>ERP: ERP 데이터 조회 (SELECT only)
    ERP-->>GO: 결과
    GO-->>CF: JSON 응답
    CF-->>U: HTTPS 응답

    Note over GO,ERP: ERP는 읽기전용<br/>INSERT/UPDATE/DELETE 절대 금지
```

---

## 6. 사용자별 채팅 이력 관리

### JSONL 저장 방식

cs-wta.com 웹채팅의 사용자별 대화 이력은 JSONL(JSON Lines) 형식으로 저장된다.

```mermaid
flowchart LR
    USER["🧑 웹 사용자"] -->|채팅| CSWTA["☁️ cs-wta.com"]
    CSWTA -->|API| AGENT["🛠️ cs-agent"]
    AGENT -->|append| JSONL["📄 채팅 이력<br/>JSONL 파일"]
    AGENT -->|벡터화| VDB["📊 벡터DB<br/>(추후 RAG 활용)"]

    style JSONL fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    style VDB fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
```

- 각 대화 세션은 고유 session_id로 관리
- 한 줄에 하나의 JSON 레코드 (질문, 답변, 타임스탬프, 사용자 정보)
- 누적된 이력은 CS RAG 품질 향상을 위한 학습 데이터로 활용 예정
- 저장 경로: `reports/cs-sessions.jsonl`

---

## 7. 포트 전체 목록 (메인 서버 192.168.0.210)

| 포트 | 서비스 | 프로토콜 | 접근 범위 |
|------|--------|----------|-----------|
| :8100 | MES Go 백엔드 (Gin) | HTTP/WS | Tunnel → 외부 공개 |
| :5555 | 에이전트 대시보드 (Flask) | HTTP | Tunnel → 외부 공개 |
| :5600 | MAX 오케스트레이터 | MCP HTTP | localhost 전용 |
| :5601 | cs-agent | MCP HTTP | localhost 전용 |
| :5602 | db-manager / cs-api | MCP HTTP | Tunnel → 외부 공개 |
| :5603 | dev-agent | MCP HTTP | localhost 전용 |
| :5604 | crafter | MCP HTTP | localhost 전용 |
| :5605 | admin-agent | MCP HTTP | localhost 전용 |
| :5606 | nc-manager | MCP HTTP | localhost 전용 |
| :5607 | qa-agent | MCP HTTP | localhost 전용 |
| :5608 | sales-agent | MCP HTTP | localhost 전용 |
| :5609 | issue-manager | MCP HTTP | localhost 전용 |
| :5610 | schedule-agent | MCP HTTP | localhost 전용 |
| :5611 | docs-agent | MCP HTTP | localhost 전용 |
| :5612 | slack-bot | MCP HTTP | localhost 전용 |
| :5613 | control-agent | MCP HTTP | localhost 전용 |
| :5615 | design-agent (별도 서버 .220) | MCP HTTP | 사내망 |
| :5616 | (예비) | - | - |
| :8080 | upload-server | HTTP | Quick Tunnel → 외부 |
| :55432 | PostgreSQL (Supabase) | PostgreSQL | localhost 전용 |

---

## 8. 에이전트 시스템 아키텍처

```mermaid
flowchart TB
    subgraph ORCHESTRATOR["👑 MAX — 오케스트레이터 (:5600)"]
        MAX["MAX<br/>요청 분류 · 위임 · 검증 · 보고"]
    end

    subgraph AGENTS["🤖 에이전트 팀 (MCP P2P 통신)"]
        CS["🛠️ cs-agent<br/>:5601"]
        DB["📊 db-manager<br/>:5602"]
        DEV["💻 dev-agent<br/>:5603"]
        CRAFT["🔧 crafter<br/>:5604"]
        ADMIN["📋 admin-agent<br/>:5605"]
        NC["🔍 nc-manager<br/>:5606"]
        QA["🔬 qa-agent<br/>:5607"]
        SALES["💰 sales-agent<br/>:5608"]
        ISSUE["🚨 issue-manager<br/>:5609"]
        SCHED["📅 schedule-agent<br/>:5610"]
        DOCS["📝 docs-agent<br/>:5611"]
        SLACK["💬 slack-bot<br/>:5612"]
        CTRL["⚡ control-agent<br/>:5613"]
        DESIGN["📐 design-agent<br/>:5615 (.220)"]
    end

    subgraph CHANNELS["📡 통신 채널"]
        TG["📱 Telegram<br/>부서장 ↔ MAX"]
        SL["💬 Slack<br/>직원 ↔ 에이전트"]
        WEB["🌐 cs-wta.com<br/>고객 ↔ cs-agent"]
    end

    TG <-->|명령/보고| MAX
    SL <-->|Socket Mode| SLACK
    WEB <-->|Ticket 폴링| CS

    MAX <-->|send_message| CS
    MAX <-->|send_message| DB
    MAX <-->|send_message| DEV
    MAX <-->|send_message| CRAFT
    MAX <-->|send_message| ADMIN
    MAX <-->|send_message| NC
    MAX <-->|send_message| QA
    MAX <-->|send_message| SALES
    MAX <-->|send_message| ISSUE
    MAX <-->|send_message| SCHED
    MAX <-->|send_message| DOCS
    MAX <-->|send_message| SLACK
    MAX <-->|send_message| CTRL
    MAX <-->|send_message| DESIGN

    SLACK <-->|라우팅| CS
    SLACK <-->|라우팅| NC
    SLACK <-->|라우팅| SALES
    SLACK <-->|라우팅| DOCS
    SLACK <-->|라우팅| CTRL

    style ORCHESTRATOR fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    style AGENTS fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
    style CHANNELS fill:#F3E5F5,stroke:#7B1FA2,stroke-width:1px
```

---

> 📌 이 문서는 인프라 변경 시마다 업데이트됩니다. 최종 업데이트: 2026-04-03
>
> CONFIDENTIAL — (주)윈텍오토메이션 생산관리팀 (AI운영팀)
> 네트워크 구성 변경 시 admin-agent 또는 MAX에게 업데이트 요청
