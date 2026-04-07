# Agent Channel Push Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace agent inbox polling with MCP channel notification push, so messages arrive in Claude Code sessions instantly instead of every 3 seconds.

**Architecture:** TypeScript MCP server (like the telegram plugin) using `@modelcontextprotocol/sdk` with `experimental/claude/channel` capability. Connects to dashboard via `socket.io-client` WebSocket. Messages received from dashboard trigger `notifications/claude/channel` notification, pushing directly into Claude Code session. Slack remains via central bridge (slack-bot.py).

**Tech Stack:** TypeScript, Bun, @modelcontextprotocol/sdk, socket.io-client

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/mcp-agent-channel.ts` | Create | TypeScript MCP server with channel notification push |
| `scripts/package.json` | Create | Dependencies for TS MCP server |
| `workspaces/*/.mcp.json` (x11) | Modify | Switch command from python to bun |
| `workspaces/*/CLAUDE.md` (x11) | Modify | Update tool names and remove polling instructions |
| `scripts/mcp-wta-hub.ts` | Create | MAX hub with channel notification push |
| `.mcp.json` | Modify | Switch MAX hub to TS version |

---

### Task 1: TypeScript MCP 서버 프로젝트 설정

**Files:**
- Create: `scripts/package.json`

- [ ] **Step 1: package.json 생성**

```json
{
  "name": "wta-agent-channel",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "socket.io-client": "^4.7.0"
  }
}
```

- [ ] **Step 2: 의존성 설치**

Run: `cd C:/MES/wta-agents/scripts && bun install`
Expected: node_modules 생성, lock파일 생성

- [ ] **Step 3: Commit**

```bash
git add scripts/package.json scripts/bun.lockb
git commit -m "chore: add TS dependencies for agent channel MCP"
```

---

### Task 2: 에이전트 채널 MCP 서버 작성 (mcp-agent-channel.ts)

**Files:**
- Create: `scripts/mcp-agent-channel.ts`
- Reference: `~/.claude/plugins/cache/claude-plugins-official/telegram/0.0.1/server.ts` (notification 패턴)

- [ ] **Step 1: MCP 서버 기본 구조 작성**

`scripts/mcp-agent-channel.ts` 생성. 핵심 구조:

```typescript
#!/usr/bin/env bun
/**
 * WTA Agent Channel MCP Server
 * 에이전트 간 실시간 통신 채널 (channel notification push)
 *
 * Usage: bun mcp-agent-channel.ts <agent_id>
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'
import { io, type Socket } from 'socket.io-client'

// -- Config --
const AGENT_ID = process.argv[2]
if (!AGENT_ID) {
  process.stderr.write('Usage: bun mcp-agent-channel.ts <agent_id>\n')
  process.exit(1)
}

const DASHBOARD_URL = 'http://localhost:5555'

// -- MCP Server with channel capability --
const mcp = new Server(
  { name: `agent-channel-${AGENT_ID}`, version: '1.0.0' },
  {
    capabilities: { tools: {}, experimental: { 'claude/channel': {} } },
    instructions: [
      `이 세션은 ${AGENT_ID} 에이전트입니다.`,
      '에이전트 간 메시지는 <channel> 태그로 자동 수신됩니다.',
      'send_message 도구로 다른 에이전트에게 메시지를 보낼 수 있습니다.',
    ].join('\n'),
  },
)

// -- Dashboard Socket.IO connection --
let socket: Socket | null = null

function connectDashboard(): void {
  socket = io(DASHBOARD_URL, {
    reconnection: true,
    reconnectionDelay: 2000,
    reconnectionAttempts: Infinity,
    transports: ['websocket', 'polling'],
  })

  socket.on('connect', () => {
    process.stderr.write(`[${AGENT_ID}] dashboard connected\n`)
    // 에이전트 등록
    socket!.emit('register', { agent_id: AGENT_ID })
  })

  // 메시지 수신 → channel notification으로 세션에 푸시
  socket.on('new_message', (msg: any) => {
    // 자신에게 온 메시지만 처리
    if (msg.to !== AGENT_ID && msg.to !== 'all') return
    if (msg.from === AGENT_ID) return  // 자기 메시지 무시

    const content = msg.content || ''
    const from = msg.from || 'unknown'
    const time = msg.time || new Date().toISOString()

    void mcp.notification({
      method: 'notifications/claude/channel',
      params: {
        content: `${content}`,
        meta: {
          source: 'wta-hub',
          from,
          to: AGENT_ID,
          message_id: String(msg.id || ''),
          ts: time,
        },
      },
    })

    process.stderr.write(`[${AGENT_ID}] push: ${from} → ${content.slice(0, 60)}\n`)
  })

  socket.on('disconnect', () => {
    process.stderr.write(`[${AGENT_ID}] dashboard disconnected\n`)
  })

  socket.on('connect_error', (err: Error) => {
    process.stderr.write(`[${AGENT_ID}] connection error: ${err.message}\n`)
  })
}

// -- Heartbeat --
let heartbeatInterval: ReturnType<typeof setInterval> | null = null

function startHeartbeat(): void {
  heartbeatInterval = setInterval(() => {
    socket?.emit('heartbeat', { agent_id: AGENT_ID })
  }, 30_000)
}

// -- HTTP helper for REST API --
async function dashboardPost(path: string, data: Record<string, unknown>): Promise<any> {
  const resp = await fetch(`${DASHBOARD_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return resp.json()
}

async function dashboardGet(path: string): Promise<any> {
  const resp = await fetch(`${DASHBOARD_URL}${path}`)
  return resp.json()
}

// -- MCP Tools --
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'send_message',
      description: '에이전트 또는 슬랙에 메시지를 전송합니다.',
      inputSchema: {
        type: 'object' as const,
        properties: {
          to: {
            type: 'string',
            description: '수신자. 에이전트ID(MAX, nc-manager 등) 또는 slack-bot(슬랙 전달)',
          },
          message: { type: 'string', description: '전송할 내용' },
        },
        required: ['to', 'message'],
      },
    },
    {
      name: 'check_status',
      description: '시스템 상태를 확인합니다.',
      inputSchema: { type: 'object' as const, properties: {} },
    },
  ],
}))

mcp.setRequestHandler(CallToolRequestSchema, async (req) => {
  try {
    switch (req.params.name) {
      case 'send_message': {
        const { to, message } = req.params.arguments as { to: string; message: string }
        // WebSocket으로 전송
        if (socket?.connected) {
          socket.emit('message', {
            from: AGENT_ID,
            to,
            content: message,
            type: 'chat',
          })
          return { content: [{ type: 'text', text: `전송 완료 → ${to}` }] }
        }
        // fallback: REST API
        const result = await dashboardPost('/api/send', {
          from: AGENT_ID,
          to,
          content: message,
        })
        return {
          content: [{ type: 'text', text: `전송 완료 → ${to} (id: ${result?.id || '?'})` }],
        }
      }
      case 'check_status': {
        const result = await dashboardGet('/api/status')
        const agents = result?.agents || []
        const stats = result?.stats || {}
        const lines = [
          `온라인 ${stats.online_count || 0}/${stats.total_agents || 0}`,
          ...agents.map((a: any) =>
            `  [${a.online ? 'ON' : 'OFF'}] ${a.emoji || ''} ${a.agent_id}`
          ),
        ]
        return { content: [{ type: 'text', text: lines.join('\n') }] }
      }
      default:
        return { content: [{ type: 'text', text: `unknown tool: ${req.params.name}` }], isError: true }
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    return { content: [{ type: 'text', text: `${req.params.name} failed: ${msg}` }], isError: true }
  }
})

// -- Main --
connectDashboard()
startHeartbeat()
await mcp.connect(new StdioServerTransport())
```

- [ ] **Step 2: 실행 테스트**

Run: `cd C:/MES/wta-agents/scripts && echo '{}' | timeout 3 bun mcp-agent-channel.ts test-agent 2>&1 || true`
Expected: stderr에 "dashboard connected" 또는 "connection error" 출력 (MCP stdio 통신 시작)

- [ ] **Step 3: Commit**

```bash
git add scripts/mcp-agent-channel.ts
git commit -m "feat: add TypeScript agent channel MCP with push notifications"
```

---

### Task 3: MAX 허브도 channel notification으로 업그레이드

**Files:**
- Create: `scripts/mcp-wta-hub.ts`
- Reference: `scripts/mcp-wta-hub.py` (기존 Python 버전)

- [ ] **Step 1: MAX 전용 TypeScript 허브 작성**

`scripts/mcp-wta-hub.ts` 생성. 기존 `mcp-wta-hub.py`의 기능 + channel notification 추가.

핵심 차이점:
- `wta_recv` 도구 제거 (channel notification으로 자동 수신)
- `wta_send`, `wta_status`, `wta_search` 도구 유지
- WebSocket 연결 + new_message 이벤트 → notification push

```typescript
#!/usr/bin/env bun
/**
 * WTA Hub MCP Server (MAX용)
 * 팀원들의 메시지를 실시간으로 MAX 세션에 푸시
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import { io, type Socket } from 'socket.io-client'

const AGENT_ID = 'MAX'
const DASHBOARD_URL = 'http://localhost:5555'

const mcp = new Server(
  { name: 'wta-hub', version: '2.0.0' },
  {
    capabilities: { tools: {}, experimental: { 'claude/channel': {} } },
    instructions: [
      '팀원들의 메시지는 <channel> 태그로 자동 수신됩니다.',
      'wta_send로 팀원에게 메시지를 보내세요.',
    ].join('\n'),
  },
)

// Socket.IO + channel notification (동일 패턴)
let socket: Socket | null = null

function connectDashboard(): void {
  socket = io(DASHBOARD_URL, {
    reconnection: true,
    reconnectionDelay: 2000,
    transports: ['websocket', 'polling'],
  })

  socket.on('connect', () => {
    process.stderr.write(`[MAX] dashboard connected\n`)
    socket!.emit('register', { agent_id: AGENT_ID })
  })

  socket.on('new_message', (msg: any) => {
    if (msg.to !== AGENT_ID && msg.to !== 'all') return
    if (msg.from === AGENT_ID) return

    void mcp.notification({
      method: 'notifications/claude/channel',
      params: {
        content: `${msg.content || ''}`,
        meta: {
          source: 'wta-hub',
          from: msg.from || 'unknown',
          to: AGENT_ID,
          message_id: String(msg.id || ''),
          ts: msg.time || new Date().toISOString(),
        },
      },
    })
  })

  socket.on('disconnect', () => process.stderr.write(`[MAX] dashboard disconnected\n`))
}

// Heartbeat
setInterval(() => socket?.emit('heartbeat', { agent_id: AGENT_ID }), 30_000)

// HTTP helpers
async function post(path: string, data: any) {
  return (await fetch(`${DASHBOARD_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })).json()
}
async function get(path: string) {
  return (await fetch(`${DASHBOARD_URL}${path}`)).json()
}

// Tools: wta_send, wta_status, wta_search
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'wta_send',
      description: '팀원에게 메시지를 전송합니다.',
      inputSchema: {
        type: 'object' as const,
        properties: {
          to: { type: 'string', description: '수신 에이전트 ID (crafter, nc-manager, all 등)' },
          message: { type: 'string', description: '전송할 내용' },
        },
        required: ['to', 'message'],
      },
    },
    {
      name: 'wta_status',
      description: '전체 팀원 온라인 상태와 시스템 통계를 반환합니다.',
      inputSchema: { type: 'object' as const, properties: {} },
    },
    {
      name: 'wta_search',
      description: 'knowledge RAG 검색 (pgvector 유사도 검색)',
      inputSchema: {
        type: 'object' as const,
        properties: {
          query: { type: 'string', description: '검색 쿼리' },
          top_k: { type: 'number', description: '최대 결과 수 (기본 5)' },
        },
        required: ['query'],
      },
    },
  ],
}))

mcp.setRequestHandler(CallToolRequestSchema, async (req) => {
  try {
    switch (req.params.name) {
      case 'wta_send': {
        const { to, message } = req.params.arguments as { to: string; message: string }
        if (socket?.connected) {
          socket.emit('message', { from: AGENT_ID, to, content: message, type: 'chat' })
          return { content: [{ type: 'text', text: `전송 완료 → ${to}` }] }
        }
        const r = await post('/api/send', { from: AGENT_ID, to, content: message })
        return { content: [{ type: 'text', text: `전송 완료 → ${to} (id: ${r?.id})` }] }
      }
      case 'wta_status': {
        const r = await get('/api/status')
        const s = r?.stats || {}
        const lines = [
          `온라인 ${s.online_count || 0}/${s.total_agents || 0} | 메시지 ${s.total_messages || 0}건 | 가동 ${s.uptime || '?'}`,
          ...(r?.agents || []).map((a: any) =>
            `[${a.online ? 'ON' : 'OFF'}] ${a.emoji} ${a.agent_id} (${a.role}) | 하트비트: ${a.last_heartbeat || '-'}`
          ),
        ]
        return { content: [{ type: 'text', text: lines.join('\n') }] }
      }
      case 'wta_search': {
        const { query, top_k } = req.params.arguments as { query: string; top_k?: number }
        // RAG 검색은 임베딩 서버 + pgvector 필요 — REST fallback
        const r = await post('/api/search', { query, top_k: top_k || 5 }).catch(() => null)
        if (!r) return { content: [{ type: 'text', text: 'RAG 검색 서비스 미가동' }] }
        return { content: [{ type: 'text', text: JSON.stringify(r, null, 2) }] }
      }
      default:
        return { content: [{ type: 'text', text: `unknown: ${req.params.name}` }], isError: true }
    }
  } catch (err) {
    return { content: [{ type: 'text', text: `error: ${err}` }], isError: true }
  }
})

connectDashboard()
await mcp.connect(new StdioServerTransport())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/mcp-wta-hub.ts
git commit -m "feat: add TypeScript MAX hub MCP with push notifications"
```

---

### Task 4: 에이전트 .mcp.json 일괄 업데이트

**Files:**
- Modify: `workspaces/nc-manager/.mcp.json`
- Modify: `workspaces/db-manager/.mcp.json`
- Modify: `workspaces/cs-agent/.mcp.json`
- Modify: `workspaces/sales-agent/.mcp.json`
- Modify: `workspaces/design-agent/.mcp.json`
- Modify: `workspaces/manufacturing-agent/.mcp.json`
- Modify: `workspaces/dev-agent/.mcp.json`
- Modify: `workspaces/admin-agent/.mcp.json`
- Modify: `workspaces/crafter/.mcp.json`
- Modify: `workspaces/issue-manager/.mcp.json`
- Modify: `workspaces/qa-agent/.mcp.json`

- [ ] **Step 1: 모든 .mcp.json을 bun + TypeScript로 변경**

기존 패턴:
```json
{
  "mcpServers": {
    "agent-channel": {
      "command": "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["C:\\MES\\wta-agents\\scripts\\mcp-agent-channel.py", "nc-manager", "--slack-channel", "부적합"]
    }
  }
}
```

새 패턴:
```json
{
  "mcpServers": {
    "agent-channel": {
      "command": "C:\\Users\\Administrator\\.bun\\bin\\bun.exe",
      "args": ["C:\\MES\\wta-agents\\scripts\\mcp-agent-channel.ts", "nc-manager"]
    }
  }
}
```

참고: `--slack-channel` 인자 제거 (슬랙은 중앙 브릿지 유지)

에이전트 목록 (11개):
- nc-manager
- db-manager
- cs-agent
- sales-agent
- design-agent
- manufacturing-agent
- dev-agent
- admin-agent
- crafter
- issue-manager
- qa-agent

- [ ] **Step 2: MAX .mcp.json 업데이트**

`C:/MES/wta-agents/.mcp.json`:
```json
{
  "mcpServers": {
    "wta-hub": {
      "command": "C:\\Users\\Administrator\\.bun\\bin\\bun.exe",
      "args": ["scripts/mcp-wta-hub.ts"],
      "cwd": "C:\\MES\\wta-agents"
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add workspaces/*/.mcp.json .mcp.json
git commit -m "chore: switch all agent MCP configs to TypeScript channel server"
```

---

### Task 5: 에이전트 CLAUDE.md 업데이트

**Files:**
- Modify: `workspaces/*/CLAUDE.md` (x11)

- [ ] **Step 1: 통신 섹션 업데이트**

기존:
```markdown
## 통신 (MCP 도구)
- `inbox_wait`: 메시지 대기 (최대 60초, 메시지 오면 즉시 반환)
- `inbox_reply`: 메시지 전송 (to, message)
- `inbox_status`: 시스템 상태 확인
```

새:
```markdown
## 통신 (MCP 도구)
- 메시지 수신: 자동 (channel notification으로 <channel> 태그가 세션에 푸시됨)
- `send_message`: 메시지 전송 (to, message)
- `check_status`: 시스템 상태 확인
```

- [ ] **Step 2: 동작 규칙 업데이트**

기존:
```markdown
## 핵심 동작 규칙
1. 시작하면 inbox_reply로 MAX에게 "준비 완료" 보고
2. **inbox_wait를 반복 호출하여 메시지를 대기**
3. 메시지가 오면 처리하고 inbox_reply로 발신자에게 응답
4. 응답 후 다시 inbox_wait 호출 (무한 루프)
5. 대기 시간 초과 시에도 다시 inbox_wait 호출
```

새:
```markdown
## 핵심 동작 규칙
1. 시작하면 send_message로 MAX에게 "준비 완료" 보고
2. 메시지는 <channel> 태그로 자동 수신됨 (대기 도구 호출 불필요)
3. <channel source="wta-hub"> 메시지가 오면 처리하고 send_message로 응답
4. 슬랙 회신: send_message(to="slack-bot", message="slack:#채널명 응답내용")
```

- [ ] **Step 3: 슬랙 회신 규칙 업데이트**

기존:
```
inbox_reply(to="slack-bot", message="slack:#채널명 응답내용")
```

새:
```
send_message(to="slack-bot", message="slack:#채널명 응답내용")
```

- [ ] **Step 4: Commit**

```bash
git add workspaces/*/CLAUDE.md
git commit -m "docs: update agent CLAUDE.md for channel notification push"
```

---

### Task 6: 통합 테스트

- [ ] **Step 1: 대시보드 실행 확인**

Run: `curl -s http://localhost:5555/api/status | head -c 200`
Expected: JSON 응답 (온라인 에이전트 수 등)

- [ ] **Step 2: TypeScript MCP 서버 단독 실행 테스트**

Run: `cd C:/MES/wta-agents/scripts && timeout 5 bun mcp-agent-channel.ts test-agent 2>&1 | head -5`
Expected: stderr에 dashboard 연결 로그

- [ ] **Step 3: 에이전트 1개 시작하여 실제 통신 테스트**

Run: `cd C:/MES/wta-agents/workspaces/crafter && claude -p "send_message 도구로 MAX에게 '테스트 메시지'를 보내세요" --dangerously-skip-permissions`
Expected: 대시보드에 메시지 표시, MAX 세션에 channel notification 수신

- [ ] **Step 4: Commit (테스트 통과 시)**

```bash
git commit --allow-empty -m "test: verify agent channel push notification works"
```
