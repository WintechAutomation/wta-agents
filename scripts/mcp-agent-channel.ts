#!/usr/bin/env bun
/**
 * WTA Agent Channel MCP Server (통합 — P2P)
 * 모든 에이전트(MAX 포함)가 사용하는 단일 통신 채널.
 *
 * - 자기 포트에서 HTTP 서버 → 메시지 수신 시 channel notification push
 * - send_message 도구로 상대 포트에 직접 HTTP POST
 * - check_status 도구로 모든 에이전트 ping
 * - 오프라인 큐: data/queue/{agent}.jsonl — 온라인 시 자동 전달
 * - MAX 전용: /telegram-log 엔드포인트, search_knowledge 도구
 *
 * Usage: bun mcp-agent-channel.ts <agent_id>
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'
import { mkdir, unlink } from 'node:fs/promises'
import { join } from 'node:path'
import { existsSync, readFileSync } from 'node:fs'

// ── scripts/.env 로드 (bun cwd가 워크스페이스일 수 있으므로 명시적 로드) ──
const SCRIPT_DIR = import.meta.dir
const ENV_PATH = join(SCRIPT_DIR, '.env')
if (existsSync(ENV_PATH)) {
  for (const line of readFileSync(ENV_PATH, 'utf-8').split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eqIdx = trimmed.indexOf('=')
    if (eqIdx < 0) continue
    const key = trimmed.slice(0, eqIdx).trim()
    const val = trimmed.slice(eqIdx + 1).trim()
    if (!process.env[key]) process.env[key] = val
  }
}

// ── 에이전트 포트 맵 — config/agents.json 단일 소스에서 로드 ──
import agentsConfig from '../config/agents.json'
const AGENT_PORTS: Record<string, number> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { port: number | null }).port !== null)
    .map(([id, a]) => [id, (a as { port: number }).port])
)

// ── 에이전트 호스트 맵 — host 필드가 없으면 localhost ──
const HUB_HOST: string = (agentsConfig as Record<string, unknown>)._hubHost as string || '192.168.0.219'

const AGENT_HOSTS: Record<string, string> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { port: number | null }).port !== null)
    .map(([id, a]) => [id, (a as { host?: string }).host || 'localhost'])
)

// ── 설정 ──
const AGENT_ID = process.argv[2]
if (!AGENT_ID) {
  process.stderr.write('Usage: bun mcp-agent-channel.ts <agent_id>\n')
  process.exit(1)
}

const MY_PORT = AGENT_PORTS[AGENT_ID]
if (!MY_PORT) {
  process.stderr.write(`알 수 없는 에이전트 ID: ${AGENT_ID}\n`)
  process.exit(1)
}

const IS_MAX = AGENT_ID === 'MAX'

// ── 외부 에이전트 통신 설정 ──
// 자신이 외부(host 필드 있음)이면 Cloudflare Tunnel relay 경유로 내부 에이전트에게 전송
const MY_HOST = AGENT_HOSTS[AGENT_ID] || 'localhost'
const IS_EXTERNAL = MY_HOST !== 'localhost'
const RELAY_BASE_URL = 'https://agent.mes-wta.com/api/agent-relay'
const RELAY_TOKEN = process.env.AGENT_RELAY_TOKEN || 'wta-relay-2026'

if (IS_EXTERNAL) {
  for (const [id, host] of Object.entries(AGENT_HOSTS)) {
    if (host === 'localhost') {
      AGENT_HOSTS[id] = HUB_HOST
    }
  }
}

const DASHBOARD_URL = IS_EXTERNAL ? 'https://agent.mes-wta.com' : 'http://localhost:5555'
const EMBED_URL = 'http://182.224.6.147:11434/api/embed'

const log = (msg: string) =>
  process.stderr.write(`[channel:${AGENT_ID}] ${new Date().toTimeString().slice(0, 8)} ${msg}\n`)

// ── 오프라인 큐 ──
const QUEUE_DIR = join(import.meta.dir, '..', 'data', 'queue')

async function ensureQueueDir(): Promise<void> {
  if (!existsSync(QUEUE_DIR)) {
    await mkdir(QUEUE_DIR, { recursive: true })
  }
}

async function saveToQueue(
  target: string,
  from: string,
  content: string,
  ts: string,
): Promise<void> {
  await ensureQueueDir()
  const file = join(QUEUE_DIR, `${target}.jsonl`)
  const line = JSON.stringify({ from, content, ts }) + '\n'
  const existing = existsSync(file) ? await Bun.file(file).text() : ''
  await Bun.write(file, existing + line)
  log(`큐 저장: ${target} ← ${from}: ${content.slice(0, 60)}`)
}

async function loadFromQueue(
  agentId: string,
): Promise<Array<{ from: string; content: string; ts: string }>> {
  const file = join(QUEUE_DIR, `${agentId}.jsonl`)
  if (!existsSync(file)) return []
  try {
    const text = await Bun.file(file).text()
    await unlink(file)
    return text
      .trim()
      .split('\n')
      .filter(Boolean)
      .map((line) => JSON.parse(line) as { from: string; content: string; ts: string })
  } catch {
    return []
  }
}

// ── 웹채팅 큐 (request_id → ChatQueue) ──
// SSE 스트리밍을 위한 다중 메시지 큐 구조
type ChatEvent =
  | { type: 'progress'; data: string }
  | { type: 'chunk'; data: string }
  | { type: 'done'; data: string }
  | { type: 'error'; data: string }

interface ChatQueue {
  items: ChatEvent[]
  waiters: Array<(ev: ChatEvent | null) => void>
  closed: boolean
  idleTimer: ReturnType<typeof setTimeout> | null
  maxTimer: ReturnType<typeof setTimeout> | null
  createdAt: number
}

const webChatQueues = new Map<string, ChatQueue>()

const IDLE_MS = 255_000 // 청크 사이 유휴 타임아웃 (Bun.serve idleTimeout 255s와 일치)
const MAX_MS = 600_000 // 하드 연결 한계 (10분)

function createChatQueue(requestId: string): ChatQueue {
  const q: ChatQueue = {
    items: [],
    waiters: [],
    closed: false,
    idleTimer: null,
    maxTimer: null,
    createdAt: Date.now(),
  }
  // 하드 타임아웃
  q.maxTimer = setTimeout(() => {
    if (!q.closed) {
      log(`웹채팅 큐 MAX 타임아웃: ${requestId}`)
      pushToQueue(requestId, { type: 'error', data: 'timeout: 600s hard limit reached' })
      closeQueue(requestId)
    }
  }, MAX_MS)
  webChatQueues.set(requestId, q)
  return q
}

function resetIdleTimer(requestId: string, q: ChatQueue): void {
  if (q.idleTimer) clearTimeout(q.idleTimer)
  q.idleTimer = setTimeout(() => {
    if (!q.closed) {
      log(`웹채팅 큐 IDLE 타임아웃: ${requestId}`)
      pushToQueue(requestId, { type: 'done', data: '' })
      closeQueue(requestId)
    }
  }, IDLE_MS)
}

function pushToQueue(requestId: string, ev: ChatEvent): boolean {
  const q = webChatQueues.get(requestId)
  if (!q || q.closed) return false
  if (q.waiters.length > 0) {
    const waiter = q.waiters.shift()!
    waiter(ev)
  } else {
    q.items.push(ev)
  }
  resetIdleTimer(requestId, q)
  return true
}

function closeQueue(requestId: string): void {
  const q = webChatQueues.get(requestId)
  if (!q || q.closed) return
  q.closed = true
  if (q.idleTimer) clearTimeout(q.idleTimer)
  if (q.maxTimer) clearTimeout(q.maxTimer)
  // 대기 중인 consumer 해제
  for (const w of q.waiters) w(null)
  q.waiters = []
  // GC — 메모리 누수 방지 (10초 후 제거, 늦게 도착한 메시지 무시)
  setTimeout(() => webChatQueues.delete(requestId), 10_000)
}

async function takeFromQueue(requestId: string): Promise<ChatEvent | null> {
  const q = webChatQueues.get(requestId)
  if (!q) return null
  if (q.items.length > 0) return q.items.shift()!
  if (q.closed) return null
  return new Promise<ChatEvent | null>((resolve) => {
    q.waiters.push(resolve)
  })
}

// ── 메시지 큐 (notification 누락 시 회수용) ──
const messageQueue: Array<{ from: string; content: string; ts: string }> = []
let waitResolve: ((msg: { from: string; content: string; ts: string }) => void) | null = null

function enqueueMessage(from: string, content: string, ts: string): void {
  if (waitResolve) {
    const resolve = waitResolve
    waitResolve = null
    resolve({ from, content, ts })
  } else {
    messageQueue.push({ from, content, ts })
  }
}

// ── MCP 서버 ──
const mcp = new Server(
  { name: `agent-channel-${AGENT_ID}`, version: '3.0.0' },
  {
    capabilities: { tools: {}, experimental: { 'claude/channel': {} } },
    instructions: [
      `이 세션은 ${AGENT_ID} 에이전트입니다.`,
      '에이전트 간 메시지는 <channel source="wta-hub"> 태그로 자동 수신됩니다.',
      'send_message 도구로 다른 에이전트에게 메시지를 보낼 수 있습니다.',
      '슬랙 회신: send_message(to="slack-bot", message="slack:#채널명 내용")',
    ].join('\n'),
  },
)

// ── HTTP 서버 ──
function startHttpServer(): void {
  Bun.serve({
    port: MY_PORT,
    idleTimeout: 255, // SSE long-polling (Bun 최대값, heartbeat 15s로 유지)
    async fetch(req) {
      const url = new URL(req.url)

      // 헬스체크 + 파일 큐 로드
      if (url.pathname === '/ping' && req.method === 'GET') {
        const fromFile = await loadFromQueue(AGENT_ID)
        for (const msg of fromFile) {
          enqueueMessage(msg.from, msg.content, msg.ts)
        }
        if (fromFile.length > 0) {
          log(`ping 시 대기 메시지 ${fromFile.length}건 로드`)
        }
        return Response.json({ agent_id: AGENT_ID, online: true })
      }

      // 텔레그램 인바운드 메시지 로깅 (MAX 전용)
      if (IS_MAX && url.pathname === '/telegram-log' && req.method === 'POST') {
        const msg = (await req.json()) as {
          from: string
          content: string
          direction: 'inbound' | 'outbound'
        }
        const from = msg.direction === 'inbound' ? msg.from : AGENT_ID
        const to = msg.direction === 'inbound' ? AGENT_ID : msg.from
        fetch(`${DASHBOARD_URL}/api/send`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ from, to, content: msg.content }),
          signal: AbortSignal.timeout(2000),
        }).catch(() => {})
        log(`텔레그램 로그 (${msg.direction}): ${msg.content.slice(0, 60)}`)
        return Response.json({ ok: true })
      }

      // CORS preflight
      if (req.method === 'OPTIONS') {
        return new Response(null, {
          status: 204,
          headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
            'Access-Control-Max-Age': '86400',
          },
        })
      }

      // 웹채팅 API (POST /api/chat)
      if (url.pathname === '/api/chat' && req.method === 'POST') {
        // API Key 인증
        const apiKey = req.headers.get('X-API-Key') || ''
        const expectedKey = process.env.CS_API_KEY || ''
        if (!expectedKey || apiKey !== expectedKey) {
          return Response.json(
            { success: false, error: 'Invalid API key' },
            { status: 401, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        let data: {
          query: string
          language?: string
          equipment_id?: string
          error_code?: string
          message_history?: Array<{ role: string; content: string }>
        }
        try {
          data = (await req.json()) as typeof data
        } catch {
          return Response.json(
            { success: false, error: 'Invalid JSON' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        const query = data.query?.trim()
        if (!query) {
          return Response.json(
            { success: false, error: 'query is required' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        const requestId = crypto.randomUUID().slice(0, 8)
        createChatQueue(requestId)

        // cs-agent 세션에 channel notification push
        const chatPayload = JSON.stringify({
          type: 'web-chat',
          request_id: requestId,
          query,
          language: data.language || 'ko',
          equipment_id: data.equipment_id || null,
          error_code: data.error_code || null,
          message_history: data.message_history || [],
        })

        try {
          await mcp.notification({
            method: 'notifications/claude/channel',
            params: {
              content: `[web-chat:${requestId}] ${chatPayload}`,
              meta: {
                source: 'web-chat',
                from: 'web-user',
                to: AGENT_ID,
                message_id: requestId,
                ts: new Date().toISOString(),
              },
            },
          })
        } catch (err) {
          log(`웹채팅 notification 실패: ${(err as Error).message}`)
        }

        enqueueMessage('web-chat', `[web-chat:${requestId}] ${chatPayload}`, new Date().toISOString())
        log(`웹채팅 요청 (sync): ${requestId} - ${query.slice(0, 80)}`)

        // 큐에서 chunk/done 이벤트 수집 (backward compat: 단일 문자열로 합성)
        const corsHeaders = { 'Access-Control-Allow-Origin': '*' }
        const chunks: string[] = []
        let errored: string | null = null
        while (true) {
          const ev = await takeFromQueue(requestId)
          if (ev === null) break
          if (ev.type === 'chunk') chunks.push(ev.data)
          else if (ev.type === 'done') {
            if (ev.data) chunks.push(ev.data)
            closeQueue(requestId)
            break
          } else if (ev.type === 'error') {
            errored = ev.data
            closeQueue(requestId)
            break
          }
          // progress는 sync API에서 무시
        }

        if (errored) {
          return Response.json(
            { success: false, error: errored, request_id: requestId },
            { status: 500, headers: corsHeaders },
          )
        }
        const response = chunks.join('')
        if (response) {
          return Response.json(
            { success: true, request_id: requestId, response },
            { headers: corsHeaders },
          )
        }
        return Response.json(
          { success: false, error: 'cs-agent no response', request_id: requestId },
          { status: 504, headers: corsHeaders },
        )
      }

      // 웹채팅 SSE 초기화 (POST /api/chat/init)
      if (url.pathname === '/api/chat/init' && req.method === 'POST') {
        const apiKey = req.headers.get('X-API-Key') || ''
        const expectedKey = process.env.CS_API_KEY || ''
        if (!expectedKey || apiKey !== expectedKey) {
          return Response.json(
            { success: false, error: 'Invalid API key' },
            { status: 401, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        let data: {
          request_id?: string
          query: string
          language?: string
          equipment_id?: string
          error_code?: string
          message_history?: Array<{ role: string; content: string }>
        }
        try {
          data = (await req.json()) as typeof data
        } catch {
          return Response.json(
            { success: false, error: 'Invalid JSON' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        const query = data.query?.trim()
        if (!query) {
          return Response.json(
            { success: false, error: 'query is required' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        const requestId = data.request_id || crypto.randomUUID().slice(0, 8)
        createChatQueue(requestId)

        const chatPayload = JSON.stringify({
          type: 'web-chat',
          request_id: requestId,
          query,
          language: data.language || 'ko',
          equipment_id: data.equipment_id || null,
          error_code: data.error_code || null,
          message_history: data.message_history || [],
        })

        try {
          await mcp.notification({
            method: 'notifications/claude/channel',
            params: {
              content: `[web-chat:${requestId}] ${chatPayload}`,
              meta: {
                source: 'web-chat',
                from: 'web-user',
                to: AGENT_ID,
                message_id: requestId,
                ts: new Date().toISOString(),
              },
            },
          })
        } catch (err) {
          log(`웹채팅 init notification 실패: ${(err as Error).message}`)
        }

        enqueueMessage('web-chat', `[web-chat:${requestId}] ${chatPayload}`, new Date().toISOString())
        log(`웹채팅 요청 (sse): ${requestId} - ${query.slice(0, 80)}`)

        return Response.json(
          { success: true, request_id: requestId },
          { headers: { 'Access-Control-Allow-Origin': '*' } },
        )
      }

      // 웹채팅 producer push (POST /api/chat/push)
      // slack-bot 등 MCP 없는 외부 서버가 큐에 이벤트를 직접 push
      if (url.pathname === '/api/chat/push' && req.method === 'POST') {
        const apiKey = req.headers.get('X-API-Key') || ''
        const expectedKey = process.env.CS_API_KEY || ''
        if (!expectedKey || apiKey !== expectedKey) {
          return Response.json(
            { success: false, error: 'Invalid API key' },
            { status: 401, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        let body: { request_id?: string; type?: string; data?: string }
        try {
          body = (await req.json()) as typeof body
        } catch {
          return Response.json(
            { success: false, error: 'Invalid JSON' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        const requestId = body.request_id || ''
        const evType = body.type || ''
        const data = body.data ?? ''

        if (!requestId) {
          return Response.json(
            { success: false, error: 'request_id is required' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }
        if (evType !== 'progress' && evType !== 'chunk' && evType !== 'done' && evType !== 'error') {
          return Response.json(
            { success: false, error: 'type must be progress|chunk|done|error' },
            { status: 400, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        const q = webChatQueues.get(requestId)
        if (!q) {
          return Response.json(
            { success: false, error: 'request_id not found' },
            { status: 404, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }
        if (q.closed) {
          return Response.json(
            { success: false, error: 'queue already closed' },
            { status: 409, headers: { 'Access-Control-Allow-Origin': '*' } },
          )
        }

        pushToQueue(requestId, { type: evType as ChatEvent['type'], data })
        log(`웹채팅 push ${evType}: ${requestId} (${data.length}자)`)
        if (evType === 'done' || evType === 'error') {
          closeQueue(requestId)
        }

        return Response.json(
          { success: true },
          { headers: { 'Access-Control-Allow-Origin': '*' } },
        )
      }

      // 웹채팅 SSE 스트림 (GET /api/chat/stream?request_id=xxx)
      if (url.pathname === '/api/chat/stream' && req.method === 'GET') {
        const requestId = url.searchParams.get('request_id') || ''
        if (!requestId || !webChatQueues.has(requestId)) {
          return new Response('request_id not found', {
            status: 404,
            headers: { 'Access-Control-Allow-Origin': '*' },
          })
        }

        const encoder = new TextEncoder()
        const stream = new ReadableStream({
          async start(controller) {
            // 즉시 헤더 flush + 연결 확인용 초기 comment
            try {
              controller.enqueue(encoder.encode(`: connected\n\n`))
            } catch {
              // noop
            }
            const heartbeat = setInterval(() => {
              try {
                controller.enqueue(encoder.encode(`: ping\n\n`))
                // SSE consumer 활성 상태이므로 큐 idle 타이머도 연장
                const q = webChatQueues.get(requestId)
                if (q && !q.closed) resetIdleTimer(requestId, q)
              } catch {
                clearInterval(heartbeat)
              }
            }, 15_000)

            const send = (event: string, data: string): void => {
              try {
                controller.enqueue(encoder.encode(`event: ${event}\ndata: ${data}\n\n`))
              } catch {
                // controller closed
              }
            }

            const formatPayload = (ev: ChatEvent): string => {
              // 다중 필드 지원: data (legacy) + event-specific alias
              if (ev.type === 'chunk') {
                return JSON.stringify({ data: ev.data, content: ev.data })
              }
              // progress / done / error
              return JSON.stringify({ data: ev.data, message: ev.data })
            }

            try {
              while (true) {
                const ev = await takeFromQueue(requestId)
                if (ev === null) {
                  send('done', JSON.stringify({ data: '', message: 'stream closed' }))
                  break
                }
                send(ev.type, formatPayload(ev))
                if (ev.type === 'done' || ev.type === 'error') {
                  closeQueue(requestId)
                  break
                }
              }
            } finally {
              clearInterval(heartbeat)
              try {
                controller.close()
              } catch {
                // already closed
              }
            }
          },
          cancel() {
            // 클라이언트 연결 종료 시 — 큐는 유지 (cs-agent가 계속 push할 수 있음)
            log(`SSE 클라이언트 연결 종료: ${requestId}`)
          },
        })

        return new Response(stream, {
          headers: {
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            Connection: 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
          },
        })
      }

      // 메시지 수신
      if (url.pathname === '/message' && req.method === 'POST') {
        const msg = (await req.json()) as {
          from: string
          to: string
          content: string
          ts?: string
        }
        const ts = msg.ts || new Date().toISOString()

        // channel notification → Claude Code 세션에 push
        try {
          await mcp.notification({
            method: 'notifications/claude/channel',
            params: {
              content: msg.content,
              meta: {
                source: 'wta-hub',
                from: msg.from,
                to: AGENT_ID,
                message_id: String(Date.now()),
                ts,
              },
            },
          })
          log(`channel notification push 성공: ${msg.from}`)
        } catch (err) {
          log(`channel notification push 실패: ${(err as Error).message}`)
        }

        enqueueMessage(msg.from, msg.content, ts)
        log(`수신: ${msg.from} → ${msg.content.slice(0, 80)}`)

        return Response.json({ ok: true })
      }

      return new Response('Not Found', { status: 404 })
    },
    error(err) {
      log(`HTTP 오류: ${err.message}`)
      return new Response('Error', { status: 500 })
    },
  })
  log(`HTTP 서버 시작 (포트 ${MY_PORT})`)
}

// ── msg_type 허용값 (B+, 2026-04-12) ──
const ALLOWED_MSG_TYPES = new Set([
  'report_complete',
  'report_progress',
  'report_blocked',
  'reply',
  'request',
])

// 대시보드에 메시지 로깅 (fire-and-forget)
function logToDashboard(
  to: string,
  message: string,
  msgType: string = 'reply',
  taskId?: string,
): void {
  const body: Record<string, unknown> = {
    from: AGENT_ID,
    to,
    content: message,
    msg_type: msgType,
  }
  if (taskId) body.task_id = taskId
  fetch(`${DASHBOARD_URL}/api/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(2000),
  }).catch(() => {})
}

// ── 메시지 전송 (오프라인 시 큐 저장) ──
async function sendMessage(
  to: string,
  message: string,
  msgType: string = 'reply',
  taskId?: string,
): Promise<string> {
  const targets =
    to === 'all'
      ? Object.keys(AGENT_PORTS).filter((id) => id !== AGENT_ID)
      : [to]

  const results = await Promise.all(
    targets.map(async (target) => {
      const port = AGENT_PORTS[target]
      if (!port) return `알 수 없는 에이전트: ${target}`
      const host = AGENT_HOSTS[target] || 'localhost'

      // 외부 에이전트 → 내부 에이전트: Cloudflare relay 경유
      const useRelay = IS_EXTERNAL && host === HUB_HOST
      const pingUrl = useRelay
        ? `${RELAY_BASE_URL}/${target}`  // relay는 ping 대신 직접 전송 시도
        : `http://${host}:${port}/ping`
      const messageUrl = useRelay
        ? `${RELAY_BASE_URL}/${target}`
        : `http://${host}:${port}/message`
      const relayHeaders: Record<string, string> = useRelay
        ? { 'Content-Type': 'application/json', 'X-Relay-Token': RELAY_TOKEN }
        : { 'Content-Type': 'application/json' }

      // 포트 온라인 여부 먼저 확인 (relay 경유 시 ping 스킵, 직접 전송)
      let isOnline = false
      if (useRelay) {
        isOnline = true  // relay는 대시보드가 내부 포트로 전달하므로 ping 불필요
      } else {
        try {
          await fetch(pingUrl, { signal: AbortSignal.timeout(1000) })
          isOnline = true
        } catch {
          isOnline = false
        }
      }

      if (isOnline) {
        try {
          await fetch(messageUrl, {
            method: 'POST',
            headers: relayHeaders,
            body: JSON.stringify({
              from: AGENT_ID,
              to: target,
              content: message,
              ts: new Date().toISOString(),
              msg_type: msgType,
              ...(taskId ? { task_id: taskId } : {}),
            }),
            signal: AbortSignal.timeout(useRelay ? 30000 : 3000),
          })
          log(`전송: → ${target}: ${message.slice(0, 80)}${useRelay ? ' (relay)' : ''}`)
          return `전송 완료 → ${target} (온라인${useRelay ? ', relay 경유' : ''})`
        } catch {
          // 전송 실패 → 큐 저장
          const ts = new Date().toISOString()
          await saveToQueue(target, AGENT_ID, message, ts)
          log(`전송 실패 → ${target}, 큐 저장${useRelay ? ' (relay 실패)' : ''}`)
          return `전송 완료 → ${target} (오프라인 - 큐에 저장됨, 온라인 시 자동 전달)`
        }
      } else {
        // 오프라인 → 파일 큐에 저장
        const ts = new Date().toISOString()
        await saveToQueue(target, AGENT_ID, message, ts)
        log(`오프라인 → ${target}, 큐 저장`)
        return `전송 완료 → ${target} (오프라인 - 큐에 저장됨, 온라인 시 자동 전달)`
      }
    }),
  )

  logToDashboard(to, message, msgType, taskId)
  return results.join('\n')
}

// ── 상태 확인 ──
async function checkStatus(): Promise<string> {
  const results = await Promise.all(
    Object.entries(AGENT_PORTS).map(async ([id, port]) => {
      const host = AGENT_HOSTS[id] || 'localhost'
      try {
        await fetch(`http://${host}:${port}/ping`, {
          signal: AbortSignal.timeout(1000),
        })
        return `[ON ] ${id} (${host}:${port})`
      } catch {
        return `[OFF] ${id} (${host}:${port})`
      }
    }),
  )
  const online = results.filter((r) => r.startsWith('[ON')).length
  return [`시스템: 온라인 ${online}/${Object.keys(AGENT_PORTS).length}`, '', ...results].join('\n')
}

// ── MCP 도구 정의 ──
mcp.setRequestHandler(ListToolsRequestSchema, async () => {
  const tools = [
    {
      name: 'send_message',
      description:
        '에이전트 또는 슬랙에 메시지를 전송합니다. 오프라인 시 큐에 저장되어 온라인 시 자동 전달됩니다. ' +
        '슬랙 회신: to="slack-bot", message="slack:#채널명 내용". ' +
        'msg_type 규칙(2026-04-12): report_complete/report_progress/report_blocked(task_id 필수), ' +
        'reply(기본), request(새 작업 지시).',
      inputSchema: {
        type: 'object' as const,
        properties: {
          to: {
            type: 'string',
            description:
              '수신자 에이전트ID (MAX, nc-manager, db-manager, cs-agent, ' +
              'sales-agent, design-agent, manufacturing-agent, dev-agent, ' +
              'admin-agent, crafter, issue-manager, qa-agent, slack-bot, all)',
          },
          message: { type: 'string', description: '전송할 내용' },
          msg_type: {
            type: 'string',
            enum: [
              'report_complete',
              'report_progress',
              'report_blocked',
              'reply',
              'request',
            ],
            description:
              '메시지 타입. report_complete/progress/blocked는 task_id 필수. 기본값 reply.',
          },
          task_id: {
            type: 'string',
            description: '작업큐 task_id. report_* 유형일 때 필수.',
          },
        },
        required: ['to', 'message'],
      },
    },
    {
      name: 'check_status',
      description: '시스템 상태 (온라인 에이전트)를 확인합니다.',
      inputSchema: {
        type: 'object' as const,
        properties: {},
      },
    },
    {
      name: 'wait_for_channel',
      description:
        '메시지를 대기합니다. 대기 중 channel notification으로 메시지가 자동 수신됩니다. ' +
        '대기 시간이 끝나면 다시 호출하여 세션을 유지하세요.',
      inputSchema: {
        type: 'object' as const,
        properties: {
          seconds: {
            type: 'number',
            description: '대기 시간(초). 기본 120초. 최대 300초.',
          },
        },
      },
    },
  ]

  // MAX + cs-agent: knowledge RAG 검색
  if (IS_MAX || AGENT_ID === 'cs-agent') {
    tools.push({
      name: 'search_knowledge',
      description:
        'knowledge RAG 검색. pgvector 유사도 검색으로 사내 지식 문서를 검색합니다.',
      inputSchema: {
        type: 'object' as const,
        properties: {
          query: { type: 'string', description: '검색 쿼리 (한국어/영어)' },
          top_k: {
            type: 'number' as const,
            description: '반환할 최대 결과 수 (기본 5)',
          },
        },
        required: ['query'],
      },
    })
  }

  return { tools }
})

// ── MCP 도구 실행 ──
mcp.setRequestHandler(CallToolRequestSchema, async (req) => {
  try {
    switch (req.params.name) {
      case 'send_message': {
        const {
          to,
          message,
          msg_type: msgType = 'reply',
          task_id: taskId,
        } = req.params.arguments as {
          to: string
          message: string
          msg_type?: string
          task_id?: string
        }

        if (!ALLOWED_MSG_TYPES.has(msgType)) {
          throw new Error(
            `잘못된 msg_type=${msgType}. 허용값: ${[...ALLOWED_MSG_TYPES].sort().join(', ')}`,
          )
        }
        if (msgType.startsWith('report_') && !taskId) {
          throw new Error(`msg_type=${msgType}에는 task_id가 필수입니다.`)
        }

        // 웹채팅 응답 라우팅
        // 형식: web-chat:{id} (chunk) / web-chat:{id}:progress / web-chat:{id}:done / web-chat:{id}:error
        if (to.startsWith('web-chat:')) {
          const parts = to.split(':')
          const requestId = parts[1]
          const suffix = parts[2] || 'chunk'

          let evType: ChatEvent['type']
          if (suffix === 'progress') evType = 'progress'
          else if (suffix === 'done') evType = 'done'
          else if (suffix === 'error') evType = 'error'
          else evType = 'chunk'

          const q = webChatQueues.get(requestId)
          if (!q) {
            return {
              content: [
                {
                  type: 'text',
                  text: `웹채팅 요청 ID를 찾을 수 없음: ${requestId} (타임아웃 또는 이미 종료)`,
                },
              ],
            }
          }
          if (q.closed) {
            return {
              content: [
                { type: 'text', text: `웹채팅 큐 이미 종료됨: ${requestId}` },
              ],
            }
          }
          pushToQueue(requestId, { type: evType, data: message })
          log(`웹채팅 ${evType}: ${requestId} (${message.length}자)`)
          if (evType === 'done' || evType === 'error') {
            closeQueue(requestId)
          }
          return {
            content: [
              {
                type: 'text',
                text: `웹채팅 ${evType} 전송 완료 (request_id: ${requestId})`,
              },
            ],
          }
        }

        const result = await sendMessage(to, message, msgType, taskId)
        return { content: [{ type: 'text', text: result }] }
      }

      case 'check_status': {
        const result = await checkStatus()
        return { content: [{ type: 'text', text: result }] }
      }

      case 'wait_for_channel': {
        const { seconds = 120 } = (req.params.arguments as { seconds?: number }) || {}
        const wait = Math.min(Math.max(seconds, 10), 300)
        log(`대기 시작: ${wait}초`)

        // 파일 큐에서 미전달 메시지 로드
        const fromFile = await loadFromQueue(AGENT_ID)
        for (const msg of fromFile) {
          enqueueMessage(msg.from, msg.content, msg.ts)
        }

        // 큐에 메시지가 있으면 전부 즉시 반환
        if (messageQueue.length > 0) {
          const msgs = messageQueue.splice(0, messageQueue.length)
          const text = msgs.map((m) => `[${m.from}] ${m.content}`).join('\n\n')
          log(`인박스: ${msgs.length}건 반환`)
          return { content: [{ type: 'text', text }] }
        }

        // 없으면 메시지 도착 또는 타임아웃까지 대기
        const msg = await Promise.race([
          new Promise<{ from: string; content: string; ts: string }>((resolve) => {
            waitResolve = resolve
          }),
          new Promise<null>((resolve) => setTimeout(() => resolve(null), wait * 1000)),
        ])

        if (msg) {
          log(`메시지 수신으로 대기 종료: ${msg.from}`)
          return {
            content: [{ type: 'text', text: `[${msg.from}] ${msg.content}` }],
          }
        }

        waitResolve = null
        log(`대기 시간 초과: ${wait}초`)
        return {
          content: [
            {
              type: 'text',
              text: `${wait}초 대기 완료 (수신 없음). 다시 wait_for_channel을 호출하여 대기하세요.`,
            },
          ],
        }
      }

      case 'search_knowledge': {
        if (!IS_MAX && AGENT_ID !== 'cs-agent') {
          return {
            content: [{ type: 'text', text: 'search_knowledge는 MAX/cs-agent 전용입니다.' }],
            isError: true,
          }
        }
        const { query, top_k = 5 } = req.params.arguments as {
          query: string
          top_k?: number
        }

        let embedding: number[]
        try {
          const resp = await fetch(EMBED_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: 'qwen3-embedding:8b', input: [query] }),
            signal: AbortSignal.timeout(5000),
          })
          const embedResult = (await resp.json()) as { embeddings?: number[][] }
          if (!embedResult.embeddings?.length) {
            return {
              content: [{ type: 'text', text: '임베딩 생성 실패: 응답에 embeddings 없음' }],
            }
          }
          embedding = embedResult.embeddings[0]
        } catch (err) {
          return {
            content: [{ type: 'text', text: `임베딩 서버 오류: ${err}` }],
          }
        }

        return {
          content: [
            {
              type: 'text',
              text: `RAG 검색 준비됨 (임베딩 ${embedding.length}차원, top_k=${top_k}). pgvector 직접 연결 구현 필요.`,
            },
          ],
        }
      }

      default:
        return {
          content: [{ type: 'text', text: `알 수 없는 도구: ${req.params.name}` }],
          isError: true,
        }
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    return {
      content: [{ type: 'text', text: `${req.params.name} 실패: ${msg}` }],
      isError: true,
    }
  }
})

// ── 기존 포트 점유 프로세스 강제 종료 ──
async function killExistingPort(): Promise<void> {
  try {
    const proc = Bun.spawnSync({
      cmd: ['cmd', '/c', `for /f "tokens=5" %a in ('netstat -ano ^| findstr ":${MY_PORT}" ^| findstr "LISTEN"') do taskkill /F /PID %a`],
      stderr: 'pipe',
      stdout: 'pipe',
    })
    const out = proc.stdout.toString().trim()
    if (out && !out.includes('not found')) {
      log(`기존 포트 ${MY_PORT} 프로세스 종료: ${out.slice(0, 80)}`)
      // 포트 해제 대기
      await new Promise(r => setTimeout(r, 500))
    }
  } catch {
    // 점유 프로세스 없으면 무시
  }
}

// ── 메인 ──
await killExistingPort()
startHttpServer()

// 시작 시 오프라인 중 쌓인 큐 메시지 로드
const pendingOnStart = await loadFromQueue(AGENT_ID)
for (const msg of pendingOnStart) {
  enqueueMessage(msg.from, msg.content, msg.ts)
}
if (pendingOnStart.length > 0) {
  log(`시작 시 대기 메시지 ${pendingOnStart.length}건 로드`)
}

await mcp.connect(new StdioServerTransport())
