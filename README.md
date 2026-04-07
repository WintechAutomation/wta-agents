# WTA Agents — 멀티에이전트 시스템

WTA 전사 업무를 지원하는 AI 에이전트 시스템.
Claude Code 기반, 텔레그램 통신, Git 버전 관리.

## 구조

```
wta-agents/
├── agents/              — 에이전트 정의 (역할, 규칙, 스킬)
│   ├── orchestrator/    — 관리자 에이전트 (오케스트레이터)
│   ├── nc-manager/      — 부적합 관리 에이전트
│   └── cs-agent/        — CS 에이전트
├── memory/              — 에이전트 메모리
│   ├── short-term/      — 단기 기억 (일자별)
│   └── long-term/       — 장기 기억 (중요 내용)
├── charter/             — 팀 헌장, 협업 규칙
├── logs/                — 활동 기록 (자동 커밋)
├── docs/                — 설계 문서, 아키텍처
└── config/              — 설정, 권한, 보안 경계
```

## 원칙

1. **모든 변경은 Git에 기록** — 에이전트의 임의 수정/삭제 대비 롤백 가능
2. **메모리 카테고리 엄수** — 단기/장기/규칙/학습 분리, 혼합 금지
3. **보안 경계** — 외부 에이전트는 민감 데이터 접근 차단
4. **사람이 병목이 되지 않는 구조** — 관리자 에이전트가 서브에이전트를 감독

## 인프라

- **플랫폼**: Claude Code (Anthropic)
- **통신**: 텔레그램 (봇 API)
- **데이터**: PostgreSQL (Supabase), ERP (SQL Server, 읽기 전용)
- **배포**: 사내 서버 (Windows Server 2022)
- **외부**: AWS EC2 (cs-wta.com)
