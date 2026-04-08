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
  weekly_tokens?: number
  weekly_cost?: number
  weekly_limit?: number
  weekly_period?: string
  session_remaining_pct?: number | null
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
      .then((d) => { if (d.ok && d.data) setUsage(d.data) })
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
              label="WEEKLY"
              value={formatTokens(usage.weekly_tokens ?? usage.tokens_used)}
              color="#e879f9"
              sub={usage.weekly_limit ? `/ ${formatTokens(usage.weekly_limit)}` : undefined}
            />
{/* Cost 카드 제거 (부서장 요청) */}
            {usage.session_remaining_pct != null && (
              <KpiCard
                label="REMAINING"
                value={`${usage.session_remaining_pct}%`}
                color={usage.session_remaining_pct > 30 ? '#22c55e' : usage.session_remaining_pct > 10 ? '#f59e0b' : '#ef4444'}
              />
            )}
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

            {/* ── Slack 게이트웨이 시각화 (slack-bot 왼쪽) ── */}
            {(() => {
              const sbPos = nodePos['slack-bot']
              if (!sbPos) return null
              // slack-bot 기준 외곽(왼쪽) 방향 계산
              const dx = sbPos.x - CX
              const dy = sbPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              // Slack 아이콘 위치 (slack-bot에서 외곽 방향 65px)
              const slackX = sbPos.x + dirX * 65
              const slackY = sbPos.y + dirY * 65
              // 사용자 그룹 위치 (Slack 아이콘에서 더 외곽 55px)
              const usersX = slackX + dirX * 55
              const usersY = slackY + dirY * 55
              // 수직 방향 (사용자 아이콘 배치용)
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  {/* slack-bot → Slack 아이콘 연결선 */}
                  <line
                    x1={sbPos.x + dirX * 24}
                    y1={sbPos.y + dirY * 24}
                    x2={slackX - dirX * 16}
                    y2={slackY - dirY * 16}
                    stroke="#E01E5A"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  {/* 양방향 화살표 마커 */}
                  <polygon
                    points={`${slackX - dirX * 18},${slackY - dirY * 18} ${slackX - dirX * 24 + perpX * 3},${slackY - dirY * 24 + perpY * 3} ${slackX - dirX * 24 - perpX * 3},${slackY - dirY * 24 - perpY * 3}`}
                    fill="#E01E5A"
                    opacity={0.6}
                  />

                  {/* Slack 아이콘 (# 마크 스타일) */}
                  <g>
                    <rect
                      x={slackX - 14}
                      y={slackY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#E01E5A"
                      strokeWidth={1.5}
                    />
                    {/* Slack 로고: 4색 바 */}
                    <rect x={slackX - 6} y={slackY - 8} width={3} height={16} rx={1.5} fill="#E01E5A" />
                    <rect x={slackX + 3} y={slackY - 8} width={3} height={16} rx={1.5} fill="#36C5F0" />
                    <rect x={slackX - 8} y={slackY - 3} width={16} height={3} rx={1.5} fill="#2EB67D" />
                    <rect x={slackX - 8} y={slackY + 3} width={16} height={3} rx={1.5} fill="#ECB22E" />
                    <text
                      x={slackX}
                      y={slackY + 24}
                      textAnchor="middle"
                      fontSize="8"
                      fill="#94a3b8"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      Slack
                    </text>
                  </g>

                  {/* Slack → 사용자 연결선 */}
                  <line
                    x1={slackX + dirX * 16}
                    y1={slackY + dirY * 16}
                    x2={usersX - dirX * 20}
                    y2={usersY - dirY * 20}
                    stroke="#36C5F0"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    opacity={0.4}
                  >
                    <animate attributeName="strokeDashoffset" values="0;-12" dur="2s" repeatCount="indefinite" />
                  </line>

                  {/* 사용자(직원) 아이콘 그룹 */}
                  {[-1, 0, 1].map((offset) => {
                    const ux = usersX + perpX * offset * 18
                    const uy = usersY + perpY * offset * 18
                    return (
                      <g key={`user-${offset}`} opacity={offset === 0 ? 0.8 : 0.5}>
                        {/* 사용자 원 */}
                        <circle cx={ux} cy={uy} r={10} fill="#1E293B" stroke="#64748b" strokeWidth={1} />
                        {/* 사용자 아이콘 (머리) */}
                        <circle cx={ux} cy={uy - 3} r={3} fill="#94a3b8" />
                        {/* 사용자 아이콘 (몸통) */}
                        <path
                          d={`M${ux - 5},${uy + 7} Q${ux - 5},${uy + 2} ${ux},${uy + 2} Q${ux + 5},${uy + 2} ${ux + 5},${uy + 7}`}
                          fill="#94a3b8"
                        />
                      </g>
                    )
                  })}
                  <text
                    x={usersX}
                    y={usersY + 22}
                    textAnchor="middle"
                    fontSize="8"
                    fill="#64748b"
                    fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                  >
                    직원
                  </text>
                </g>
              )
            })()}

            {/* ── MES/ERP 시각화 (db-manager 외곽) ── */}
            {(() => {
              const dbPos = nodePos['db-manager']
              if (!dbPos) return null
              const dx = dbPos.x - CX
              const dy = dbPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              // MES 위치 (db-manager에서 외곽 방향 65px)
              const mesX = dbPos.x + dirX * 65
              const mesY = dbPos.y + dirY * 65
              // ERP 위치 (MES에서 더 외곽 55px)
              const erpX = mesX + dirX * 55
              const erpY = mesY + dirY * 55
              // 수직 방향
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  {/* db-manager → MES 연결선 */}
                  <line
                    x1={dbPos.x + dirX * 24}
                    y1={dbPos.y + dirY * 24}
                    x2={mesX - dirX * 16}
                    y2={mesY - dirY * 16}
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <polygon
                    points={`${mesX - dirX * 18},${mesY - dirY * 18} ${mesX - dirX * 24 + perpX * 3},${mesY - dirY * 24 + perpY * 3} ${mesX - dirX * 24 - perpX * 3},${mesY - dirY * 24 - perpY * 3}`}
                    fill="#3b82f6"
                    opacity={0.6}
                  />

                  {/* MES 아이콘 (DB 실린더) */}
                  <g>
                    <rect
                      x={mesX - 14}
                      y={mesY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#3b82f6"
                      strokeWidth={1.5}
                    />
                    {/* DB 실린더 아이콘 */}
                    <ellipse cx={mesX} cy={mesY - 5} rx={7} ry={3} fill="none" stroke="#60a5fa" strokeWidth={1.2} />
                    <line x1={mesX - 7} y1={mesY - 5} x2={mesX - 7} y2={mesY + 5} stroke="#60a5fa" strokeWidth={1.2} />
                    <line x1={mesX + 7} y1={mesY - 5} x2={mesX + 7} y2={mesY + 5} stroke="#60a5fa" strokeWidth={1.2} />
                    <ellipse cx={mesX} cy={mesY + 5} rx={7} ry={3} fill="none" stroke="#60a5fa" strokeWidth={1.2} />
                    <text
                      x={mesX}
                      y={mesY + 24}
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill="#60a5fa"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      mes-wta.com
                    </text>
                  </g>

                  {/* MES → ERP 연결선 */}
                  <line
                    x1={mesX + dirX * 16}
                    y1={mesY + dirY * 16}
                    x2={erpX - dirX * 16}
                    y2={erpY - dirY * 16}
                    stroke="#f59e0b"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    opacity={0.4}
                  >
                    <animate attributeName="strokeDashoffset" values="0;-12" dur="2s" repeatCount="indefinite" />
                  </line>

                  {/* ERP 아이콘 (서버) */}
                  <g opacity={0.7}>
                    <rect
                      x={erpX - 14}
                      y={erpY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#f59e0b"
                      strokeWidth={1.5}
                    />
                    {/* 서버 랙 아이콘 */}
                    <rect x={erpX - 7} y={erpY - 8} width={14} height={5} rx={1} fill="none" stroke="#fbbf24" strokeWidth={1} />
                    <rect x={erpX - 7} y={erpY - 1} width={14} height={5} rx={1} fill="none" stroke="#fbbf24" strokeWidth={1} />
                    <rect x={erpX - 7} y={erpY + 6} width={14} height={5} rx={1} fill="none" stroke="#fbbf24" strokeWidth={1} />
                    {/* LED 점 */}
                    <circle cx={erpX + 4} cy={erpY - 5.5} r={1} fill="#22c55e" />
                    <circle cx={erpX + 4} cy={erpY + 1.5} r={1} fill="#22c55e" />
                    <circle cx={erpX + 4} cy={erpY + 8.5} r={1} fill="#f59e0b" />
                    <text
                      x={erpX}
                      y={erpY + 24}
                      textAnchor="middle"
                      fontSize="8"
                      fontWeight="bold"
                      fill="#fbbf24"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      ERP
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── cs-wta.com 웹사이트 시각화 (cs-agent 외곽) ── */}
            {(() => {
              const csPos = nodePos['cs-agent']
              if (!csPos) return null
              const dx = csPos.x - CX
              const dy = csPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              // 웹사이트 아이콘 위치
              const webX = csPos.x + dirX * 65
              const webY = csPos.y + dirY * 65
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  {/* cs-agent → 웹사이트 연결선 */}
                  <line
                    x1={csPos.x + dirX * 24}
                    y1={csPos.y + dirY * 24}
                    x2={webX - dirX * 16}
                    y2={webY - dirY * 16}
                    stroke="#f97316"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <polygon
                    points={`${webX - dirX * 18},${webY - dirY * 18} ${webX - dirX * 24 + perpX * 3},${webY - dirY * 24 + perpY * 3} ${webX - dirX * 24 - perpX * 3},${webY - dirY * 24 - perpY * 3}`}
                    fill="#f97316"
                    opacity={0.6}
                  />

                  {/* 글로브(웹) 아이콘 */}
                  <g>
                    <rect
                      x={webX - 14}
                      y={webY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#f97316"
                      strokeWidth={1.5}
                    />
                    {/* 지구본 아이콘 */}
                    <circle cx={webX} cy={webY} r={8} fill="none" stroke="#fb923c" strokeWidth={1.2} />
                    <ellipse cx={webX} cy={webY} rx={4} ry={8} fill="none" stroke="#fb923c" strokeWidth={0.8} />
                    <line x1={webX - 8} y1={webY} x2={webX + 8} y2={webY} stroke="#fb923c" strokeWidth={0.8} />
                    <line x1={webX - 7} y1={webY - 4} x2={webX + 7} y2={webY - 4} stroke="#fb923c" strokeWidth={0.6} />
                    <line x1={webX - 7} y1={webY + 4} x2={webX + 7} y2={webY + 4} stroke="#fb923c" strokeWidth={0.6} />
                    <text
                      x={webX}
                      y={webY + 24}
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill="#fb923c"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      cs-wta.com
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── Online/Web 시각화 (research-agent 외곽) ── */}
            {(() => {
              const raPos = nodePos['research-agent']
              if (!raPos) return null
              const dx = raPos.x - CX
              const dy = raPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              const netX = raPos.x + dirX * 90
              const netY = raPos.y + dirY * 90
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  <line
                    x1={raPos.x + dirX * 24}
                    y1={raPos.y + dirY * 24}
                    x2={netX - dirX * 16}
                    y2={netY - dirY * 16}
                    stroke="#06b6d4"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <polygon
                    points={`${netX - dirX * 18},${netY - dirY * 18} ${netX - dirX * 24 + perpX * 3},${netY - dirY * 24 + perpY * 3} ${netX - dirX * 24 - perpX * 3},${netY - dirY * 24 - perpY * 3}`}
                    fill="#06b6d4"
                    opacity={0.6}
                  />
                  <g>
                    <rect
                      x={netX - 14}
                      y={netY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#06b6d4"
                      strokeWidth={1.5}
                    />
                    {/* 지구본 + 검색 아이콘 */}
                    <circle cx={netX - 2} cy={netY - 1} r={7} fill="none" stroke="#22d3ee" strokeWidth={1.2} />
                    <ellipse cx={netX - 2} cy={netY - 1} rx={3.5} ry={7} fill="none" stroke="#22d3ee" strokeWidth={0.7} />
                    <line x1={netX - 9} y1={netY - 1} x2={netX + 5} y2={netY - 1} stroke="#22d3ee" strokeWidth={0.7} />
                    {/* 돋보기 */}
                    <circle cx={netX + 4} cy={netY + 3} r={3} fill="none" stroke="#67e8f9" strokeWidth={1} />
                    <line x1={netX + 6.2} y1={netY + 5.2} x2={netX + 9} y2={netY + 8} stroke="#67e8f9" strokeWidth={1.2} />
                    <text
                      x={netX}
                      y={netY + 24}
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill="#22d3ee"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      Online
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── NAS 저장소 시각화 (docs-agent 외곽) ── */}
            {(() => {
              const daPos = nodePos['docs-agent']
              if (!daPos) return null
              const dx = daPos.x - CX
              const dy = daPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              const nasX = daPos.x + dirX * 65
              const nasY = daPos.y + dirY * 65
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  <line
                    x1={daPos.x + dirX * 24}
                    y1={daPos.y + dirY * 24}
                    x2={nasX - dirX * 16}
                    y2={nasY - dirY * 16}
                    stroke="#a855f7"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <polygon
                    points={`${nasX - dirX * 18},${nasY - dirY * 18} ${nasX - dirX * 24 + perpX * 3},${nasY - dirY * 24 + perpY * 3} ${nasX - dirX * 24 - perpX * 3},${nasY - dirY * 24 - perpY * 3}`}
                    fill="#a855f7"
                    opacity={0.6}
                  />
                  <g>
                    <rect
                      x={nasX - 14}
                      y={nasY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#a855f7"
                      strokeWidth={1.5}
                    />
                    {/* NAS 스토리지 아이콘 (HDD 슬롯 2개) */}
                    <rect x={nasX - 8} y={nasY - 8} width={16} height={7} rx={1.5} fill="none" stroke="#c084fc" strokeWidth={1} />
                    <rect x={nasX - 8} y={nasY + 1} width={16} height={7} rx={1.5} fill="none" stroke="#c084fc" strokeWidth={1} />
                    {/* 슬롯 라인 */}
                    <line x1={nasX - 5} y1={nasY - 4.5} x2={nasX + 3} y2={nasY - 4.5} stroke="#c084fc" strokeWidth={0.6} />
                    <line x1={nasX - 5} y1={nasY + 4.5} x2={nasX + 3} y2={nasY + 4.5} stroke="#c084fc" strokeWidth={0.6} />
                    {/* LED */}
                    <circle cx={nasX + 5} cy={nasY - 4.5} r={1} fill="#22c55e" />
                    <circle cx={nasX + 5} cy={nasY + 4.5} r={1} fill="#22c55e" />
                    <text
                      x={nasX}
                      y={nasY + 24}
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill="#c084fc"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      NAS
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── 다우오피스 시각화 (admin-agent 외곽) ── */}
            {(() => {
              const aaPos = nodePos['admin-agent']
              if (!aaPos) return null
              const dx = aaPos.x - CX
              const dy = aaPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              const gwX = aaPos.x + dirX * 65
              const gwY = aaPos.y + dirY * 65
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  <line
                    x1={aaPos.x + dirX * 24}
                    y1={aaPos.y + dirY * 24}
                    x2={gwX - dirX * 16}
                    y2={gwY - dirY * 16}
                    stroke="#a855f7"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <polygon
                    points={`${gwX - dirX * 18},${gwY - dirY * 18} ${gwX - dirX * 24 + perpX * 3},${gwY - dirY * 24 + perpY * 3} ${gwX - dirX * 24 - perpX * 3},${gwY - dirY * 24 - perpY * 3}`}
                    fill="#a855f7"
                    opacity={0.6}
                  />
                  <g>
                    <rect
                      x={gwX - 14}
                      y={gwY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#a855f7"
                      strokeWidth={1.5}
                    />
                    {/* 메일 봉투 아이콘 */}
                    <rect x={gwX - 8} y={gwY - 5} width={16} height={11} rx={1.5} fill="none" stroke="#c084fc" strokeWidth={1.2} />
                    <polyline
                      points={`${gwX - 8},${gwY - 5} ${gwX},${gwY + 2} ${gwX + 8},${gwY - 5}`}
                      fill="none"
                      stroke="#c084fc"
                      strokeWidth={1}
                    />
                    <text
                      x={gwX}
                      y={gwY + 24}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="bold"
                      fill="#c084fc"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      다우오피스
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── designPC 시각화 (design-agent 외곽) ── */}
            {(() => {
              const daPos = nodePos['design-agent']
              if (!daPos) return null
              const dx = daPos.x - CX
              const dy = daPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              const pcX = daPos.x + dirX * 65
              const pcY = daPos.y + dirY * 65
              const perpX = -dirY
              const perpY = dirX

              return (
                <g opacity={0.9}>
                  <line
                    x1={daPos.x + dirX * 24}
                    y1={daPos.y + dirY * 24}
                    x2={pcX - dirX * 16}
                    y2={pcY - dirY * 16}
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <polygon
                    points={`${pcX - dirX * 18},${pcY - dirY * 18} ${pcX - dirX * 24 + perpX * 3},${pcY - dirY * 24 + perpY * 3} ${pcX - dirX * 24 - perpX * 3},${pcY - dirY * 24 - perpY * 3}`}
                    fill="#3b82f6"
                    opacity={0.6}
                  />
                  <g>
                    <rect
                      x={pcX - 14}
                      y={pcY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#3b82f6"
                      strokeWidth={1.5}
                    />
                    {/* 모니터 아이콘 */}
                    <rect x={pcX - 8} y={pcY - 7} width={16} height={11} rx={1.5} fill="none" stroke="#60a5fa" strokeWidth={1.2} />
                    {/* 화면 내부 */}
                    <rect x={pcX - 6} y={pcY - 5} width={12} height={7} rx={0.5} fill="#60a5fa" opacity={0.15} />
                    {/* 스탠드 */}
                    <line x1={pcX} y1={pcY + 4} x2={pcX} y2={pcY + 7} stroke="#60a5fa" strokeWidth={1.2} />
                    <line x1={pcX - 4} y1={pcY + 7} x2={pcX + 4} y2={pcY + 7} stroke="#60a5fa" strokeWidth={1.2} />
                    <text
                      x={pcX}
                      y={pcY + 24}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="bold"
                      fill="#60a5fa"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      designPC
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── Atlassian 시각화 (research-agent 외곽, Online 반대편) ── */}
            {(() => {
              const raPos = nodePos['research-agent']
              if (!raPos) return null
              const dx = raPos.x - CX
              const dy = raPos.y - CY
              const dist = Math.sqrt(dx * dx + dy * dy) || 1
              const dirX = dx / dist
              const dirY = dy / dist
              // Online과 수직 방향으로 배치
              const perpX = -dirY
              const perpY = dirX
              const atlX = raPos.x + dirX * 50 + perpX * 75
              const atlY = raPos.y + dirY * 50 + perpY * 75

              return (
                <g opacity={0.9}>
                  <line
                    x1={raPos.x + perpX * 24}
                    y1={raPos.y + perpY * 24}
                    x2={atlX - perpX * 14}
                    y2={atlY - perpY * 14}
                    stroke="#2684FF"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  <g>
                    <rect
                      x={atlX - 14}
                      y={atlY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#2684FF"
                      strokeWidth={1.5}
                    />
                    {/* Atlassian "A" 마크 */}
                    <text
                      x={atlX}
                      y={atlY + 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize="16"
                      fontWeight="900"
                      fill="#2684FF"
                      fontFamily="Arial, sans-serif"
                    >
                      A
                    </text>
                    <text
                      x={atlX}
                      y={atlY + 22}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="bold"
                      fill="#2684FF"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      Atlassian
                    </text>
                    <text
                      x={atlX}
                      y={atlY + 31}
                      textAnchor="middle"
                      fontSize="6"
                      fill="#6B778C"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      Jira · Confluence
                    </text>
                  </g>
                </g>
              )
            })()}

            {/* ── Telegram 시각화 (MAX 노드 옆) ── */}
            {(() => {
              // MAX 왼쪽에 배치
              const tgX = CX - 75
              const tgY = CY

              return (
                <g opacity={0.9}>
                  <line
                    x1={CX - 36}
                    y1={CY}
                    x2={tgX + 16}
                    y2={tgY}
                    stroke="#0088cc"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    opacity={0.5}
                  />
                  {/* 화살표 */}
                  <polygon
                    points={`${tgX + 18},${tgY} ${tgX + 24},${tgY - 3} ${tgX + 24},${tgY + 3}`}
                    fill="#0088cc"
                    opacity={0.6}
                  />
                  <g>
                    <rect
                      x={tgX - 14}
                      y={tgY - 14}
                      width={28}
                      height={28}
                      rx={6}
                      fill="#1E293B"
                      stroke="#0088cc"
                      strokeWidth={1.5}
                    />
                    {/* 종이비행기 아이콘 */}
                    <polygon
                      points={`${tgX - 7},${tgY} ${tgX + 8},${tgY - 6} ${tgX + 3},${tgY + 7}`}
                      fill="none"
                      stroke="#29b6f6"
                      strokeWidth={1.2}
                      strokeLinejoin="round"
                    />
                    <line x1={tgX + 8} y1={tgY - 6} x2={tgX - 1} y2={tgY + 1} stroke="#29b6f6" strokeWidth={0.8} />
                    <line x1={tgX - 1} y1={tgY + 1} x2={tgX + 3} y2={tgY + 7} stroke="#29b6f6" strokeWidth={0.8} />
                    <text
                      x={tgX}
                      y={tgY + 24}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="bold"
                      fill="#29b6f6"
                      fontFamily="'맑은 고딕', 'Malgun Gothic', sans-serif"
                    >
                      Telegram
                    </text>
                  </g>
                </g>
              )
            })()}
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
