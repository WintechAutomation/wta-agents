// 실시간 모니터 — 에이전트 상태 + 도구 사용 모니터링
import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'

const TOOL_COLORS = [
  '#60a5fa', '#34d399', '#f87171', '#fbbf24', '#a78bfa',
  '#fb7185', '#38bdf8', '#4ade80', '#facc15', '#c084fc',
]

// 마지막 활동 이후 경과 시간(초) 계산
function secondsSince(ts: string | undefined): number {
  if (!ts) return Infinity
  const d = new Date(ts.replace(' ', 'T'))
  return (Date.now() - d.getTime()) / 1000
}

export default function MonitorPage() {
  const agents    = useAgentStore((s) => s.agents)
  const stats     = useAgentStore((s) => s.stats)
  const toolLogs  = useAgentStore((s) => s.toolLogs)
  const toolStats = useAgentStore((s) => s.toolStats)

  // 에이전트별 마지막 도구 사용 시간
  const lastActivity = useMemo(() => {
    const map: Record<string, string> = {}
    for (const log of toolLogs) {
      if (!map[log.agent_id] || log.timestamp > map[log.agent_id]) {
        map[log.agent_id] = log.timestamp
      }
    }
    return map
  }, [toolLogs])

  // 에이전트별 도구 사용량 차트 데이터 (상위 8개)
  const agentChartData = useMemo(() =>
    Object.entries(toolStats.by_agent)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([id, count]) => ({
        name: AGENT_PROFILES[id]?.name ?? id,
        count,
      })),
    [toolStats.by_agent]
  )

  // 도구별 사용량 차트 데이터 (상위 10개)
  const toolChartData = useMemo(() =>
    Object.entries(toolStats.by_tool)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([tool, count]) => ({ name: tool, count })),
    [toolStats.by_tool]
  )

  // 최근 로그 (최신 50건, 역순)
  const recentLogs = useMemo(() => [...toolLogs].reverse().slice(0, 50), [toolLogs])

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-white">🖥️ 실시간 모니터</h1>
        <p className="text-gray-400 text-sm mt-1">에이전트 상태 · 도구 사용 모니터링</p>
      </div>

      {/* 요약 통계 */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-green-400">{stats.online_count}</div>
          <div className="text-xs text-gray-500 mt-1">온라인</div>
        </div>
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-gray-400">{stats.total_agents - stats.online_count}</div>
          <div className="text-xs text-gray-500 mt-1">오프라인</div>
        </div>
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-blue-400">
            {Object.values(toolStats.by_agent).reduce((s, n) => s + n, 0)}
          </div>
          <div className="text-xs text-gray-500 mt-1">총 도구 호출</div>
        </div>
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-purple-400">{stats.uptime}</div>
          <div className="text-xs text-gray-500 mt-1">업타임</div>
        </div>
      </div>

      {/* 에이전트 상태 그리드 (활동 상태 포함) */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">에이전트 상태</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Object.values(AGENT_PROFILES).map((profile) => {
            const status   = agents.find((a) => a.agent_id === profile.id)
            const online   = status?.online ?? false
            const lastTs   = lastActivity[profile.id]
            const secAgo   = secondsSince(lastTs)
            // 30초 이내 도구 사용 = 작업 중
            const working  = secAgo < 30
            return (
              <div
                key={profile.id}
                className={`flex items-center gap-3 p-3 rounded-xl border ${
                  online
                    ? working
                      ? 'bg-blue-950 border-blue-700'
                      : 'bg-gray-800 border-gray-700'
                    : 'bg-gray-900 border-gray-800 opacity-50'
                }`}
              >
                <div className="relative flex-shrink-0">
                  <span className="text-xl">{profile.emoji}</span>
                  <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-gray-900 ${
                    working ? 'bg-blue-400 animate-pulse' : online ? 'bg-green-400' : 'bg-gray-600'
                  }`} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-white truncate">{profile.name}</div>
                  <div className={`text-xs ${working ? 'text-blue-400' : online ? 'text-green-400' : 'text-gray-600'}`}>
                    {working ? '작업 중' : online ? '대기' : '오프라인'}
                  </div>
                </div>
                {lastTs && (
                  <div className="text-xs text-gray-600 flex-shrink-0">
                    {toolStats.by_agent[profile.id] ?? 0}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 차트 2개 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 에이전트별 도구 사용량 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">에이전트별 도구 호출 수</h2>
          {agentChartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-600 text-sm">데이터 없음</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={agentChartData} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#e5e7eb' }}
                  itemStyle={{ color: '#60a5fa' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {agentChartData.map((_, i) => (
                    <Cell key={i} fill={TOOL_COLORS[i % TOOL_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 도구별 사용량 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">도구별 사용량 (Top 10)</h2>
          {toolChartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-600 text-sm">데이터 없음</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={toolChartData} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 10 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#e5e7eb' }}
                  itemStyle={{ color: '#34d399' }}
                />
                <Bar dataKey="count" fill="#34d399" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 최근 활동 타임라인 */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">최근 도구 사용 타임라인</h2>
        {recentLogs.length === 0 ? (
          <div className="text-gray-600 text-sm text-center py-6">활동 없음 — 에이전트가 작업을 시작하면 여기에 표시됩니다</div>
        ) : (
          <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
            {recentLogs.map((log, i) => {
              const profile = AGENT_PROFILES[log.agent_id]
              return (
                <div key={i} className="flex items-center gap-3 py-1.5 border-b border-gray-800 last:border-0">
                  <span className="text-base flex-shrink-0">{profile?.emoji ?? '🤖'}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0 w-16 truncate">
                    {profile?.name ?? log.agent_id}
                  </span>
                  <span className="text-xs font-mono text-blue-300 flex-1 truncate">{log.tool_name}</span>
                  <span className="text-xs text-gray-600 flex-shrink-0">
                    {log.timestamp.slice(11, 19)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
