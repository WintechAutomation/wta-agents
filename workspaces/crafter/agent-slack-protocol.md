# 에이전트 ↔ slack-bot 메시지 프로토콜 표준 (Phase 1)

작성: 2026-04-06 / 작성자: crafter / 승인대상: MAX → 부서장
대상: 모든 에이전트(`nc-manager`, `cs-agent`, `qa-agent`, `dev-agent`, 등 16개) + `slack-bot`
연관: slack-pipeline-design.md (MAX 1안 채택)

---

## 1. 목적
슬랙 멘션(`@WTA-AI`) 응답 파이프라인에서 에이전트들이 일관된 메시지 형식으로
slack-bot에 응답 이벤트를 전달하도록 한다. slack-bot은 수신한 이벤트를
`chat.update`로 해당 슬랙 메시지에 반영하여 점진적 스트리밍 UX를 구현한다.

---

## 2. 전송 경로

모든 메시지는 **MCP agent-channel**의 `send_message` 도구로 전달한다.
```
send_message(to="slack-bot", message="<프로토콜 문자열>")
```

- 새 엔드포인트 · HTTP 직통 호출 **금지** (agent-channel 경유만 허용)
- slack-bot이 수신한 메시지를 파싱하여 slack `chat.update` 호출

---

## 3. 메시지 형식 (5종)

### 3-A. slack-bot → 에이전트 (요청 전달)

**형식**
```
slack-req:{request_id}:{channel}:{user_query}
```

**예시**
```
slack-req:sm_a1b2c3d4:C0AP1D6AJHH:포장기 #6 밝기 비대칭 문제 알려줘
```

**필드**
| 필드 | 설명 | 예시 |
|------|------|------|
| request_id | slack-bot 생성 고유 ID | `sm_a1b2c3d4` |
| channel | 슬랙 채널 ID | `C0AP1D6AJHH` |
| user_query | 사용자 멘션 본문 (콜론 포함 가능, 마지막 세그먼트) | `포장기 #6 ...` |

**주의**: `thread_ts`, `message_ts`는 slack-bot 내부 상태(slackRequestStates)로만 관리하며 에이전트에게 전달하지 않는다. 에이전트는 request_id만으로 응답하면 된다.

---

### 3-B. 에이전트 → slack-bot (진행 상태)

**형식**
```
slack-progress:{request_id}:{상태 텍스트}
```

**예시**
```
slack-progress:sm_a1b2c3d4:🔍 벡터DB 검색 중...
slack-progress:sm_a1b2c3d4:📚 관련 문서 3건 발견, 답변 작성 중...
```

**용도**: 긴 처리 중 사용자에게 상태 표시 (optional, 권장)

**슬랙 업데이트 내용**: `상태 텍스트` 전체를 message_ts에 적용 (이전 progress 대체)

---

### 3-C. 에이전트 → slack-bot (응답 청크)

**형식**
```
slack-chunk:{request_id}:{증분 텍스트}
```

**예시**
```
slack-chunk:sm_a1b2c3d4:포장기 #6의 밝기 비대칭 문제는
slack-chunk:sm_a1b2c3d4: 조명 DOMELIGHT100의 노화가 주 원인입니다.
slack-chunk:sm_a1b2c3d4:\n\n**해결책**:\n1. 램프 교체 (예상 수명 초과 시)
```

**필드**: `증분 텍스트`는 이전 청크에 이어 **새로 생성된 부분만** 담는다.

**슬랙 업데이트 내용**: slack-bot이 accum = accum + chunk 방식으로 누적 → chat.update로 전체 반영

**delta 원칙**: 매번 전체 답변을 재전송하지 **않는다**. 네트워크·파싱 낭비 방지.

---

### 3-D. 에이전트 → slack-bot (완료)

**형식**
```
slack-done:{request_id}
```

또는 (옵션으로 최종 메타 포함)
```
slack-done:{request_id}:{완료 메시지(옵션)}
```

**예시**
```
slack-done:sm_a1b2c3d4
slack-done:sm_a1b2c3d4:✅ 답변 완료
```

**용도**: 응답 스트리밍 종료 신호. slack-bot이 완료 마커(이모지 등) 추가 가능.

**의무 사항**: 에이전트는 응답 완료 시 **반드시 slack-done을 전송**해야 한다. (누락 시 slack-bot 5분 GC 타이머로 자동 정리)

---

### 3-E. 에이전트 → slack-bot (에러)

**형식**
```
slack-error:{request_id}:{에러 사유}
```

**예시**
```
slack-error:sm_a1b2c3d4:데이터베이스 연결 실패
slack-error:sm_a1b2c3d4:질문 이해 실패 — 재입력 필요
```

**용도**: 응답 생성 실패 시 사용자에게 에러 표시.

**의무 사항**: 에러 발생 시 **반드시 slack-error 전송**. 침묵(no-response)은 금지.

**슬랙 업데이트 내용**: "⚠️ {에러 사유}" 형태로 message_ts 갱신.

---

## 4. 청크 분할 기준 (권장)

에이전트가 긴 응답을 생성할 때 적절한 단위로 청크를 끊어 전송한다.

### 권장 단위
- **문장 단위**: 한국어 `. ` / `? ` / `! ` / `\n` 기준 분할
- **문단 단위**: `\n\n` 기준 분할
- **토큰 기준**: 20~50 토큰 (대략 40~100자)마다

### 최소/최대
- 최소: 20자 이상 (너무 잦은 업데이트 방지)
- 최대: 500자 이하 (한 번에 너무 긴 청크는 분할 권장)

### 업데이트 주기
- 초당 최대 **2회** (Slack rate limit 고려 — chat.update는 분당 60회/채널 권장)

---

## 5. 에이전트 구현 예시 (의사코드)

```python
# 에이전트가 slack-req 수신 후 처리
def handle_slack_request(msg_content):
    parts = msg_content.split(":", 3)  # maxsplit=3
    _, request_id, channel, query = parts

    # 상태 전송
    send_message(to="slack-bot", message=f"slack-progress:{request_id}:🔍 자료 조회 중...")

    try:
        # LLM 스트리밍 응답
        accumulated = ""
        buffer = ""
        for delta in llm_stream(query):
            buffer += delta
            # 문장 끝 or 100자 누적 시 전송
            if buffer.endswith(('. ', '.\n', '? ', '! ')) or len(buffer) >= 100:
                send_message(to="slack-bot",
                             message=f"slack-chunk:{request_id}:{buffer}")
                accumulated += buffer
                buffer = ""

        # 남은 버퍼 flush
        if buffer:
            send_message(to="slack-bot",
                         message=f"slack-chunk:{request_id}:{buffer}")

        # 완료 신호 (필수)
        send_message(to="slack-bot", message=f"slack-done:{request_id}")

    except Exception as e:
        send_message(to="slack-bot",
                     message=f"slack-error:{request_id}:{str(e)[:200]}")
```

---

## 6. slack-bot 동작 (dev-agent 구현)

### 상태 관리
```python
# slackRequestStates (slack-bot 내부 dict)
{
  "sm_a1b2c3d4": {
    "channel": "C0AP1D6AJHH",
    "thread_ts": "",
    "message_ts": "1775405001.654321",
    "accumulated": "누적된 답변...",
    "status": "active",
    "created_at": 1775405000,
    "last_event_at": 1775405019
  }
}
```

### 수신 이벤트별 처리
| 메시지 prefix | 동작 |
|---------------|------|
| `slack-progress:` | `chat.update(message_ts, text=progress_text)` |
| `slack-chunk:` | `accumulated += chunk` → `chat.update(message_ts, text=accumulated)` |
| `slack-done:` | 완료 마커 추가 → `chat.update(message_ts, text=accumulated+"✅")` → 5분 GC 예약 |
| `slack-error:` | `chat.update(message_ts, text="⚠️ "+reason)` → status=errored → 5분 GC 예약 |

### 5분 GC
- 각 request_id마다 300s 타이머
- 만료 시 status=expired, accumulated 로그 저장 후 dict 삭제
- slack-done 수신 시 타이머 재설정(= 5분 후 GC)

---

## 7. Phase 1 범위 (확정)

**포함**:
- `@WTA-AI` 멘션 응답 (채널 직접)
- 5종 메시지 프로토콜 (req/progress/chunk/done/error)
- delta 증분 방식 청크
- slack-bot 5분 GC

**제외 (Phase 2)**:
- 스레드 답글(thread_ts) 대응
- JSONL 영속화
- 멀티 에이전트 협업 응답
- GET /api/slack/state 조회 API

---

## 8. CLAUDE.md 반영 권장 문구 (전 에이전트 공통)

아래 섹션을 `wta-agents/CLAUDE.md` 및 각 에이전트 `workspaces/{에이전트}/CLAUDE.md`에 추가:

```markdown
## 슬랙 응답 프로토콜 (Phase 1)

slack-bot으로부터 `slack-req:...` 메시지 수신 시 아래 순서로 응답:

1. 파싱: `slack-req:{request_id}:{channel}:{query}` (maxsplit=3)
2. 상태 전송(옵션): `slack-progress:{request_id}:{상태}`
3. 응답 생성 — 증분(delta) 청크로 분할:
   `slack-chunk:{request_id}:{새로 생성된 부분}`
4. 완료 시 필수: `slack-done:{request_id}`
5. 에러 시 필수: `slack-error:{request_id}:{사유}`

전송 방법: `send_message(to="slack-bot", message="...")`
금지: 전체 답변 매번 재전송(delta 원칙 위반), slack-done/error 누락.
표준 문서: `workspaces/crafter/agent-slack-protocol.md`
```

---

## 9. 다음 단계

1. MAX 검토·승인
2. dev-agent와 slack-bot 파싱 규약 최종 합의 (형식 고정 여부)
3. 전 에이전트 CLAUDE.md에 8번 섹션 추가 (admin-agent 주관)
4. Phase 1 통합 테스트 (cs-agent 선행, nc-manager 등 확대)
5. Phase 2 설계 (스레드 · 영속화 · 멀티 에이전트)
