# cs-wta.com 개발 가이드 (공용)

cs-wta.com 웹사이트 개발 시 참조하는 공용 정보.
어떤 에이전트든 이 문서를 읽고 바로 작업 가능하도록 정리.

## 경로

| 항목 | 경로 |
|------|------|
| 소스코드 (로컬) | `D:\csagent` |
| 프론트엔드 소스 | `D:\csagent\frontend\src` |
| 백엔드 소스 | `D:\csagent\backend` |
| 배포 설정 | `D:\csagent\deploy` |
| 설계 문서 | `D:\csagent\PROJECT_OVERVIEW.md` |
| CLAUDE.md | `D:\csagent\CLAUDE.md` |

> **주의**: `C:\MES\csagent`는 MES 프로젝트이며 cs-wta.com과 무관.

## 기술 스택

- **Frontend**: React 19, TypeScript, Vite, shadcn/ui, Tailwind CSS
- **Backend**: Python (FastAPI), PydanticAI
- **DB**: PostgreSQL (CS 이력, 출하 현황)
- **Vector DB**: PostgreSQL pgvector (manual.documents, csagent.vector_embeddings 테이블)
- **배포**: AWS EC2, Docker Compose
- **도메인**: cs-wta.com

## 프론트엔드 구조

```
D:\csagent\frontend\src\
├── App.tsx
├── main.tsx
├── api/          — API 호출
├── components/   — 공통 컴포넌트
├── contexts/     — React Context
├── i18n/         — 다국어
├── pages/        — 페이지 컴포넌트
├── types/        — 타입 정의
└── utils/        — 유틸리티
```

## 배포

- EC2 접속: SSH 키 `C:\Users\Administrator\.ssh`
- Docker Compose: `D:\csagent\deploy\docker-compose.cloud.yml`
- 프론트엔드 빌드 → dist → Nginx 서빙

## 개발 서버

- 프론트엔드: `http://localhost:5173` (Vite dev server)
- 백엔드 API: `http://localhost:8001` (프록시 `/api` → 8001)

## 역할 분담

- **dev-agent**: 프론트엔드 + 백엔드 개발, 빌드, EC2 배포 (단독 담당)
- **cs-agent**: 도메인 지식, RAG 파이프라인, 데이터 모델 설계 (개발 업무 없음)
- **crafter**: cs-wta.com 관여 없음 (인프라 정보는 dev-agent에게 이관 완료)
