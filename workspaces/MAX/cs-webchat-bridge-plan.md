# cs-wta.com AI 채팅 ↔ cs-agent 연동 설계

작성일: 2026-04-03
승인: 부서장

---

## 1. 목표

cs-wta.com 웹 AI 채팅에서 사내 cs-agent(Claude Code 세션)를 직접 호출하여,
RAG + CS이력 기반의 고품질 답변을 웹 사용자에게 제공한다.

## 2. 현재 구조

```
웹 사용자 → cs-wta.com(AWS EC2) → 자체 PydanticAI 백엔드 → pgvector 검색 → 응답
```

## 3. 목표 구조

```
웹 사용자
  → cs-wta.com(AWS EC2) /api/v1/query
    → Cloudflare Tunnel (cs-api.mes-wta.com)
      → 사내 서버 cs-agent API (localhost:5602/api/chat)
        → cs-agent: RAG + CS이력 + AI 추론
      ← 응답 반환
    ← Tunnel 경유
  ← 웹 채팅에 표시
```

## 4. 구현 항목

### 4-1. cs-agent 측: Chat API 엔드포인트 (crafter 담당)
- cs-agent MCP 서버(5602)에 `/api/chat` HTTP POST 엔드포인트 추가
- 요청 형식:
  ```json
  {
    "query": "NC Press 29호기 알람 E-001 해결방법",
    "language": "ko",
    "equipment_id": "optional",
    "error_code": "optional",
    "message_history": [{"role": "user", "content": "..."}, ...]
  }
  ```
- 응답 형식: 기존 QueryResponse 호환
- 인증: API Key 헤더 (X-API-Key)

### 4-2. Cloudflare Tunnel 설정 (MAX/crafter 담당)
- 기존 토큰 기반 터널에 Public Hostname 추가
- 도메인: cs-api.mes-wta.com → localhost:5602
- Zero Trust Access 정책: cs-wta.com 백엔드 IP(AWS EC2)만 허용

### 4-3. cs-wta.com 백엔드 수정 (dev-agent 담당)
- /api/v1/query에서 cs-agent API 호출로 전환
- 기존 자체 PydanticAI 로직 → cs-agent 브릿지로 교체
- 타임아웃 설정 (cs-agent 응답 대기 최대 60초)
- 폴백: cs-agent 응답 실패 시 기존 자체 AI로 처리

## 5. 보안

- Cloudflare Tunnel + Zero Trust Access (IP 제한)
- API Key 인증 (cs-wta.com 백엔드만 보유)
- cs-agent 포트 직접 외부 노출 없음 (Tunnel 경유만)

## 6. 담당

| 항목 | 담당 | 비고 |
|------|------|------|
| cs-agent Chat API | crafter | MCP 서버에 엔드포인트 추가 |
| Cloudflare Tunnel | crafter | Public Hostname 추가 |
| cs-wta.com 백엔드 | dev-agent | query API 브릿지 전환 |
| 테스트/검증 | qa-agent | E2E 테스트 |
