# Slack 라우팅 파이프라인 업그레이드 설계 (slack-bot 측)

작성: dev-agent
일자: 2026-04-05
상태: 초안 (crafter 설계 완료 대기)

## 배경

웹챗에 적용된 신규 파이프라인(`webchat-req/chunk/done` 마커 + hub `/api/chat/push`)의 설계를 슬랙 채널 멘션 라우팅에도 확장한다. 현재 슬랙 멘션은 1회성 `send_message` → `send_to_agent` 방식으로 완성본 1회만 편집(chat.update)되어 긴 답변 대기 시간이 길고 사용자 체감이 나쁘다. 이를 progressive edit 방식으로 전환한다.

**적용 1순위 채널**: #cs, #부적합, #개발

## 목표

- 사용자가 멘션 직후 "답변 생성 중..." 플레이스홀더 즉시 확인
- 에이전트 응답이 청크 단위로 들어올 때마다 해당 메시지 편집(chat.update)하여 실시간 진행감 제공
- 종료/오류 마커로 최종 상태 확정

## 프로토콜 (신규 마커)

### slack-bot → 에이전트 발송
```
slack-req:{request_id}:{channel_id}:{user_query}
```
- request_id: slack-bot 발급 8자리 hex (uuid4 앞 8자)
- channel_id: 슬랙 채널 ID (C... 또는 D...)
- user_query: 사용자 멘션 텍스트 (봇 멘션 토큰 제거 후)

### 에이전트 → slack-bot 회신
```
slack-chunk:{id}:{text}        # 1회 또는 여러 번
slack-done:{id}                # 종료 마커 (필수)
slack-error:{id}:{reason}      # 오류 시 chunk 대체
```

## 상태 테이블

```python
_slack_pipeline_sessions: dict[str, dict] = {
    # request_id → session 정보
    # {
    #   "channel_id": "C0AQZ9RH8BS",
    #   "ts": "1775405350.000100",     # 슬랙 메시지 timestamp
    #   "accum": "",                    # 누적 청크 텍스트
    #   "target_agent": "cs-agent",
    #   "created_at": 1775405351.0,
    #   "done": False,
    # }
}
_slack_pipeline_lock = threading.Lock()
```

- 10분 이상 미완료(done=False) 세션은 별도 GC 스레드로 청소

## 처리 흐름 (slack-bot)

### 1) 멘션 수신 → 세션 시작
```
[slack_bolt @app.event("app_mention")] 또는 기존 메시지 핸들러
  ↓
request_id = uuid4().hex[:8]
  ↓
chat.postMessage(channel, "⏳ {emoji} 답변 생성 중...")
  → ts 획득
  ↓
_slack_pipeline_sessions[request_id] = { channel_id, ts, accum:"", target_agent, ... }
  ↓
send_to_agent(target_agent, f"slack-req:{request_id}:{channel_id}:{query}")
```

### 2) 에이전트 응답 수신 (`/message` 핸들러 확장)
```python
# 기존 webchat-* 파서 다음에 추가
if content.startswith(("slack-chunk:", "slack-done:", "slack-error:")):
    _slack_pipeline_handle(content, sender)
    return ack
```

### 3) 청크별 메시지 편집
```python
def _slack_pipeline_handle(content, sender):
    parts = content.split(":", 2)
    marker, req_id, rest = parts[0], parts[1], parts[2] if len(parts)>2 else ""
    sess = _slack_pipeline_sessions.get(req_id)
    if not sess: return

    if marker == "slack-chunk":
        sess["accum"] += rest
        # debounce: 최근 update 이후 0.8초 경과 또는 누적 120자 증가 시만 chat.update
        _throttled_update(req_id)
    elif marker == "slack-done":
        # 누적된 나머지 flush + 최종 렌더
        _final_update(req_id, final_text=sess["accum"])
        sess["done"] = True
    elif marker == "slack-error":
        _final_update(req_id, final_text=f"⚠️ 오류: {rest}")
        sess["done"] = True
```

### 4) chat.update throttling
- 최소 간격 800ms (슬랙 rate limit 보호)
- 또는 누적 120자 증가 시 즉시 업데이트
- 최종 done 이벤트 시 무조건 1회 업데이트

## `/api/slack/push` (crafter 신설 예정) 연동 여부

**1안 (권장): slack-bot 직접 chat.update 호출**
- 에이전트 → slack-bot(5612) /message 로 마커 전송 (기존 경로 그대로)
- slack-bot이 Slack Web API (chat.update) 직접 호출
- hub 불필요, 구조 단순
- slack-bot은 이미 Slack Bolt 클라이언트 보유 → chat.update 사용 가능

**2안: hub `/api/slack/push` 경유**
- 에이전트 → slack-bot → hub /api/slack/push 호출 → hub가 slack-bot을 다시 트리거?
- 2-hop 구조, 실익 불명확

**결론**: 1안 기본. hub API는 향후 외부 시스템(대시보드 등)에서 슬랙으로 push 해야 할 때 별도 설계.

## 마이그레이션 전략

### 단계 1 — 프로토콜만 추가, 기존 동작 유지
- slack-bot에 `slack-*` 마커 파서 + 세션 관리 구현
- 기존 멘션 핸들러는 그대로 두고, **feature flag**(예: `SLACK_PIPELINE_V2_CHANNELS`)로 채널별 on/off

### 단계 2 — 1순위 채널 활성화
- #cs, #부적합, #개발 채널만 feature flag on
- 해당 채널 담당 에이전트(cs-agent, nc-manager, dev-agent) CLAUDE.md에 신규 프로토콜 추가

### 단계 3 — 전체 확대
- 잔여 채널 순차 적용

## 에이전트 CLAUDE.md 업데이트 필요 항목

각 담당 에이전트(cs-agent, nc-manager, dev-agent 등)에 추가:

```markdown
## 슬랙 채널 응답 — 신규 파이프라인 (progressive edit)

`slack-req:{id}:{channel}:{query}` 마커 수신 시:

1. 답변을 청크 단위(문단/문장)로 생성하며 각 청크마다 즉시 전송:
   send_message(to="slack-bot", message="slack-chunk:{id}:{텍스트 조각}")

2. 답변 완료 후 종료 마커:
   send_message(to="slack-bot", message="slack-done:{id}")

3. 오류 시: slack-error:{id}:{사유}

주의: chunk 텍스트에는 줄바꿈/콜론 포함 가능. slack-bot이 3번째 콜론 이후 전체를 텍스트로 처리.
짧은 답변은 chunk 1회 + done으로 충분.
```

## 관측/로그

- `[slack-pipe] req {id} ch={channel} agent={target}` — 세션 시작
- `[slack-pipe] chunk {id} (+{n}b, total {m}b)` — 청크 도착
- `[slack-pipe] update {id} ts={ts} size={len}` — chat.update 호출
- `[slack-pipe] done {id} total={m}b duration={t}s` — 종료

## 리스크

| 리스크 | 완화 |
|-------|-----|
| Slack chat.update rate limit (초당 20req/workspace) | throttle 800ms + 누적 120자 단위 |
| 긴 답변 편집 실패(4000자 제한) | chunk 도착 시 길이 체크, 초과 시 Block Kit 분할 또는 "(이어서)" 새 메시지 |
| 에이전트가 done 보내지 않음 | 5분 GC, 그 시점 수동 "(응답 미종료)" 표시 |
| request_id 충돌 | uuid4 8자리, 세션 만료 10분으로 사실상 비충돌 |
| 멘션 밖 응답 혼입(잘못된 마커) | req_id 조회 실패 시 drop + warning 로그 |

## 작업 범위 추정

| 항목 | 예상 |
|-----|-----|
| slack-bot 세션 상태 관리 + 마커 파서 | 100~150 LOC |
| chat.update throttle 로직 | 30~50 LOC |
| feature flag + 채널별 on/off | 20 LOC |
| 멘션 핸들러 분기 개조 | 기존 핸들러 수정 ~50 LOC |
| 에이전트 CLAUDE.md 업데이트 (ch당 1개) | 채널당 ~20줄 |
| GC 스레드 | 30 LOC |
| **합계** | **slack-bot 약 280 LOC + 담당 에이전트 3건 CLAUDE.md** |

## 테스트 시나리오

1. 짧은 답변(chunk 1회): 즉시 완료, 편집 2회(플레이스홀더→최종)
2. 긴 답변(chunk 5회 이상): throttle 동작, 편집 3~4회
3. 동시 2건 요청(다른 채널): 세션 독립 보장
4. 에이전트 done 누락: 5분 후 GC 메시지 노출
5. slack API 429: 재시도 backoff
6. 잘못된 req_id 수신: drop 확인

## crafter 협업 체크포인트

- [ ] hub `/api/slack/push` 엔드포인트 필요성 재확인 (현 설계는 불필요 판단)
- [ ] 에이전트 측 신규 프로토콜 문서 공유
- [ ] feature flag 환경변수 네이밍 합의
- [ ] 1순위 채널 3개 활성화 일정 조율

## 오픈 이슈

- slack-bot 재시작 시 세션 상태 전부 소실 → 웹챗과 달리 슬랙은 `ts` 기반이므로 재조회 가능하지만 복구 로직은 별도 설계
- 긴 답변 thread reply로 분할할지(가독성) vs 단일 메시지 계속 편집할지(단순성): 단일 메시지 편집을 기본으로, 4000자 초과 시 thread reply 추가

## 다음 단계

1. crafter 설계 문서 수신 후 `/api/slack/push` 사용 여부 최종 확정
2. 본 문서 MAX 승인 → 구현 착수
3. cs-agent CLAUDE.md 선행 업데이트 → #cs 채널부터 단계적 롤아웃
