// 에이전트 관제센터 (NOC 스타일) — React + CSS/SVG
import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'
import { io } from 'socket.io-client'
import agentsConfig from '@agents'

// ── 토큰 사용량 타입 ──────────────────────────────────────────
interface UsageData {
  tokens_used: number
  tokens_limit: number
  cost: number
  period: string
  updated_at: string
}

// ── 부서별 그룹 정의 ──────────────────────────────────────────
interface DeptGroup {
  label: string
  color: string      // 글로우/보더 색상
  bgColor: string    // 배경 색조
  agents: string[]
}

const DEPT_GROUPS: DeptGroup[] = [
  {
    label: '품질',
    color: '#22c55e',
    bgColor: 'rgba(34,197,94,0.06)',
    agents: ['nc-manager', 'qa-agent', 'issue-manager'],
  },
  {
    label: '개발',
    color: '#3b82f6',
    bgColor: 'rgba(59,130,246,0.06)',
    agents: ['dev-agent', 'crafter', 'db-manager', 'design-agent'],
  },
  {
    label: 'CS/영업',
    color: '#f97316',
    bgColor: 'rgba(249,115,22,0.06)',
    agents: ['cs-agent', 'sales-agent'],
  },
  {
    label: '관리',
    color: '#a855f7',
    bgColor: 'rgba(168,85,247,0.06)',
    agents: ['admin-agent', 'slack-bot', 'docs-agent', 'schedule-agent'],
  },
  {
    label: '데이터',
    color: '#06b6d4',
    bgColor: 'rgba(6,182,212,0.06)',
    agents: ['research-agent'],
  },
  {
    label: '기구/구매',
    color: '#14b8a6',
    bgColor: 'rgba(20,184,166,0.06)',
    agents: ['purchase-agent', 'control-agent'],
  },
]

// ── 에이전트 색상 맵 (agents.json의 color 필드) ──
const AGENT_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { color: string | null }).color)
    .map(([id, a]) => [id, (a as { color: string }).color])
)

// ── 방사형 레이아웃 계산 ────────────────────────────────────────
interface NodePos {
  id: string
  x: number
  y: number
  dept: DeptGroup
}

function calcRadialLayout(cx: number, cy: number, radius: number): NodePos[] {
  const nodes: NodePos[] = []
  const allAgents = DEPT_GROUPS.flatMap((d) => d.agents)
  const total = allAgents.length
  let idx = 0

  for (const dept of DEPT_GROUPS) {
    for (const agentId of dept.agents) {
      const angle = (idx / total) * 2 * Math.PI - Math.PI / 2
      nodes.push({
        id: agentId,
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        dept,
      })
      idx++
    }
  }
  return nodes
}

// ── 토큰 수 포맷 (1234567 → "1.23M") ──────────────────────────────
function formatTokens(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

// ── 최근 메시지 시간 포맷 ────────────────────────────────────────
function formatTime(timeStr: string): string {
  if (!timeStr) return ''
  const parts = timeStr.split(' ')
  return parts.length >= 2 ? parts[1].slice(0, 5) : timeStr.slice(0, 5)
}

// ── 메인 컴포넌트 ───────────────────────────────────────────────
export default function OfficePage() {
  const agents = useAgentStore((s) => s.agents)
  const stats = useAgentStore((s) => s.stats)
  const messages = useAgentStore((s) => s.messages)
  const toolStats = useAgentStore((s) => s.toolStats)
  const toolLogs = useAgentStore((s) => s.toolLogs)

  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [pulseLines, setPulseLines] = useState<Set<string>>(new Set())
  const [usage, setUsage] = useState<UsageData | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  // 토큰 사용량 fetch + socket 수신
  const fetchUsage = useCallback(() => {
    fetch('/api/usage')
      .then((r) => r.json())
      .then((d) => { if (d.ok && d.data?.tokens_used) setUsage(d.data) })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchUsage()
    const interval = setInterval(fetchUsage, 600_000) // 10분 폴링
    const socket = io('/', { path: '/socket.io', transports: ['websocket', 'polling'] })
    socket.on('usage_update', (data: UsageData) => setUsage(data))
    return () => {
      clearInterval(interval)
      socket.disconnect()
    }
  }, [fetchUsage])

  const onlineSet = useMemo(
    () => new Set(agents.filter((a) => a.online).map((a) => a.agent_id)),
    [agents],
  )
  const onlineCount = onlineSet.size
  const offlineCount = stats.total_agents - stats.online_count
  const totalToolCalls = Object.values(toolStats.by_agent).reduce((s, n) => s + n, 0)

  // 작업중 판정: 마지막 도구 사용이 30초 이내
  const workingSet = useMemo(() => {
    const lastAct: Record<string, string> = {}
    for (const log of toolLogs) {
      if (!lastAct[log.agent_id] || log.timestamp > lastAct[log.agent_id]) {
        lastAct[log.agent_id] = log.timestamp
      }
    }
    const now = Date.now()
    const set = new Set<string>()
    for (const [id, ts] of Object.entries(lastAct)) {
      const elapsed = (now - new Date(ts.replace(' ', 'T')).getTime()) / 1000
      if (elapsed < 30) set.add(id)
    }
    return set
  }, [toolLogs])

  // SVG 크기
  const SVG_W = 800
  const SVG_H = 600
  const CX = SVG_W / 2
  const CY = SVG_H / 2 - 20
  const RADIUS = 220

  const nodes = useMemo(() => calcRadialLayout(CX, CY, RADIUS), [CX, CY])

  // 노드 위치 맵 (id → {x, y})
  const nodePos = useMemo(() => {
    const map: Record<string, { x: number; y: number; dept: DeptGroup }> = {}
    map['MAX'] = { x: CX, y: CY, dept: DEPT_GROUPS[0] }
    for (const n of nodes) {
      map[n.id] = { x: n.x, y: n.y, dept: n.dept }
    }
    return map
  }, [nodes, CX, CY])

  // 모든 에이전트 쌍 (메시 네트워크 기본선)
  const allPairs = useMemo(() => {
    const ids = Object.keys(nodePos)
    const pairs: { a: string; b: string }[] = []
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        pairs.push({ a: ids[i], b: ids[j] })
      }
    }
    return pairs
  }, [nodePos])

  // 활성 통신 쌍 (펄스 중인 연결)
  const activePairSet = useMemo(() => {
    const set = new Set<string>()
    for (const lineKey of pulseLines) {
      const sepIdx = lineKey.indexOf('|')
      if (sepIdx < 0) continue
      const from = lineKey.slice(0, sepIdx)
      const to = lineKey.slice(sepIdx + 1)
      set.add([from, to].sort().join('|'))
    }
    return set
  }, [pulseLines])

  // 통신 애니메이션: 2초마다 /api/history 폴링하여 새 메시지 감지
  const seenIdsRef = useRef(new Set<number>())
  const initDoneRef = useRef(false)
  useEffect(() => {
    const agentIds = new Set(Object.keys(nodePos))
    const poll = async () => {
      try {
        const res = await fetch('/api/history?limit=20')
        const data = await res.json()
        const msgs = (data.messages ?? []) as { id: number; from: string; to: string; type: string }[]
        if (msgs.length === 0) return
        // 초회: 기존 메시지 ID만 기록하고 애니메이션 없이 리턴
        if (!initDoneRef.current) {
          initDoneRef.current = true
          for (const msg of msgs) seenIdsRef.current.add(msg.id)
          return
        }
        for (const msg of msgs) {
          if (seenIdsRef.current.has(msg.id)) continue
          seenIdsRef.current.add(msg.id)
          // nodePos에 있는 에이전트 간 통신만 표시
          const from = agentIds.has(msg.from) ? msg.from : null
          const to = agentIds.has(msg.to) ? msg.to : null
          if (!from && !to) continue
          // 한쪽만 매칭되면 MAX와 연결
          const a = from || 'MAX'
          const b = to || 'MAX'
          if (a === b) continue
          const sortedKey = [a, b].sort().join('|')
          setPulseLines((prev) => {
            const next = new Set(prev)
            next.add(sortedKey)
            return next
          })
          setTimeout(() => {
            setPulseLines((prev) => {
              const next = new Set(prev)
              next.delete(sortedKey)
              return next
            })
          }, 5000)
        }
        // 메모리 관리: 오래된 ID 정리
        if (seenIdsRef.current.size > 500) {
          const arr = Array.from(seenIdsRef.current).sort((a, b) => a - b)
          seenIdsRef.current = new Set(arr.slice(-200))
        }
      } catch { /* ignore */ }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [nodePos])

  // 최근 메시지 피드 (10건, 선택 에이전트 필터링)
  const recentMessages = useMemo(() => {
    const filtered = selectedAgent
      ? messages.filter((m) => m.from === selectedAgent || m.to === selectedAgent)
      : messages
    return filtered.slice(-10).reverse()
  }, [messages, selectedAgent])

  const selectedProfile = selectedAgent
    ? (agentsConfig[selectedAgent as keyof typeof agentsConfig] as {
        name: string; emoji: string; role: string; model: string | null; rank: string | null; port: number | null
      } | undefined)
    : null

  return (
    <div className="px-2 py-2 h-full flex flex-col overflow-hidden" style={{ background: '#0F172A' }}>
      {/* 헤더 */}
      <div className="mb-1 px-1 flex-shrink-0">
        <h1 className="text-sm font-bold text-slate-100">Agent Control Center</h1>
      </div>

      {/* KPI 바 */}
      <div className="flex flex-wrap gap-3 mb-2 px-1 flex-shrink-0">
        <KpiCard label="ONLINE" value={onlineCount} color="#22c55e" />
        <KpiCard label="OFFLINE" value={offlineCount} color="#64748b" />
        <KpiCard label="TOOL CALLS" value={totalToolCalls} color="#3b82f6" />
        <KpiCard label="UPTIME" value={stats.uptime} color="#a855f7" />
        <KpiCard label="MESSAGES" value={stats.total_messages} color="#f59e0b" />
        {usage && (
          <>
            <KpiCard
              label="TOKENS"
              value={formatTokens(usage.tokens_used)}
              color="#e879f9"
              sub={usage.tokens_limit ? `/ ${formatTokens(usage.tokens_limit)}` : undefined}
            />
            <KpiCard
              label="COST"
              value={`$${usage.cost.toFixed(2)}`}
              color="#fb923c"
              sub={usage.period || undefined}
            />
          </>
        )}
      </div>

      <div className="flex gap-3 flex-1 min-h-0">
        {/* 메인 관제 맵 */}
        <div
          className="flex-1 min-h-0 rounded-xl border overflow-hidden relative flex flex-col"
          style={{
            borderColor: 'rgba(51,65,85,0.5)',
            background: 'linear-gradient(180deg, #0F172A 0%, #1E293B 100%)',
          }}
        >
          {/* 그리드 패턴 배경 */}
          <div
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: `
                linear-gradient(rgba(148,163,184,1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(148,163,184,1) 1px, transparent 1px)
              `,
              backgroundSize: '40px 40px',
            }}
          />

          <svg
            ref={svgRef}
            viewBox={`0 0 ${SVG_W} ${SVG_H}`}
            className="w-full h-full relative z-10"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              {/* 글로우 필터 */}
              <filter id="glow-green" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="glow-line" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              {/* 부서 영역 배경용 그라데이션 */}
              {DEPT_GROUPS.map((dept) => (
                <radialGradient key={dept.label} id={`grad-${dept.label}`}>
                  <stop offset="0%" stopColor={dept.color} stopOpacity="0.08" />
                  <stop offset="100%" stopColor={dept.color} stopOpacity="0" />
                </radialGradient>
              ))}
            </defs>

            {/* 부서 영역 배경 */}
            {DEPT_GROUPS.map((dept) => {
              const deptNodes = nodes.filter((n) => n.dept.label === dept.label)
              if (deptNodes.length === 0) return null
              const avgX = deptNodes.reduce((s, n) => s + n.x, 0) / deptNodes.length
              const avgY = deptNodes.reduce((s, n) => s + n.y, 0) / deptNodes.length
              return (
                <circle
                  key={`area-${dept.label}`}
                  cx={avgX}
                  cy={avgY}
                  r={90}
                  fill={`url(#grad-${dept.label})`}
                />
              )
            })}

            {/* 부서 라벨 */}
            {DEPT_GROUPS.map((dept) => {
              const deptNodes = nodes.filter((n) => n.dept.label === dept.label)
              if (deptNodes.length === 0) return null
              const avgX = deptNodes.reduce((s, n) => s + n.x, 0) / deptNodes.length
              const avgY = deptNodes.reduce((s, n) => s + n.y, 0) / deptNodes.length
              // 라벨을 바깥쪽으로 오프셋
              const dx = avgX - CX
              const dy = avgY - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const labelX = avgX + (dx / dist) * 55
              const labelY = avgY + (dy / dist) * 55
              return (
                <text
                  key={`label-${dept.label}`}
                  x={labelX}
                  y={labelY}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill={dept.color}
                  opacity="0.5"
                  fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                >
                  {dept.label}
                </text>
              )
            })}

            {/* 네트워크 메시 연결선 (모든 쌍 기본 + 활성 글로우) */}
            {allPairs.map(({ a, b }) => {
              const posA = nodePos[a]
              const posB = nodePos[b]
              if (!posA || !posB) return null
              const key = [a, b].sort().join('|')
              const isActive = activePairSet.has(key)
              const color = isActive ? '#00ff88' : 'rgba(71,85,105,1)'
              return (
                <g key={`mesh-${a}-${b}`}>
                  <line
                    x1={posA.x}
                    y1={posA.y}
                    x2={posB.x}
                    y2={posB.y}
                    stroke={color}
                    strokeWidth={isActive ? 3 : 0.5}
                    opacity={isActive ? 1 : 0.15}
                    filter={isActive ? 'url(#glow-line)' : undefined}
                    style={{
                      transition: 'stroke 0.3s, stroke-width 0.3s, opacity 0.3s',
                    }}
                  >
                    {isActive && (
                      <animate attributeName="opacity" values="1;0.4;1" dur="1s" repeatCount="indefinite" />
                    )}
                  </line>
                  {isActive && (
                    <line
                      x1={posA.x}
                      y1={posA.y}
                      x2={posB.x}
                      y2={posB.y}
                      stroke={color}
                      strokeWidth={6}
                      opacity={0.3}
                      filter="url(#glow-line)"
                    >
                      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="1s" repeatCount="indefinite" />
                    </line>
                  )}
                </g>
              )
            })}

            {/* MAX 허브 노드 */}
            <g
              className="cursor-pointer"
              onClick={() => setSelectedAgent(selectedAgent === 'MAX' ? null : 'MAX')}
            >
              <circle
                cx={CX}
                cy={CY}
                r={36}
                fill="#1E293B"
                stroke="#eab308"
                strokeWidth={onlineSet.has('MAX') ? 2.5 : 1}
                filter={onlineSet.has('MAX') ? 'url(#glow-green)' : undefined}
                opacity={onlineSet.has('MAX') ? 1 : 0.4}
              />
              <text
                x={CX}
                y={CY - 6}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="20"
              >
                👑
              </text>
              <text
                x={CX}
                y={CY + 14}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="10"
                fontWeight="bold"
                fill="#eab308"
                fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
              >
                MAX
              </text>
              {/* 상태 LED */}
              <circle
                cx={CX + 26}
                cy={CY - 26}
                r={5}
                fill={workingSet.has('MAX') ? '#60a5fa' : onlineSet.has('MAX') ? '#22c55e' : '#475569'}
                filter={onlineSet.has('MAX') ? 'url(#glow-green)' : undefined}
              >
                {workingSet.has('MAX') && (
                  <animate attributeName="opacity" values="1;0.3;1" dur="1.5s" repeatCount="indefinite" />
                )}
              </circle>
              {workingSet.has('MAX') && (
                <circle
                  cx={CX}
                  cy={CY}
                  r={32}
                  fill="none"
                  stroke="#60a5fa"
                  strokeWidth={2}
                  strokeDasharray="20 60"
                  strokeLinecap="round"
                  opacity={0.8}
                >
                  <animateTransform
                    attributeName="transform"
                    type="rotate"
                    from={`0 ${CX} ${CY}`}
                    to={`360 ${CX} ${CY}`}
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
            </g>

            {/* 에이전트 노드 */}
            {nodes.map((node) => {
              const profile = AGENT_PROFILES[node.id]
              if (!profile) return null
              const online = onlineSet.has(node.id)
              const agentColor = AGENT_COLORS[node.id] || node.dept.color
              const isSelected = selectedAgent === node.id

              return (
                <g
                  key={node.id}
                  className="cursor-pointer"
                  onClick={() => setSelectedAgent(isSelected ? null : node.id)}
                >
                  {/* 선택 링 */}
                  {isSelected && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={30}
                      fill="none"
                      stroke={agentColor}
                      strokeWidth={1.5}
                      strokeDasharray="4 3"
                      opacity={0.6}
                    />
                  )}
                  {/* 노드 배경 */}
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={24}
                    fill="#1E293B"
                    stroke={online ? agentColor : '#334155'}
                    strokeWidth={online ? 1.5 : 1}
                    opacity={online ? 1 : 0.4}
                  />
                  {/* 이모지 */}
                  <text
                    x={node.x}
                    y={node.y - 4}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="16"
                    opacity={online ? 1 : 0.4}
                  >
                    {profile.emoji}
                  </text>
                  {/* 이름 */}
                  <text
                    x={node.x}
                    y={node.y + 12}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="10"
                    fontWeight="600"
                    fill={online ? '#e2e8f0' : '#64748b'}
                    fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                  >
                    {profile.name}
                  </text>
                  {/* 상태 LED */}
                  <circle
                    cx={node.x + 17}
                    cy={node.y - 17}
                    r={4}
                    fill={workingSet.has(node.id) ? '#60a5fa' : online ? '#22c55e' : '#475569'}
                    filter={online ? 'url(#glow-green)' : undefined}
                  >
                    {workingSet.has(node.id) && (
                      <animate attributeName="opacity" values="1;0.3;1" dur="1.5s" repeatCount="indefinite" />
                    )}
                  </circle>
                  {/* 작업중 spinning arc */}
                  {workingSet.has(node.id) && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={28}
                      fill="none"
                      stroke="#60a5fa"
                      strokeWidth={1.5}
                      strokeDasharray="16 50"
                      strokeLinecap="round"
                      opacity={0.7}
                    >
                      <animateTransform
                        attributeName="transform"
                        type="rotate"
                        from={`0 ${node.x} ${node.y}`}
                        to={`360 ${node.x} ${node.y}`}
                        dur="2s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}
                </g>
              )
            })}
          </svg>
        </div>

        {/* 우측 고정 패널 */}
        <div
          className="w-64 flex-shrink-0 flex flex-col gap-3 overflow-y-auto min-h-0 rounded-xl p-3"
          style={{ background: 'rgba(15,23,42,0.9)', border: '1px solid rgba(51,65,85,0.5)' }}
        >
          {/* 선택된 에이전트 정보 */}
          {selectedAgent && selectedProfile && (
            <div
              className="rounded-xl border p-4"
              style={{
                borderColor: AGENT_COLORS[selectedAgent] || '#334155',
                background: 'rgba(30,41,59,0.8)',
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{selectedProfile.emoji}</span>
                <div>
                  <div className="text-sm font-bold text-slate-100">{selectedProfile.name}</div>
                  <div className="text-xs text-slate-500">{selectedProfile.rank || '—'}</div>
                </div>
                <span
                  className="ml-auto w-2.5 h-2.5 rounded-full"
                  style={{
                    background: onlineSet.has(selectedAgent) ? '#22c55e' : '#475569',
                    boxShadow: onlineSet.has(selectedAgent) ? '0 0 8px #22c55e' : 'none',
                  }}
                />
              </div>
              <div className="text-xs text-slate-400 mb-2">{selectedProfile.role}</div>
              <div className="flex gap-2 text-xs">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                  {selectedProfile.model || '—'}
                </span>
                {selectedProfile.port && (
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                    :{selectedProfile.port}
                  </span>
                )}
              </div>
              {toolStats.by_agent[selectedAgent] && (
                <div className="mt-2 text-xs text-slate-500">
                  도구 호출: <span className="text-blue-400 font-mono">{toolStats.by_agent[selectedAgent]}</span>회
                </div>
              )}
            </div>
          )}

          {/* 부서별 범례 */}
          <div
            className="rounded-xl border p-3"
            style={{ borderColor: 'rgba(51,65,85,0.5)', background: 'rgba(30,41,59,0.6)' }}
          >
            <div className="text-xs font-semibold text-slate-400 mb-2">DEPARTMENTS</div>
            <div className="flex flex-wrap gap-2">
              {DEPT_GROUPS.map((dept) => (
                <span
                  key={dept.label}
                  className="flex items-center gap-1.5 text-xs px-2 py-1 rounded"
                  style={{ background: dept.bgColor, color: dept.color }}
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: dept.color }}
                  />
                  {dept.label}
                </span>
              ))}
            </div>
          </div>

          {/* 최근 메시지 피드 */}
          <div
            className="rounded-xl border p-3 flex-1 min-h-0 flex flex-col"
            style={{ borderColor: 'rgba(51,65,85,0.5)', background: 'rgba(30,41,59,0.6)' }}
          >
            <div className="text-xs font-semibold text-slate-400 mb-2 flex-shrink-0">
              RECENT ACTIVITY
              {selectedAgent && (
                <span className="ml-1 text-blue-400 font-normal">
                  ({AGENT_PROFILES[selectedAgent]?.name || selectedAgent})
                </span>
              )}
            </div>
            <div className="space-y-1.5 overflow-y-auto flex-1 min-h-0">
              {recentMessages.length === 0 && (
                <div className="text-xs text-slate-600 py-4 text-center">메시지 없음</div>
              )}
              {recentMessages.map((msg) => {
                const fromEmoji = AGENT_PROFILES[msg.from]?.emoji || '📨'
                const toEmoji = AGENT_PROFILES[msg.to]?.emoji || '📨'
                return (
                  <div
                    key={msg.id}
                    className="flex items-start gap-2 text-xs py-1 border-b"
                    style={{ borderColor: 'rgba(51,65,85,0.3)' }}
                  >
                    <span className="text-slate-600 font-mono whitespace-nowrap mt-0.5">
                      {formatTime(msg.time)}
                    </span>
                    <div className="min-w-0">
                      <span>
                        {fromEmoji}
                        <span className="text-slate-500 mx-0.5">→</span>
                        {toEmoji}
                      </span>
                      <div className="text-slate-500 truncate mt-0.5" title={msg.content}>
                        {msg.content.slice(0, 80)}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── KPI 카드 ────────────────────────────────────────────────────
function KpiCard({ label, value, color, sub }: { label: string; value: string | number; color: string; sub?: string }) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg border px-3 py-1.5"
      style={{
        borderColor: `${color}30`,
        background: `${color}08`,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: color, boxShadow: `0 0 6px ${color}` }}
      />
      <span className="text-xs text-slate-500 font-mono uppercase">{label}</span>
      <span className="text-sm font-bold font-mono" style={{ color }}>
        {value}
      </span>
      {sub && <span className="text-xs text-slate-600 font-mono">{sub}</span>}
    </div>
  )
}
