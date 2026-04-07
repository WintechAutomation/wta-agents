# cs-wta.com AI 채팅 SSE 스트리밍 전환 설계서

작성: dev-agent, 2026-04-05
대상: MAX 승인 → crafter 핸드오프

## 배경 / 문제

현재 `mcp-agent-channel.ts`의 `webChatPending` Map은 one-shot Promise 구조. cs-agent가 동일 requestId로 `send_message` 2회 이상 호출하면 첫 호출만 웹에 전달되고 나머지는 소실됨 (부서장 2026-04-05 장애 보고).

## 목표

- cs-agent가 여러 번에 걸쳐 진행상황/답변을 push 가능
- 웹 사용자에게 실시간 중간 피드백 제공
- Cloudflare 터널/nginx 환경에서 안정 동작

---

## 1. SSE 이벤트 스키마

MIME: `text/event-stream`

| event | 송신 시점 | payload (JSON) | 클라이언트 처리 |
|-------|-----------|----------------|-----------------|
| `open` | 연결 직후 1회 | `{"request_id": "<uuid8>"}` | 세션 식별 |
| `progress` | 진행상황 알림 (선택) | `{"message": "자료 검색 중..."}` | 로딩 텍스트 교체 |
| `chunk` | 본 답변 조각 | `{"content": "...", "seq": 1}` | 답변 버블에 append |
| `meta` | 참고자료/모델 정보 | `{"sources":[...],"model_used":"..."}` | 사이드 카드에 렌더 |
| `done` | 최종 종료 | `{}` | 스트림 종료, 로딩 해제 |
| `error` | 오류 | `{"code":"TIMEOUT","message":"..."}` | 에러 UI 표시 |
| `ping` | keepalive (20s 주기) | `{}` | 무시 |

**규칙:**
- 첫 `chunk` 도착 시 클라이언트는 빈 answer 버블 생성 → 이후 `chunk.content` 누적
- `done` 받기 전 연결 끊기면 재연결 금지 (Idempotency 없음, 사용자 재질문 유도)
- `ping`은 Cloudflare 100초 idle timeout 회피용

---

## 2. EC2 cs-backend SSE 엔드포인트

**신규 엔드포인트:**
```
POST /api/v1/chat/stream
Content-Type: application/json
Authorization: Bearer <JWT>

{
  "query": "...",
  "language": "ko",
  "equipment_id": "...",
  "error_code": "...",
  "message_history": [{"role":"user","content":"..."}, ...]
}

Response: 200 OK, Content-Type: text/event-stream
```

**구현 (FastAPI):**
```python
from fastapi.responses import StreamingResponse
import httpx

@router.post("/stream")
async def chat_stream(req: ChatStreamRequest, user=Depends(get_current_user)):
    async def event_gen():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{SLACK_BOT_URL}/api/chat-stream",
                json=req.model_dump(),
                headers={"X-API-Key": CS_API_KEY},
            ) as resp:
                async for line in resp.aiter_lines():
                    yield line + "\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

**동작:**
- EC2 FastAPI는 slack-bot `/api/chat-stream` SSE를 그대로 pass-through
- JWT 인증은 EC2에서만 확인, slack-bot 호출은 기존 X-API-Key 재사용
- 응답을 DB에 저장하려면 stream 완료 후 별도 처리 (아래 §5 참고)

---

## 3. slack-bot 측 요구사항 (crafter 작업)

**요청 엔드포인트 (신규):**
```
POST http://slack-bot:5612/api/chat-stream
Content-Type: application/json
X-API-Key: <CS_API_KEY>

{ "query": "...", "language": "ko", "equipment_id": "...", "error_code": "...", "message_history": [...] }

Response: text/event-stream (SSE 무한 스트림)
```

**구현 요구:**
1. 요청 수신 시 `requestId` 발급 후 mcp-agent-channel의 SSE 엔드포인트 호출 (GET `/api/chat/stream?request_id=...`)
2. mcp-agent-channel의 SSE를 그대로 클라이언트에 pass-through
3. 20초마다 `event: ping\ndata: {}\n\n` 전송 (Cloudflare keepalive)

**간소화 옵션:** slack-bot을 단순 패스스루 프록시로 유지. 모든 큐잉/done 로직은 mcp-agent-channel.ts에 집중.

---

## 4. mcp-agent-channel.ts 측 요구사항 (crafter 작업)

**데이터 구조 변경:**
```typescript
// 기존
webChatPending: Map<requestId, { resolve, timer }>

// 신규
webChatStreams: Map<requestId, {
  queue: Array<{event: string, data: object}>,  // 대기 중인 이벤트
  subscribers: Set<(evt) => void>,               // SSE 클라이언트
  lastMessageAt: number,                          // idle 감지
  timer: NodeJS.Timeout,                          // 최대 연결 시간
  done: boolean
}>
```

**신규 엔드포인트:**
```
GET /api/chat/stream?request_id=<uuid>
Response: text/event-stream
```

**send_message 라우팅 변경:**
- `to = "web-chat:{id}"` 수신 시 → 즉시 resolve 대신 `queue.push({event:"chunk", data:{content: message}})` + subscribers에 broadcast + `lastMessageAt` 갱신
- `to = "web-chat:{id}:done"` 수신 시 → `queue.push({event:"done", data:{}})` + 연결 종료 시그널
- idle 타임아웃 (마지막 chunk 이후 **3초 (MAX 승인)** 무응답) → 자동 done 이벤트 전송 후 종료
- 전체 타임아웃 (요청 후 **300초**) → error 이벤트 + 종료

**기존 동기 `/api/chat` 유지** (하위 호환, 첫 send_message만 반환)

---

## 5. 프론트엔드 Chat.tsx 변경 (dev-agent 작업)

**EventSource 대신 fetch + ReadableStream:**
- EventSource는 GET만 지원 → POST body 전송 불가
- fetch + ReadableStream.getReader() + TextDecoder로 SSE 파싱

```typescript
async function streamChat(req: QueryRequest, handlers: {
  onChunk: (content: string) => void,
  onMeta: (meta: object) => void,
  onDone: () => void,
  onError: (err: string) => void,
}) {
  const resp = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop()!;
    for (const raw of events) parseEvent(raw, handlers);
  }
}
```

**UI 처리:**
- 첫 `chunk` 수신 시 history에 임시 entry 추가, answer="" 시작
- 이후 `chunk`마다 마지막 entry의 answer에 append (setState 업데이트)
- `meta`로 sources/model_used 반영
- `done`으로 isLoading=false, chat_history 저장 API 호출 (기존 saveChatEntry)

**DB 저장 타이밍:** stream 완료 후 전체 answer를 `POST /chat-history/save` 한 번에 저장 (지금과 동일).

---

## 6. cs-agent 측 규칙 (MAX 공지 필요)

응답 완료 시 반드시 다음 두 가지 중 하나 수행:
1. 명시적 종료: `send_message(to="web-chat:{request_id}:done", message="")`
2. 암묵적 종료: 마지막 chunk 이후 3초 무응답 → 자동 done (권장: 명시적 done)

진행상황 전달 (선택):
- `send_message(to="web-chat:{request_id}", message="...")` — 중간 상태도 chunk로 전달됨

---

## 7. 작업 순서

1. **[dev-agent, 지금]** 본 설계서 제출 → MAX 검토
2. **[crafter]** mcp-agent-channel.ts SSE 엔드포인트 + 큐 구조 구현
3. **[crafter]** slack-bot.py `/api/chat-stream` 패스스루 추가
4. **[dev-agent]** cs-backend `/api/v1/chat/stream` 엔드포인트 추가
5. **[dev-agent]** Chat.tsx streamChat 전환
6. **[MAX]** cs-agent 응답 규칙 공지
7. **통합 테스트**: cs-wta.com 로그인 → 질문 → progress+chunk+done 순차 수신 확인
8. **#csdev 슬랙 알림 + 부서장 보고**

---

## 8. 위험요소

- **Cloudflare 버퍼링**: nginx/Cloudflare가 SSE를 버퍼링하면 실시간성 상실 → nginx에 `proxy_buffering off; proxy_cache off; X-Accel-Buffering: no` 헤더 필요
- **JWT 만료**: 긴 연결 중 토큰 만료 시 중간 재인증 불가 → 요청 시점 토큰으로 전체 스트림 유지
- **다중 탭**: 사용자가 여러 탭 열면 cs-agent에 동시 요청 부담 → 큐 수용량 고려

---

## 9. 하위 호환

기존 `POST /api/v1/query` 및 slack-bot `/api/chat`은 유지. 점진적으로 Chat.tsx만 stream 사용하도록 전환. 문제 발생 시 롤백 가능.
