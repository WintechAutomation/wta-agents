// 작업 큐 관리 — 팀원별 지시 작업 현황판
import { useState, useEffect, useCallback } from 'react'
import { useAgentStore, AGENT_PROFILES } from '@/store/agentStore'
import agentsConfig from '@agents'

type TaskStatus   = 'pending' | 'in_progress' | 'done' | 'cancelled'
type TaskPriority = 'high' | 'medium' | 'low'

interface Task {
  id: string
  agent: string
  task: string
  message: string
  status: TaskStatus
  priority: TaskPriority
  created_at: string
  updated_at: string
  last_report_at: string | null
  completed_at: string | null
}

function isStalled(task: Task): boolean {
  if (task.status !== 'in_progress') return false
  const updated = task.updated_at
  if (!updated) return false
  try {
    const dt = new Date(updated)
    const elapsed = (Date.now() - dt.getTime()) / 1000
    return elapsed > 15 * 60
  } catch { return false }
}

interface FormData {
  agent: string
  task: string
  message: string
  status: TaskStatus
  priority: TaskPriority
}

const EMPTY_FORM: FormData = {
  agent: '', task: '', message: '', status: 'pending', priority: 'medium',
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  pending: '대기', in_progress: '진행중', done: '완료', cancelled: '취소',
}

const STATUS_COLORS: Record<TaskStatus, string> = {
  pending:     'bg-gray-700 text-gray-300',
  in_progress: 'bg-blue-900 text-blue-300',
  done:        'bg-green-900 text-green-300',
  cancelled:   'bg-gray-800 text-gray-500',
}

const STATUS_DOT: Record<TaskStatus, string> = {
  pending:     'bg-gray-500',
  in_progress: 'bg-blue-400 animate-pulse',
  done:        'bg-green-400',
  cancelled:   'bg-gray-600',
}

const PRIORITY_BADGE: Record<TaskPriority, string> = {
  high:   'text-red-400 border border-red-800',
  medium: 'text-yellow-400 border border-yellow-800',
  low:    'text-gray-500 border border-gray-700',
}

const PRIORITY_LABEL: Record<TaskPriority, string> = { high: 'HIGH', medium: 'MED', low: 'LOW' }

function fmtTime(s: string | null | undefined) {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString('ko-KR', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch { return s }
}

const STATUSES: TaskStatus[]   = ['pending', 'in_progress', 'done', 'cancelled']
const PRIORITIES: TaskPriority[] = ['high', 'medium', 'low']

export default function TaskQueuePage() {
  const agentProfiles = AGENT_PROFILES
  const agentsCfg     = agentsConfig as Record<string, { enabled?: boolean }>

  const [tasks, setTasks]         = useState<Task[]>([])
  const [loading, setLoading]     = useState(true)
  const [filterAgent, setFilterAgent] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('active')
  const [showForm, setShowForm]   = useState(false)
  const [form, setForm]           = useState<FormData>(EMPTY_FORM)
  const [saving, setSaving]       = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [error, setError]         = useState<string | null>(null)

  const loadTasks = useCallback(async () => {
    try {
      const url = filterAgent !== 'all'
        ? `/api/task-queue?agent=${filterAgent}`
        : '/api/task-queue'
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setTasks(await res.json() as Task[])
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [filterAgent])

  useEffect(() => {
    void loadTasks()
    const id = setInterval(loadTasks, 20000)
    return () => clearInterval(id)
  }, [loadTasks])

  const visibleTasks = tasks.filter(t => {
    if (filterStatus === 'active') return t.status === 'pending' || t.status === 'in_progress'
    if (filterStatus === 'done')   return t.status === 'done' || t.status === 'cancelled'
    return true
  })

  // 팀원별 그룹화 (filterAgent = all 일 때)
  const grouped = filterAgent === 'all'
    ? Object.entries(
        visibleTasks.reduce<Record<string, Task[]>>((acc, t) => {
          (acc[t.agent] = acc[t.agent] ?? []).push(t); return acc
        }, {})
      ).sort(([a], [b]) => a.localeCompare(b))
    : [[ filterAgent, visibleTasks ] as [string, Task[]]]

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await fetch('/api/task-queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) { const j = await res.json() as { error: string }; throw new Error(j.error) }
      setShowForm(false); setForm(EMPTY_FORM)
      await loadTasks()
    } catch (e) {
      alert('추가 실패: ' + (e instanceof Error ? e.message : String(e)))
    } finally { setSaving(false) }
  }

  async function handleStatusChange(task: Task, status: TaskStatus) {
    try {
      await fetch(`/api/task-queue/${task.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      await loadTasks()
    } catch { /* ignore */ }
  }

  async function handleDelete(task: Task) {
    if (!confirm(`"${task.task}" 작업을 삭제하시겠습니까?`)) return
    try {
      await fetch(`/api/task-queue/${task.id}`, { method: 'DELETE' })
      await loadTasks()
    } catch { /* ignore */ }
  }

  // 요약 통계
  const countByStatus = tasks.reduce<Record<string, number>>((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1; return acc
  }, {})
  const stalledCount = tasks.filter(isStalled).length

  const agentIds = Object.keys(agentsCfg).length > 0
    ? Object.keys(agentsCfg).filter(id => agentsCfg[id]?.enabled !== false)
    : []

  return (
    <div className="p-3 md:p-4 space-y-2.5">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white" style={{ color: '#ffffff' }}>📋 작업 큐</h1>
          <p className="text-gray-400 text-[11px]">팀원별 지시 작업 현황 · 상태 관리</p>
        </div>
        <button
          onClick={() => { setShowForm(true); setForm(EMPTY_FORM) }}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-3 py-1.5 rounded-md transition-colors"
        >
          + 작업 추가
        </button>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-5 gap-2">
        {(['pending','in_progress','done','cancelled'] as TaskStatus[]).map(s => (
          <div key={s} className="bg-gray-900 rounded-lg border border-gray-800 px-2 py-1.5 text-center">
            <div className={`text-lg font-bold leading-tight ${
              s === 'in_progress' ? 'text-blue-400' :
              s === 'done'        ? 'text-green-400' :
              s === 'cancelled'   ? 'text-gray-600' : 'text-yellow-400'
            }`}>{countByStatus[s] ?? 0}</div>
            <div className="text-[10px] text-gray-500">{STATUS_LABELS[s]}</div>
          </div>
        ))}
        <div className="bg-gray-900 rounded-lg border border-orange-900 px-2 py-1.5 text-center">
          <div className={`text-lg font-bold leading-tight ${stalledCount > 0 ? 'text-orange-400' : 'text-gray-600'}`}>
            {stalledCount}
          </div>
          <div className="text-[10px] text-gray-500">무응답 ⚠️</div>
        </div>
      </div>

      {/* 필터 */}
      <div className="flex flex-wrap gap-1.5">
        <div className="flex gap-0.5 bg-gray-900 rounded p-0.5">
          {(['active','done','all'] as const).map(f => (
            <button key={f} onClick={() => setFilterStatus(f)}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                filterStatus === f ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {f === 'active' ? '활성' : f === 'done' ? '완료/취소' : '전체'}
            </button>
          ))}
        </div>
        <div className="flex gap-0.5 bg-gray-900 rounded p-0.5">
          <button onClick={() => setFilterAgent('all')}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
              filterAgent === 'all' ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-gray-200'
            }`}
          >전체 팀원</button>
          {agentIds.map(id => {
            const p = agentProfiles[id]
            if (!p) return null
            return (
              <button key={id} onClick={() => setFilterAgent(id)}
                className={`px-1.5 py-0.5 rounded text-[11px] transition-colors ${
                  filterAgent === id ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-gray-200'
                }`}
              >{p.emoji} {p.name}</button>
            )
          })}
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* 목록 */}
      {loading ? (
        <div className="text-center text-gray-500 py-8 text-sm">로딩 중...</div>
      ) : grouped.length === 0 || grouped.every(([, ts]) => ts.length === 0) ? (
        <div className="text-center text-gray-600 py-8 text-sm">
          해당 조건의 작업이 없습니다.
        </div>
      ) : (
        <div className="space-y-3">
          {grouped.map(([agent, agentTasks]) => {
            if (agentTasks.length === 0) return null
            const profile = agentProfiles[agent]
            return (
              <div key={agent}>
                {filterAgent === 'all' && (
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-sm">{profile?.emoji ?? '🤖'}</span>
                    <span className="text-xs font-semibold text-gray-300">
                      {profile?.name ?? agent}
                    </span>
                    <span className="text-[10px] text-gray-600">
                      ({agentTasks.filter(t => t.status === 'in_progress').length}진행 / {agentTasks.filter(t => t.status === 'pending').length}대기)
                    </span>
                    <div className="flex-1 h-px bg-gray-800" />
                  </div>
                )}
                <div className="space-y-1">
                  {agentTasks.map(task => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      expanded={expandedId === task.id}
                      onExpand={() => setExpandedId(expandedId === task.id ? null : task.id)}
                      onStatusChange={handleStatusChange}
                      onDelete={handleDelete}
                      showAgent={filterAgent === 'all'}
                      agentProfiles={agentProfiles}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 생성 모달 */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-white mb-4">작업 추가</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">담당 팀원 *</label>
                  <select
                    required
                    value={form.agent}
                    onChange={e => setForm(f => ({ ...f, agent: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="">선택</option>
                    {agentIds.map(id => (
                      <option key={id} value={id}>
                        {agentProfiles[id]?.emoji ?? ''} {agentProfiles[id]?.name ?? id}
                      </option>
                    ))}
                    {agentIds.length === 0 && (
                      <>
                        {['MAX','crafter','db-manager','nc-manager','qa-agent','cs-agent','dev-agent','issue-manager','admin-agent','sales-agent','schedule-agent','docs-agent','design-agent','control-agent'].map(id => (
                          <option key={id} value={id}>{id}</option>
                        ))}
                      </>
                    )}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">우선순위</label>
                  <select
                    value={form.priority}
                    onChange={e => setForm(f => ({ ...f, priority: e.target.value as TaskPriority }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="high">🔴 HIGH</option>
                    <option value="medium">🟡 MEDIUM</option>
                    <option value="low">⚪ LOW</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">작업 요약 *</label>
                <input
                  type="text" required
                  value={form.task}
                  onChange={e => setForm(f => ({ ...f, task: e.target.value }))}
                  placeholder="크론 관리 페이지 개발"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">지시 메시지 전문</label>
                <textarea
                  rows={4}
                  value={form.message}
                  onChange={e => setForm(f => ({ ...f, message: e.target.value }))}
                  placeholder="MAX가 팀원에게 보낸 실제 지시 메시지..."
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">초기 상태</label>
                <select
                  value={form.status}
                  onChange={e => setForm(f => ({ ...f, status: e.target.value as TaskStatus }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="pending">대기</option>
                  <option value="in_progress">진행중</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-2 rounded-lg transition-colors"
                >취소</button>
                <button type="submit" disabled={saving}
                  className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold py-2 rounded-lg transition-colors disabled:opacity-40"
                >{saving ? '추가 중...' : '추가'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 작업 카드 컴포넌트 ──
interface TaskCardProps {
  task: Task
  expanded: boolean
  onExpand: () => void
  onStatusChange: (t: Task, s: TaskStatus) => void
  onDelete: (t: Task) => void
  showAgent: boolean
  agentProfiles: Record<string, { emoji: string; name: string }>
}

function TaskCard({ task, expanded, onExpand, onStatusChange, onDelete, showAgent, agentProfiles }: TaskCardProps) {
  const stalled = isStalled(task)
  return (
    <div className={`bg-gray-900 rounded-lg border transition-colors ${
      task.status === 'cancelled' || task.status === 'done'
        ? 'border-gray-800 opacity-60'
        : stalled
        ? 'border-orange-800'
        : 'border-gray-800'
    }`}>
      <div className="px-2.5 py-1.5">
        <div className="flex items-center gap-2">
          {/* 상태 점 */}
          <span className={`flex-shrink-0 w-1.5 h-1.5 rounded-full ${STATUS_DOT[task.status]}`} />

          {/* 내용 */}
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {showAgent && (
                <span className="text-[10px] text-gray-500">
                  {agentProfiles[task.agent]?.emoji ?? '🤖'} {agentProfiles[task.agent]?.name ?? task.agent}
                </span>
              )}
              <span className={`text-[9px] font-bold px-1 py-px rounded ${PRIORITY_BADGE[task.priority]}`}>
                {PRIORITY_LABEL[task.priority]}
              </span>
              <span className={`text-[9px] px-1 py-px rounded font-medium ${STATUS_COLORS[task.status]}`}>
                {STATUS_LABELS[task.status]}
              </span>
              {stalled && (
                <span className="text-[9px] px-1 py-px rounded font-bold text-orange-400 border border-orange-800 animate-pulse">
                  ⚠️ 무응답
                </span>
              )}
            </div>
            <span className="text-xs text-white font-medium truncate">{task.task}</span>
            <span className="text-[10px] text-gray-600 flex-shrink-0 ml-auto hidden sm:inline">
              {fmtTime(task.created_at)}
              {task.completed_at && <span className="ml-1.5">완료: {fmtTime(task.completed_at)}</span>}
            </span>
          </div>

          {/* 액션 */}
          <div className="flex items-center gap-0.5 flex-shrink-0">
            {task.message && (
              <button onClick={onExpand}
                className="text-[10px] text-gray-600 hover:text-gray-300 px-1 py-0.5 rounded hover:bg-gray-800 transition-colors"
                title="지시 메시지 보기"
              >
                {expanded ? '▲' : '▼'}
              </button>
            )}
            <select
              value={task.status}
              onChange={e => onStatusChange(task, e.target.value as TaskStatus)}
              className="bg-gray-800 border border-gray-700 text-[10px] text-gray-300 rounded px-1 py-0.5 focus:outline-none"
              onClick={e => e.stopPropagation()}
            >
              {(['pending','in_progress','done','cancelled'] as TaskStatus[]).map(s => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </select>
            <button onClick={() => onDelete(task)}
              className="text-[10px] text-red-600 hover:text-red-400 px-1 py-0.5 rounded hover:bg-gray-800 transition-colors"
            >✕</button>
          </div>
        </div>
      </div>

      {/* 지시 메시지 펼쳐보기 */}
      {expanded && task.message && (
        <div className="border-t border-gray-800 px-2.5 py-2">
          <div className="text-[10px] text-gray-500 mb-0.5">지시 메시지</div>
          <pre className="text-[11px] text-gray-300 whitespace-pre-wrap break-words font-sans leading-snug max-h-40 overflow-y-auto">
            {task.message}
          </pre>
        </div>
      )}
    </div>
  )
}
