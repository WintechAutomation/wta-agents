# 슬랙 파이프라인 hub 설계 (crafter)

작성: 2026-04-06 / 대상: MAX 검토 → 부서장 보고

## 목적
웹챗의 `webChatQueues` 구조를 슬랙 멘션 응답 흐름에 적용.
에이전트 응답 → hub 상태 추적 → slack-bot 메시지 업데이트 파이프라인 구성.
점진적 응답 표시(스트리밍) + 타임아웃 안전망 + 동시요청 분리를 목표로 한다.

---

## 1. 데이터 구조

### slackRequestStates: Map<request_id, SlackRequestState>
```typescript
interface SlackRequestState {
  channel: string              // 슬랙 채널 ID (C0AP...)
  thread_ts?: string           // 스레드 ts (답글 모드)
  message_ts: string           // slack-bot이 생성한 '답변 생성 중...' 메시지 ts
  createdAt: number
  lastEventAt: number
  accumulated: string          // 누적 답변 텍스트 (chunk 합성용)
  events: SlackEvent[]         // 이벤트 로그 (디버깅/재전송)
  status: 'active' | 'completed' | 'errored' | 'expired'
  timeoutTimer: ReturnType<typeof setTimeout>
}

type SlackEvent =
  | { type: 'progress', data: string, ts: number }
  | { type: 'chunk',    data: string, ts: number }
  | { type: 'done',     data: string, ts: number }
  | { type: 'error',    data: string, ts: number }
```

---

## 2. 엔드포인트 스펙

### 2-A. POST /api/slack/init
**역할**: slack-bot이 멘션 수신 후 호출. 추적 엔트리 생성.

**Request**
```json
{
  "request_id": "sm_a1b2c3d4",
  "channel": "C0AP1D6AJHH",
  "thread_ts": "1775405000.123456",
  "message_ts": "1775405001.654321"
}
```

**Response 200**
```json
{"success": true, "request_id": "sm_a1b2c3d4"}
```

**Error**
- 400 `{"success":false,"error":"channel/message_ts required"}`
- 401 `{"success":false,"error":"Invalid API key"}`
- 409 `{"success":false,"error":"request_id already exists"}`

---

### 2-B. POST /api/slack/push
**역할**: 에이전트(cs-agent 등)가 응답 이벤트 push.

**Request**
```json
{
  "request_id": "sm_a1b2c3d4",
  "type": "progress" | "chunk" | "done" | "error",
  "data": "응답 본문 텍스트"
}
```

**Response 200**
```json
{"success": true}
```

**Error**
- 400 `"type must be progress|chunk|done|error"` / `"request_id required"`
- 401 Invalid API key
- 404 `"request_id not found"`
- 409 `"already completed"` / `"already errored"` / `"expired"`

**부가 동작**: push 성공 시 hub가 즉시 slack-bot `/api/slack/event`로 HTTP 전달 (push-through).

---

### 2-C. (옵션) GET /api/slack/state?request_id=xxx
**역할**: 디버깅/조회. 현재 상태 + 이벤트 로그 반환.

**Response 200**
```json
{
  "success": true,
  "state": {
    "request_id": "sm_a1b2c3d4",
    "channel": "C0AP1D6AJHH",
    "status": "active",
    "accumulated": "현재까지 응답 누적 내용...",
    "event_count": 3,
    "created_at": "2026-04-06T01:12:00Z",
    "last_event_at": "2026-04-06T01:12:05Z"
  }
}
```

---

## 3. 동작 플로우

```
1. 슬랙 채널 멘션 (@WTA-AI ...) 수신
2. slack-bot: 초기 메시지 "🤔 답변 생성 중..." 전송 → message_ts 획득
3. slack-bot → hub  POST /api/slack/init   (추적 엔트리 등록)
4. slack-bot → cs-agent  send_message("slack-req:sm_xxx:질문...")
5. cs-agent 처리 시작
   └ hub POST /api/slack/push (progress, "자료 조회 중...")
      └ hub → slack-bot POST /api/slack/event
         └ slack chat.update(message_ts, "🔍 자료 조회 중...")
6. cs-agent 응답 생성
   └ hub POST /api/slack/push (chunk, "답변 본문...")
      └ hub가 accumulated 누적 저장
      └ hub → slack-bot POST /api/slack/event
         └ slack chat.update(message_ts, accumulated)
7. cs-agent 완료
   └ hub POST /api/slack/push (done, "")
      └ status=completed, timer cancel
      └ hub → slack-bot POST /api/slack/event (최종)
         └ slack chat.update(message_ts, accumulated + "✅")
   └ 10초 후 slackRequestStates GC
```

---

## 4. 타임아웃 안전망

- **timeoutTimer**: 180s (웹챗 120s보다 길게 — 슬랙 멘션은 복잡한 질문 포함 가능)
- **이벤트 도착마다 reset** (idle tracking 방식)
- **만료 시 동작**:
  1. status = 'expired'
  2. hub → slack-bot `/api/slack/event` (type=error, data="응답 시간 초과(180초)")
  3. 10초 후 GC

---

## 5. hub → slack-bot 전달 (push-through)

**Endpoint**: POST http://localhost:5612/api/slack/event
**Headers**: X-API-Key (내부 인증)
**Body**
```json
{
  "request_id": "sm_a1b2c3d4",
  "type": "chunk",
  "data": "응답 본문...",
  "accumulated": "지금까지 누적된 전체 답변...",
  "channel": "C0AP1D6AJHH",
  "thread_ts": "1775405000.123456",
  "message_ts": "1775405001.654321",
  "status": "active"
}
```

**slack-bot 측 처리 (dev-agent 담당)**:
- progress → message_ts 갱신 (상태 텍스트만)
- chunk → message_ts 갱신 (accumulated 전체)
- done → message_ts 갱신 (accumulated + 완료 마커)
- error → message_ts 갱신 (에러 메시지)

**실패 정책**: slack-bot 전달 실패 시 hub 로그 기록 후 **계속 진행** (큐에는 이미 저장됨, 재전송은 slack-bot이 GET /api/slack/state로 복구 가능).

---

## 6. 웹챗 vs 슬랙 구조 비교

| 항목 | 웹챗 (webChatQueues) | 슬랙 (slackRequestStates) |
|-----|---------------------|--------------------------|
| consumer | SSE stream (browser EventSource) | slack-bot HTTP 콜백 |
| 큐잉 | items[] + waiters[] (SSE pull) | push-through 즉시 전달 |
| 상태 필드 | closed flag | status enum (active/completed/errored/expired) |
| 누적 저장 | 없음 (clients가 chunk 조립) | accumulated 필드 (서버에서 합성) |
| 타임아웃 | idle 30s / max 120s | single 180s (idle reset) |
| 메시지 흐름 | 단방향 스트림 | 초기 전송 + 반복 update |
| GC | closeQueue 후 10s | 종료(completed/errored/expired) 후 10s |

---

## 7. 동시 요청 처리

- `request_id`는 slack-bot이 생성 (형식 권장: `sm_<hash8>` 또는 `sm_<ts>_<channel3>`)
- 같은 채널/스레드에 여러 멘션 동시 발생 시에도 request_id 다르면 **독립 추적**
- slackRequestStates는 Map이므로 동시성 충돌 없음 (Bun 단일 스레드)

---

## 8. 구현 순서 (hub 측)

1. `slackRequestStates` Map + `SlackRequestState` type 추가
2. POST `/api/slack/init` (state 생성 + timer 시작)
3. POST `/api/slack/push` (accumulated 누적 + hub→slack-bot forward + timer reset)
4. 타임아웃 만료 로직 (status=expired + error forward)
5. GC 타이머 (종료 후 10s)
6. (옵션) GET `/api/slack/state`

**예상 코드 규모**: webChatQueues 확장판, 약 150~200라인 추가.

---

## 9. dev-agent 담당 범위 (협업 대상)

- slack-bot에 `POST /api/slack/event` 엔드포인트 추가
- accumulated 텍스트를 slack `chat.update` API로 반영
- hub 전달 실패 시 retry/복구 로직 (옵션: GET /api/slack/state 폴링)
- 초기 "답변 생성 중..." 메시지 생성 + init 호출

---

## 10. 오픈 이슈

1. **accumulated 누적 정책**: chunk가 "전체 답변 통째"로 오는가, "증분"으로 오는가?
   - 현재 가정: 증분(delta). chunk 데이터를 accumulated에 `+=` 합성.
   - 만약 "전체 갱신"이면 accumulated = data로 덮어쓰기 옵션 필요. cs-agent 응답 규약에 맞춰 확정 필요.

2. **멘션 없는 채널 메시지**: 현재는 `@WTA-AI` 멘션 필수. thread reply에도 동일 적용할지 확정 필요.

3. **hub→slack-bot 전달 보안**: 내부 포트(127.0.0.1:5612)이므로 X-API-Key만으로 충분. 외부 노출 시 재검토.

4. **재시작 복원력**: bun 재시작 시 slackRequestStates 소멸 → 진행 중이던 슬랙 메시지는 "응답 없음" 상태로 고아가 됨. 운영 단계에서 JSONL 저장/복원 검토 가능.

---

*연관 문서: webChatQueues 구현(`scripts/mcp-agent-channel.ts`), ontology-draft-system.md(SlackChannel 엔티티)*

---

## 11. 최종 판단 기록 (2026-04-06)

**MAX 판단: 1안 채택, hub API 보류**

- 본 문서의 `/api/slack/init`, `/api/slack/push`, `/api/slack/state` 3종 엔드포인트는 **구현하지 않음**.
- 슬랙 파이프라인은 slack-bot이 agent-channel로 수신한 이벤트를 직접 `chat.update`로 반영하는 구조(1-hop)로 확정.
- 이유: 슬랙은 `chat.update`가 hub 큐/consumer 역할을 대체하므로 hub 중계 불필요. 2-hop 회피, 구현 복잡도 절반.
- 단, 본 문서의 오픈 이슈 4건은 모두 수용:
  1. chunk 누적 = **delta(증분)** 확정
  2. thread reply = Phase 1 제외 (멘션 채널만), Phase 2 검토
  3. 인증 = hub 불개입이라 불필요
  4. 재시작 복원력 = 5분 GC만, JSONL 영속화는 Phase 2

**후속 작업**: 에이전트 ↔ slack-bot 메시지 프로토콜 표준화 문서 → `workspaces/crafter/agent-slack-protocol.md`
