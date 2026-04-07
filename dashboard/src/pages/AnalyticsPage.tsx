// 분석 페이지 — 세션 볼륨 추이 + 에이전트별 메시지 수 + 도구 사용량 + 에이전트 활동
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  BarChart, Bar, Cell,
} from 'recharts'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'
import agentsConfig from '@agents'

// 바 차트 색상 — config/agents.json 단일 소스
const BAR_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { barColor: string | null }).barColor !== null)
    .map(([id, a]) => [id, (a as { barColor: string }).barColor])
)

// === 타입 ===
interface VolumeDay {
  date: string
  count: number
}

interface AgentCount {
  id: string
  name: string
  count: number
}

// === 도구 사용량 (시뮬레이션, 도구 추적 미구현) ===
const TOOL_DATA = [
  { tool: 'send_message', count: 145, color: '#3b82f6' },
  { tool: 'check_status', count: 89, color: '#22c55e' },
  { tool: 'db_query', count: 67, color: '#a855f7' },
  { tool: 'file_read', count: 52, color: '#eab308' },
  { tool: 'web_search', count: 38, color: '#ef4444' },
  { tool: 'code_edit', count: 31, color: '#06b6d4' },
  { tool: 'report_gen', count: 24, color: '#f97316' },
]

// === 로딩 스켈레톤 ===
function ChartSkeleton() {
  return (
    <div className="flex items-center justify-center h-[220px]">
      <div className="flex flex-col items-center gap-2">
        <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
        <span className="text-xs text-gray-600">로딩 중...</span>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  // 에이전트별 메시지 수 (운영 대시보드에서 이동)
  const messages = useAgentStore((s) => s.messages)
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

  // 볼륨 데이터 (API)
  const [volumeData, setVolumeData] = useState<{ date: string; 메시지: number }[]>([])
  const [volumeLoading, setVolumeLoading] = useState(true)

  // 에이전트 활동 데이터 (API)
  const [agentActivity, setAgentActivity] = useState<{ agent: string; id: string; 활동량: number }[]>([])
  const [agentLoading, setAgentLoading] = useState(true)

  // 태스크 완료율 (시뮬레이션)
  const taskStats = { total: 47, completed: 39, rate: 83 }

  // === 볼륨 데이터 로드 ===
  const loadVolume = useCallback(async () => {
    try {
      setVolumeLoading(true)
      const res = await fetch('/api/stats/volume')
      if (!res.ok) throw new Error('fetch failed')
      const json = await res.json() as { days: VolumeDay[] }
      setVolumeData(
        (json.days ?? []).map((d) => ({ date: d.date, 메시지: d.count }))
      )
    } catch {
      setVolumeData([])
    } finally {
      setVolumeLoading(false)
    }
  }, [])

  // === 에이전트 활동 로드 ===
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
            return {
              agent: profile ? `${profile.emoji} ${profile.name}` : a.name,
              id: a.id,
              활동량: a.count,
            }
          })
          .filter((d) => d.활동량 > 0)
          .sort((a, b) => b.활동량 - a.활동량)
      )
    } catch {
      setAgentActivity([])
    } finally {
      setAgentLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadVolume()
    void loadAgents()
  }, [loadVolume, loadAgents])

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-white">📈 분석</h1>
        <p className="text-gray-400 text-sm mt-1">세션 볼륨 추이 · 도구 사용량 · 에이전트 활동</p>
      </div>

      {/* 에이전트별 메시지 수 바 차트 */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5 mb-4">
        <div className="text-sm font-semibold text-gray-300 mb-3">에이전트별 메시지 수</div>
        {messages.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">메시지 데이터 없음</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={msgBarData} layout="vertical" margin={{ left: 10, right: 20 }}>
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
              <YAxis
                type="category"
                dataKey="agent"
                width={100}
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#d1d5db' }}
                itemStyle={{ color: '#9ca3af' }}
              />
              <Bar dataKey="count" name="메시지" radius={[0, 4, 4, 0]}>
                {msgBarData.map((entry) => (
                  <Cell key={entry.id} fill={BAR_COLORS[entry.id] ?? '#6b7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 세션 볼륨 추이 (7일) */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="text-sm font-semibold text-gray-300 mb-3">세션 볼륨 추이 (7일)</div>
          {volumeLoading ? (
            <ChartSkeleton />
          ) : volumeData.length === 0 ? (
            <div className="flex items-center justify-center h-[220px] text-gray-500 text-sm">데이터 없음</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={volumeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
                <Tooltip
                  contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                  labelStyle={{ color: '#d1d5db' }}
                  itemStyle={{ color: '#9ca3af' }}
                />
                <Line
                  type="monotone"
                  dataKey="메시지"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ fill: '#3b82f6', r: 3 }}
                  activeDot={{ r: 5, fill: '#60a5fa' }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 도구별 사용량 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-300">도구별 사용량</span>
            <span className="text-xs text-gray-600">시뮬레이션 데이터</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={TOOL_DATA} layout="vertical" margin={{ left: 5, right: 20 }}>
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#374151' }} />
              <YAxis
                type="category"
                dataKey="tool"
                width={95}
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#d1d5db' }}
                itemStyle={{ color: '#9ca3af' }}
              />
              <Bar dataKey="count" name="호출" radius={[0, 4, 4, 0]}>
                {TOOL_DATA.map((entry) => (
                  <Cell key={entry.tool} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 에이전트별 활동량 */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-5">
          <div className="text-sm font-semibold text-gray-300 mb-3">에이전트별 활동량</div>
          {agentLoading ? (
            <ChartSkeleton />
          ) : agentActivity.length === 0 ? (
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
                      <div
                        className="bg-blue-500 h-full rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
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
                <circle
                  cx="50" cy="50" r="42" fill="none"
                  stroke="#22c55e" strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${taskStats.rate * 2.64} ${264 - taskStats.rate * 2.64}`}
                />
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
