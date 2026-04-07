# 에이전트 추가 체크리스트

새 에이전트를 시스템에 추가할 때 아래 항목을 빠짐없이 수행한다.

## 1. 기본 설정

- [ ] `config/agents.json` — 에이전트 정의 추가 (id, name, emoji, role, model, port, room, enabled)
- [ ] `workspaces/{agent-id}/CLAUDE.md` — 워크스페이스 및 에이전트 지시문 생성
- [ ] `.claude/agents/{agent-id}.md` — Claude Code 서브에이전트 정의 파일 생성 (필요시)

## 2. 대시보드

- [ ] `dashboard/src/pages/TaskQueuePage.tsx` — 폴백 에이전트 목록에 추가
- [ ] `config/knowledge.json` — 운영 에이전트 수 업데이트
- [ ] `config/task-queue-check.json` — 헬스체크 대상에 추가 (port, name, emoji)

## 3. 통신 채널

- [ ] MCP agent-channel 수신자 목록에 등록 (admin-agent에게 요청)
- [ ] 슬랙 채널 라우팅 설정 (해당 채널이 있는 경우 `scripts/slack-bot.py`에 라우팅 추가)

## 4. 런처

- [ ] `scripts/launch-agents-conemu.ps1` — 모델 매핑 확인 (opusAgents / haikuAgents / sonnet 기본)
- [ ] ConEmu 레이아웃 pane 수 확인 (16개 초과 시 레이아웃 조정 필요)

## 5. 오케스트레이터 (MAX)

- [ ] `CLAUDE.md` (wta-agents) — 에이전트 참조 규칙 테이블에 추가 (키워드, 에이전트, 이모지)
- [ ] 메모리 `MEMORY.md` — 에이전트 운영 현황 업데이트

## 6. 검증

- [ ] 대시보드 프론트엔드 빌드 (`npm run build`) 성공 확인
- [ ] 에이전트 세션 시작 후 send_message 통신 테스트
- [ ] 헬스체크에서 정상 감지되는지 확인

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-02 | 초기 작성 (control-agent 추가 과정에서 누락 사례 기반) |
