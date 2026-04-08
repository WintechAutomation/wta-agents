// 에이전트 관제센터 (NOC 스타일) — React + CSS/SVG
import { useState, useEffect, useRef, useMemo } from 'react'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'
import agentsConfig from '@agents'

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

  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [pulseLines, setPulseLines] = useState<Set<string>>(new Set())
  const svgRef = useRef<SVGSVGElement>(null)

  const onlineSet = useMemo(
    () => new Set(agents.filter((a) => a.online).map((a) => a.agent_id)),
    [agents],
  )
  const onlineCount = onlineSet.size
  const offlineCount = stats.total_agents - stats.online_count
  const totalToolCalls = Object.values(toolStats.by_agent).reduce((s, n) => s + n, 0)

  // SVG 크기
  const SVG_W = 800
  const SVG_H = 600
  const CX = SVG_W / 2
  const CY = SVG_H / 2 - 20
  const RADIUS = 220

  const nodes = useMemo(() => calcRadialLayout(CX, CY, RADIUS), [CX, CY])

  // 최근 메시지로 연결선 펄스 애니메이션
  useEffect(() => {
    if (messages.length === 0) return
    const latest = messages[messages.length - 1]
    const from = latest.from
    const to = latest.to
    const lineKey = `${from}-${to}`
    setPulseLines((prev) => new Set(prev).add(lineKey))
    const timer = setTimeout(() => {
      setPulseLines((prev) => {
        const next = new Set(prev)
        next.delete(lineKey)
        return next
      })
    }, 2000)
    return () => clearTimeout(timer)
  }, [messages])

  // 최근 메시지 피드 (10건)
  const recentMessages = useMemo(() => {
    return messages.slice(-10).reverse()
  }, [messages])

  const selectedProfile = selectedAgent
    ? (agentsConfig[selectedAgent as keyof typeof agentsConfig] as {
        name: string; emoji: string; role: string; model: string | null; rank: string | null; port: number | null
      } | undefined)
    : null

  return (
    <div className="p-4 min-h-screen" style={{ background: '#0F172A' }}>
      {/* 헤더 */}
      <div className="mb-4">
        <h1 className="text-lg font-bold text-slate-100">Agent Control Center</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          WTA Multi-Agent System — {Object.keys(AGENT_PROFILES).length} agents
        </p>
      </div>

      {/* KPI 바 */}
      <div className="flex flex-wrap gap-3 mb-4">
        <KpiCard label="ONLINE" value={onlineCount} color="#22c55e" />
        <KpiCard label="OFFLINE" value={offlineCount} color="#64748b" />
        <KpiCard label="TOOL CALLS" value={totalToolCalls} color="#3b82f6" />
        <KpiCard label="UPTIME" value={stats.uptime} color="#a855f7" />
        <KpiCard label="MESSAGES" value={stats.total_messages} color="#f59e0b" />
      </div>

      <div className="flex gap-4 flex-col xl:flex-row">
        {/* 메인 관제 맵 */}
        <div
          className="flex-1 rounded-xl border overflow-hidden relative"
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
            className="w-full h-auto relative z-10"
            style={{ maxHeight: '70vh' }}
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
                  fontFamily="ui-monospace, monospace"
                >
                  {dept.label}
                </text>
              )
            })}

            {/* MAX → 에이전트 연결선 */}
            {nodes.map((node) => {
              const isActive =
                pulseLines.has(`MAX-${node.id}`) ||
                pulseLines.has(`${node.id}-MAX`) ||
                pulseLines.has(`slack-bot-${node.id}`) ||
                pulseLines.has(`${node.id}-slack-bot`)
              const online = onlineSet.has(node.id)
              return (
                <line
                  key={`line-${node.id}`}
                  x1={CX}
                  y1={CY}
                  x2={node.x}
                  y2={node.y}
                  stroke={isActive ? node.dept.color : online ? 'rgba(71,85,105,0.3)' : 'rgba(51,65,85,0.15)'}
                  strokeWidth={isActive ? 2 : 1}
                  filter={isActive ? 'url(#glow-line)' : undefined}
                  style={{
                    transition: 'stroke 0.5s, stroke-width 0.3s',
                  }}
                />
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
                fontFamily="ui-monospace, monospace"
              >
                MAX
              </text>
              {/* 상태 LED */}
              <circle
                cx={CX + 26}
                cy={CY - 26}
                r={5}
                fill={onlineSet.has('MAX') ? '#22c55e' : '#475569'}
                filter={onlineSet.has('MAX') ? 'url(#glow-green)' : undefined}
              />
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
                    fontSize="7"
                    fontWeight="600"
                    fill={online ? '#e2e8f0' : '#64748b'}
                    fontFamily="ui-monospace, monospace"
                  >
                    {profile.name}
                  </text>
                  {/* 상태 LED */}
                  <circle
                    cx={node.x + 17}
                    cy={node.y - 17}
                    r={4}
                    fill={online ? '#22c55e' : '#475569'}
                    filter={online ? 'url(#glow-green)' : undefined}
                  />
                </g>
              )
            })}
          </svg>
        </div>

        {/* 우측 패널 */}
        <div className="xl:w-80 flex flex-col gap-4">
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
            className="rounded-xl border p-3 flex-1 min-h-0"
            style={{ borderColor: 'rgba(51,65,85,0.5)', background: 'rgba(30,41,59,0.6)' }}
          >
            <div className="text-xs font-semibold text-slate-400 mb-2">RECENT ACTIVITY</div>
            <div className="space-y-1.5 overflow-y-auto max-h-[320px]">
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

      {/* 하단 에이전트 상태 그리드 */}
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
        {Object.entries(AGENT_PROFILES).map(([id, p]) => {
          const online = onlineSet.has(id)
          const color = AGENT_COLORS[id] || '#64748b'
          return (
            <div
              key={id}
              className="flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg border cursor-pointer"
              style={{
                borderColor: online ? `${color}40` : 'rgba(51,65,85,0.3)',
                background: online ? `${color}0a` : 'transparent',
                color: online ? '#e2e8f0' : '#475569',
              }}
              onClick={() => setSelectedAgent(selectedAgent === id ? null : id)}
            >
              <span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{
                  background: online ? '#22c55e' : '#475569',
                  boxShadow: online ? '0 0 6px #22c55e' : 'none',
                }}
              />
              {p.emoji} {p.name}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── KPI 카드 ────────────────────────────────────────────────────
function KpiCard({ label, value, color }: { label: string; value: string | number; color: string }) {
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
    </div>
  )
}
