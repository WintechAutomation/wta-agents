// 시스템 개요 — KPI + 에이전트 모니터 + 분석 통합 페이지
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  PieChart, Pie, Cell,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  BarChart, Bar,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'
import agentsConfig from '@agents'

// ── 공통 상수 ─────────────────────────────────────────────────
const TOOLTIP_STYLE = {
  contentStyle: { background: '#1f2937', border: '1px solid #374151', borderRadius: '8px' },
  labelStyle: { color: '#d1d5db' },
  itemStyle: { color: '#9ca3af' },
}

const TOOL_COLORS = [
  '#60a5fa', '#34d399', '#f87171', '#fbbf24', '#a78bfa',
  '#fb7185', '#38bdf8', '#4ade80', '#facc15', '#c084fc',
]

// 바 차트 색상 (agents.json)
const BAR_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { barColor: string | null }).barColor !== null)
    .map(([id, a]) => [id, (a as { barColor: string }).barColor])
)

// 카테고리별 에이전트
const CATEGORY_AGENTS: Record<string, string[]> = Object.entries(agentsConfig)
  .filter(([, a]) => (a as { enabled: boolean; category: string | null }).enabled && (a as { category: string | null }).category)
  .reduce<Record<string, string[]>>((acc, [id, a]) => {
    const cat = (a as { category: string }).category
    ;(acc[cat] ??= []).push(id)
    return acc
  }, {})

const MODEL_COLORS: Record<string, string> = {
  'claude-opus-4': '#8b5cf6',
  'claude-sonnet-4-6': '#3b82f6',
  'claude-haiku-4-5': '#22c55e',
}
const MODEL_LABELS: Record<string, string> = {
  'claude-opus-4': 'Opus',
  'claude-sonnet-4-6': 'Sonnet',
  'claude-haiku-4-5': 'Haiku',
}

// 도구 사용량 (시뮬레이션)
const TOOL_MOCK = [
  { tool: 'send_message', count: 145, color: '#3b82f6' },
  { tool: 'check_status', count: 89,  color: '#22c55e' },
  { tool: 'db_query',     count: 67,  color: '#a855f7' },
  { tool: 'file_read',    count: 52,  color: '#eab308' },
  { tool: 'web_search',   count: 38,  color: '#ef4444' },
  { tool: 'code_edit',    count: 31,  color: '#06b6d4' },
  { tool: 'report_gen',   count: 24,  color: '#f97316' },
]

// ── 서브 컴포넌트 ─────────────────────────────────────────────
function KpiCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
      <div className="text-xs text-gray-500 mb-2">{label}</div>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

function ChartSkeleton() {
  return (
    <div className="flex items-center justify-center h-[200px]">
      <div className="flex flex-col items-center gap-2">
        <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
        <span className="text-xs text-gray-600">로딩 중...</span>
      </div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-base font-semibold text-white mb-3 pt-2 border-t border-gray-800">
      {children}
    </h2>
  )
}

// 마지막 활동 이후 경과 시간(초)
function secondsSince(ts: string | undefined): number {
  if (!ts) return Infinity
  const d = new Date(ts.replace(' ', 'T'))
  return (Date.now() - d.getTime()) / 1000
}

interface VolumeDay  { date: string; count: number }
interface AgentCount { id: string; name: string; count: number }

// ── 메인 컴포넌트 ─────────────────────────────────────────────
export default function OverviewPage() {
  const stats      = useAgentStore((s) => s.stats)
  const agents     = useAgentStore((s) => s.agents)
  const messages   = useAgentStore((s) => s.messages)
  const toolLogs   = useAgentStore((s) => s.toolLogs)
  const toolStats  = useAgentStore((s) => s.toolStats)

  const onlineAgents = agents.filter((a) => a.online)
  const totalToolCalls = Object.values(toolStats.by_agent).reduce((s, n) => s + n, 0)

  // ── 레이더 데이터 ─────────────────────────────────────────
  const radarData = useMemo(() => {
    const onlineSet = new Set(agents.filter((a) => a.online).map((a) => a.agent_id))
    return Object.entries(CATEGORY_AGENTS).map(([category, agentIds]) => ({
      category,
      활동: agentIds.filter((id) => onlineSet.has(id)).length,
      전체: agentIds.length,
    }))
  }, [agents])

  // ── 모델 분포 ─────────────────────────────────────────────
  const modelData = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const p of Object.values(AGENT_PROFILES)) {
      counts[p.model] = (counts[p.model] ?? 0) + 1
    }
    return Object.entries(counts).map(([model, count]) => ({
      name: MODEL_LABELS[model] ?? model, value: count, model,
    }))
  }, [])

  // ── 에이전트별 마지막 도구 사용 ───────────────────────────
  const lastActivity = useMemo(() => {
    const map: Record<string, string> = {}
    for (const log of toolLogs) {
      if (!map[log.agent_id] || log.timestamp > map[log.agent_id]) {
        map[log.agent_id] = log.timestamp
      }
    }
    return map
  }, [toolLogs])

  // ── 에이전트별 도구 호출 차트 ────────────────────────────
  const agentChartData = useMemo(() =>
    Object.entries(toolStats.by_agent)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([id, count]) => ({ name: AGENT_PROFILES[id]?.name ?? id, count })),
    [toolStats.by_agent]
  )

  // ── 도구별 사용량 차트 ────────────────────────────────────
  const toolChartData = useMemo(() =>
    Object.entries(toolStats.by_tool)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([tool, count]) => ({ name: tool, count })),
    [toolStats.by_tool]
  )

  // ── 최근 로그 ─────────────────────────────────────────────
  const recentLogs = useMemo(() => [...toolLogs].reverse().slice(0, 50), [toolLogs])

  // ── 에이전트별 메시지 수 ──────────────────────────────────
  const msgBarData = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const msg of messages) {
      counts[msg.from] = (counts[msg.from] ?? 0) + 1
    }
    return Object.keys(AGENT_PROFILES)
      .map((id) => ({
        agent: AGENT_PROFILES[id].emoji + ' ' + AGENT_PROFILES[id].name,
        id,
        count: counts[id] ?? 0,
      }))
      .sort((a, b) => b.count - a.count)
  }, [messages])

  // ── API 데이터 ────────────────────────────────────────────
  const [volumeData, setVolumeData]     = useState<{ date: string; 메시지: number }[]>([])
  const [volumeLoading, setVolumeLoading] = useState(true)
  const [agentActivity, setAgentActivity] = useState<{ agent: string; id: string; 활동량: number }[]>([])
  const [agentLoading, setAgentLoading]   = useState(true)

  const loadVolume = useCallback(async () => {
    try {
      setVolumeLoading(true)
      const res = await fetch('/api/stats/volume')
      if (!res.ok) throw new Error('fetch failed')
      const json = await res.json() as { days: VolumeDay[] }
      setVolumeData((json.days ?? []).map((d) => ({ date: d.date, 메시지: d.count })))
    } catch { setVolumeData([]) }
    finally { setVolumeLoading(false) }
  }, [])

  const loadAgents = useCallback(async () => {
    try {
      setAgentLoading(true)
      const res = await fetch('/api/stats/agents')
      if (!res.ok) throw new Error('fetch failed')
      const json = await res.json() as { agents: AgentCount[] }
      setAgentActivity(
        (json.agents ?? [])
          .map((a) => {
            const profile = AGENT_PROFILES[a.id]
            return { agent: profile ? `${profile.emoji} ${profile.name}` : a.name, id: a.id, 활동량: a.count }
          })
          .filter((d) => d.활동량 > 0)
          .sort((a, b) => b.활동량 - a.활동량)
      )
    } catch { setAgentActivity([]) }
    finally { setAgentLoading(false) }
  }, [])

  useEffect(() => {
    void loadVolume()
    void loadAgents()
  }, [loadVolume, loadAgents])

  const taskStats = { total: 47, completed: 39, rate: 83 }

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-sm font-bold text-white" style={{ color: '#ffffff' }}>📊 시스템 개요</h1>
        <p className="text-gray-500 text-xs mt-0.5">WTA AI 에이전트 시스템 현황 · 모니터 · 분석</p>
      </div>

      {/* ── KPI 카드 ── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard label="온라인 에이전트"   value={`${stats.online_count}/${stats.total_agents}`} sub="실시간"              color="text-green-400"  />
        <KpiCard label="총 도구 호출"       value={totalToolCalls}                                sub="세션 누적"           color="text-blue-400"   />
        <KpiCard label="시스템 업타임"      value={stats.uptime}                                  sub="마지막 재시작 이후"  color="text-purple-400" />
        <KpiCard label="MES 연동"           value="정상"                                           sub="mes-wta.com"         color="text-yellow-400" />
      </div>

      {/* ── 온라인 에이전트 ── */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
        <div className="text-sm font-semibold text-gray-300 mb-3">온라인 에이전트</div>
        <div className="flex flex-wrap gap-2">
          {onlineAgents.map((a) => (
            <span key={a.agent_id} className="px-2.5 py-1 bg-green-500/10 border border-green-500/30 rounded-full text-xs text-green-400">
              {a.emoji} {a.name}
            </span>
          ))}
          {onlineAgents.length === 0 && <span className="text-xs text-gray-500">온라인 에이전트 없음</span>}
        </div>
      </div>

      {/* ── 카테고리 레이더 + 모델 분포 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="text-sm font-semibold text-gray-300 mb-3">카테고리별 에이전트 활동</div>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#374151" />
              <PolarAngleAxis dataKey="category" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <PolarRadiusAxis tick={{ fill: '#6b7280', fontSize: 10 }} domain={[0, 'dataMax']} />
              <Radar name="전체" dataKey="전체" stroke="#6b7280" fill="#6b7280" fillOpacity={0.15} />
              <Radar name="활동" dataKey="활동" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="text-sm font-semibold text-gray-300 mb-3">에이전트 모델 분포</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={modelData} cx="50%" cy="50%" innerRadius={55} outerRadius={95}
                paddingAngle={4} dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}>
                {modelData.map((entry) => (
                  <Cell key={entry.model} fill={MODEL_COLORS[entry.model] ?? '#6b7280'} />
                ))}
              </Pie>
              <Tooltip {...TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 에이전트별/도구별 도구 호출 차트 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-white mb-4">에이전트별 도구 호출 수</h2>
          {agentChartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-600 text-sm">데이터 없음</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={agentChartData} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {agentChartData.map((_, i) => <Cell key={i} fill={TOOL_COLORS[i % TOOL_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-white mb-4">도구별 사용량 (Top 10)</h2>
          {toolChartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-600 text-sm">데이터 없음</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={toolChartData} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 10 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#34d399" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 최근 도구 사용 타임라인 */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
        <h2 className="text-sm font-semibold text-white mb-4">최근 도구 사용 타임라인</h2>
        {recentLogs.length === 0 ? (
          <div className="text-gray-600 text-sm text-center py-6">활동 없음 — 에이전트가 작업을 시작하면 여기에 표시됩니다</div>
        ) : (
          <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
            {recentLogs.map((log, i) => {
              const profile = AGENT_PROFILES[log.agent_id]
              return (
                <div key={i} className="flex items-center gap-3 py-1.5 border-b border-gray-800 last:border-0">
                  <span className="text-base flex-shrink-0">{profile?.emoji ?? '🤖'}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0 w-16 truncate">{profile?.name ?? log.agent_id}</span>
                  <span className="text-xs font-mono text-blue-300 flex-1 truncate">{log.tool_name}</span>
                  <span className="text-xs text-gray-600 flex-shrink-0">{log.timestamp.slice(11, 19)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ════ 분석 ════ */}
      <SectionTitle>📈 분석</SectionTitle>

      {/* 에이전트별 메시지 수 */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
        <div className="text-sm font-semibold text-gray-300 mb-3">에이전트별 메시지 수</div>
        {messages.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">메시지 데이터 없음</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={msgBarData} layout="vertical" margin={{ left: 10, right: 20 }}>
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
              <YAxis type="category" dataKey="agent" width={100}
                tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="count" name="메시지" radius={[0, 4, 4, 0]}>
                {msgBarData.map((entry) => <Cell key={entry.id} fill={BAR_COLORS[entry.id] ?? '#6b7280'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 세션 볼륨 추이 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="text-sm font-semibold text-gray-300 mb-3">세션 볼륨 추이 (7일)</div>
          {volumeLoading ? <ChartSkeleton /> : volumeData.length === 0 ? (
            <div className="flex items-center justify-center h-[200px] text-gray-500 text-sm">데이터 없음</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={volumeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Line type="monotone" dataKey="메시지" stroke="#3b82f6" strokeWidth={2}
                  dot={{ fill: '#3b82f6', r: 3 }} activeDot={{ r: 5, fill: '#60a5fa' }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 도구별 사용량 (시뮬레이션) */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-300">도구별 사용량</span>
            <span className="text-xs text-gray-600">시뮬레이션</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={TOOL_MOCK} layout="vertical" margin={{ left: 5, right: 20 }}>
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
              <YAxis type="category" dataKey="tool" width={95}
                tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="count" name="호출" radius={[0, 4, 4, 0]}>
                {TOOL_MOCK.map((entry) => <Cell key={entry.tool} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 에이전트별 활동량 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="text-sm font-semibold text-gray-300 mb-3">에이전트별 활동량</div>
          {agentLoading ? <ChartSkeleton /> : agentActivity.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-gray-500 text-sm">데이터 수집 중</div>
          ) : (
            <div className="space-y-2">
              {agentActivity.slice(0, 8).map((item) => {
                const max = agentActivity[0].활동량
                const pct = max > 0 ? Math.round((item.활동량 / max) * 100) : 0
                return (
                  <div key={item.id} className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 w-24 truncate">{item.agent}</span>
                    <div className="flex-1 bg-gray-800 rounded-full h-3 overflow-hidden">
                      <div className="bg-blue-500 h-full rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-gray-400 w-8 text-right">{item.활동량}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 태스크 완료율 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-300">태스크 완료율</span>
            <span className="text-xs text-gray-600">시뮬레이션</span>
          </div>
          <div className="flex flex-col items-center justify-center h-48">
            <div className="relative w-32 h-32">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#1f2937" strokeWidth="8" />
                <circle cx="50" cy="50" r="42" fill="none" stroke="#22c55e" strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${taskStats.rate * 2.64} ${264 - taskStats.rate * 2.64}`} />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold text-green-400">{taskStats.rate}%</span>
              </div>
            </div>
            <div className="mt-3 flex gap-4 text-xs text-gray-500">
              <span>전체 {taskStats.total}건</span>
              <span>완료 {taskStats.completed}건</span>
              <span>미완료 {taskStats.total - taskStats.completed}건</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
