---
name: project_multiagent_plan
description: wta-agents 멀티에이전트 시스템 초기 구축 계획 - 5개 에이전트(orchestrator, mes-data, nc-manager, cs-agent, reporter) + 4개 스킬 문서 + 메모리 파이프라인
type: project
---

wta-agents 멀티에이전트 시스템 구축 계획 수립 완료 (2026-03-26).

**Why:** 사장님(생산부서장)이 12개 팀 업무를 AI 에이전트로 자동화하려는 목적. Claude Code 네이티브 에이전트 시스템 활용.

**How to apply:**
- 에이전트 정의는 `.claude/agents/*.md` (frontmatter 형식)
- 스킬은 실행 파일이 아닌 참조 문서 (`skills/*.md`)
- MES 레포(`C:/MES/.claude/agents/`)와 wta-agents 레포는 분리 유지
- DB 접근은 Bash에서 psql/sqlcmd CLI 사용, 연결 정보는 .env 참조
- ERP는 절대 READ-ONLY
- 에이전트 간 직접 통신 금지, 오케스트레이터 경유
