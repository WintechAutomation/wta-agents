// 스케줄 관리 — APScheduler 기반 크론 작업 CRUD
import { useState, useEffect, useCallback } from 'react'

interface JobRun {
  run_id: string
  job_id: string
  name: string
  status: 'success' | 'error' | 'timeout'
  started: string
  finished: string
  output: string
}

interface Job {
  id: string
  name: string
  description: string
  command: string
  cron: string
  enabled: boolean
  created_at: string
  next_run: string | null
  last_runs: JobRun[]
}

interface FormData {
  name: string
  description: string
  command: string
  cron: string
  enabled: boolean
}

const EMPTY_FORM: FormData = { name: '', description: '', command: '', cron: '0 9 * * *', enabled: true }

function statusColor(status: string) {
  if (status === 'success') return 'text-green-400'
  if (status === 'error')   return 'text-red-400'
  return 'text-yellow-400'
}

function statusIcon(status: string) {
  if (status === 'success') return '✓'
  if (status === 'error')   return '✗'
  return '⏱'
}

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ko-KR', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return iso }
}

function CronBadge({ cron }: { cron: string }) {
  return (
    <span className="font-mono text-xs bg-gray-800 text-blue-300 px-2 py-0.5 rounded">
      {cron}
    </span>
  )
}

export default function CronPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<FormData>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set())
  const [expandedLog, setExpandedLog] = useState<string | null>(null)
  const [logData, setLogData] = useState<Record<string, JobRun[]>>({})
  const [error, setError] = useState<string | null>(null)

  const loadJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/jobs')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json() as Job[]
      setJobs(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadJobs()
    const id = setInterval(loadJobs, 15000)
    return () => clearInterval(id)
  }, [loadJobs])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const err = await res.json() as { error: string }
        throw new Error(err.error)
      }
      setShowForm(false)
      setForm(EMPTY_FORM)
      await loadJobs()
    } catch (e) {
      alert('생성 실패: ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setSaving(false)
    }
  }

  async function handleToggle(job: Job) {
    try {
      await fetch(`/api/jobs/${job.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !job.enabled }),
      })
      await loadJobs()
    } catch { /* ignore */ }
  }

  async function handleDelete(job: Job) {
    if (!confirm(`"${job.name}" 작업을 삭제하시겠습니까?`)) return
    try {
      await fetch(`/api/jobs/${job.id}`, { method: 'DELETE' })
      await loadJobs()
    } catch { /* ignore */ }
  }

  async function handleRunNow(job: Job) {
    setRunningIds(prev => new Set(prev).add(job.id))
    try {
      const res = await fetch(`/api/jobs/${job.id}/run`, { method: 'POST' })
      const data = await res.json() as { message?: string }
      if (data.message) alert(data.message)
      setTimeout(loadJobs, 2000)
    } catch { /* ignore */ } finally {
      setTimeout(() => {
        setRunningIds(prev => {
          const next = new Set(prev)
          next.delete(job.id)
          return next
        })
      }, 3000)
    }
  }

  async function handleExpandLog(jobId: string) {
    if (expandedLog === jobId) {
      setExpandedLog(null)
      return
    }
    try {
      const res = await fetch(`/api/jobs/${jobId}/logs`)
      const data = await res.json() as JobRun[]
      setLogData(prev => ({ ...prev, [jobId]: data }))
      setExpandedLog(jobId)
    } catch { /* ignore */ }
  }

  const activeCount  = jobs.filter(j => j.enabled).length
  const totalCount   = jobs.length

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-bold text-white" style={{ color: '#ffffff' }}>⏰ 스케줄 관리</h1>
          <p className="text-gray-500 text-xs mt-0.5">크론 작업 등록 · 실행 이력 · 다음 실행 시각</p>
        </div>
        <button
          onClick={() => { setShowForm(true); setForm(EMPTY_FORM) }}
          className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
        >
          + 새 작업
        </button>
      </div>

      {/* 요약 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-blue-400">{totalCount}</div>
          <div className="text-xs text-gray-500 mt-1">전체 작업</div>
        </div>
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-green-400">{activeCount}</div>
          <div className="text-xs text-gray-500 mt-1">활성</div>
        </div>
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-gray-400">{totalCount - activeCount}</div>
          <div className="text-xs text-gray-500 mt-1">비활성</div>
        </div>
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 text-center">
          <div className="text-2xl font-bold text-purple-400">
            {jobs.filter(j => j.last_runs?.[0]?.status === 'success').length}
          </div>
          <div className="text-xs text-gray-500 mt-1">마지막 성공</div>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm">
          API 오류: {error}
        </div>
      )}

      {/* 작업 목록 */}
      {loading ? (
        <div className="text-center text-gray-500 py-12">로딩 중...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center text-gray-600 py-12">
          등록된 스케줄 작업이 없습니다.<br />
          <span className="text-sm text-gray-400">+ 새 작업 버튼으로 추가하세요.</span>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map(job => {
            const lastRun = job.last_runs?.[0]
            const isRunning = runningIds.has(job.id)
            const isExpanded = expandedLog === job.id
            return (
              <div
                key={job.id}
                className={`bg-gray-900 rounded-2xl border transition-colors ${
                  job.enabled ? 'border-gray-800' : 'border-gray-800 opacity-60'
                }`}
              >
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    {/* 활성화 토글 */}
                    <button
                      onClick={() => handleToggle(job)}
                      className={`mt-0.5 flex-shrink-0 w-10 h-5 rounded-full relative transition-colors ${
                        job.enabled ? 'bg-green-500' : 'bg-gray-700'
                      }`}
                      title={job.enabled ? '비활성화' : '활성화'}
                    >
                      <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${
                        job.enabled ? 'left-5' : 'left-0.5'
                      }`} />
                    </button>

                    {/* 작업 정보 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-white">{job.name}</span>
                        <CronBadge cron={job.cron} />
                        {lastRun && (
                          <span className={`text-xs font-mono ${statusColor(lastRun.status)}`}>
                            {statusIcon(lastRun.status)} {lastRun.status}
                          </span>
                        )}
                      </div>
                      {job.description && (
                        <div className="text-xs text-gray-500 mt-0.5">{job.description}</div>
                      )}
                      <div className="text-xs text-gray-600 font-mono mt-1 truncate">{job.command}</div>
                      <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
                        <span>다음 실행: <span className="text-gray-300">{fmtTime(job.next_run)}</span></span>
                        {lastRun && (
                          <span>마지막 실행: <span className="text-gray-300">{fmtTime(lastRun.started)}</span></span>
                        )}
                        <span>등록: <span className="text-gray-600">{fmtTime(job.created_at)}</span></span>
                      </div>
                    </div>

                    {/* 액션 버튼 */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleExpandLog(job.id)}
                        className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-800 transition-colors"
                        title="실행 이력"
                      >
                        {isExpanded ? '▲ 로그' : '▼ 로그'}
                      </button>
                      <button
                        onClick={() => handleRunNow(job)}
                        disabled={isRunning}
                        className="text-xs bg-blue-800 hover:bg-blue-700 text-blue-200 px-3 py-1 rounded-lg transition-colors disabled:opacity-40"
                      >
                        {isRunning ? '실행 중...' : '▶ 실행'}
                      </button>
                      <button
                        onClick={() => handleDelete(job)}
                        className="text-xs text-red-500 hover:text-red-400 px-2 py-1 rounded hover:bg-gray-800 transition-colors"
                        title="삭제"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </div>

                {/* 실행 이력 패널 */}
                {isExpanded && (
                  <div className="border-t border-gray-800 p-4">
                    <div className="text-xs font-semibold text-gray-400 mb-2">실행 이력 (최신 순)</div>
                    {(logData[job.id] ?? []).length === 0 ? (
                      <div className="text-gray-600 text-xs py-2">실행 이력 없음</div>
                    ) : (
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {(logData[job.id] ?? []).map(run => (
                          <div key={run.run_id} className="bg-gray-800 rounded-lg p-3 text-xs">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`font-semibold ${statusColor(run.status)}`}>
                                {statusIcon(run.status)} {run.status}
                              </span>
                              <span className="text-gray-500">{fmtTime(run.started)}</span>
                              <span className="text-gray-600">~ {fmtTime(run.finished)}</span>
                            </div>
                            {run.output && (
                              <pre className="text-gray-400 font-mono text-[10px] whitespace-pre-wrap break-all mt-1 max-h-24 overflow-y-auto">
                                {run.output}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 생성 모달 */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-lg font-bold text-white mb-4">새 스케줄 작업</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 block mb-1">작업 이름 *</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="CS 임베딩 동기화"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">설명</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="작업 설명 (선택)"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">실행 명령 *</label>
                <input
                  type="text"
                  required
                  value={form.command}
                  onChange={e => setForm(f => ({ ...f, command: e.target.value }))}
                  placeholder="python C:/MES/wta-agents/scripts/cs-embed.py"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Cron 표현식 *
                  <span className="text-gray-600 ml-2">분 시 일 월 요일</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.cron}
                  onChange={e => setForm(f => ({ ...f, cron: e.target.value }))}
                  placeholder="0 2 * * *"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 font-mono focus:outline-none focus:border-blue-500"
                />
                <div className="text-xs text-gray-600 mt-1 space-y-0.5">
                  <div>예시: <code className="text-blue-400">0 2 * * *</code> 매일 새벽 2시, <code className="text-blue-400">*/30 * * * *</code> 30분마다</div>
                  <div><code className="text-blue-400">0 9 * * 1-5</code> 평일 오전 9시, <code className="text-blue-400">0 0 * * 0</code> 매주 일요일 자정</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="form-enabled"
                  checked={form.enabled}
                  onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))}
                  className="accent-blue-500"
                />
                <label htmlFor="form-enabled" className="text-sm text-gray-300">즉시 활성화</label>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium py-2 rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold py-2 rounded-lg transition-colors disabled:opacity-40"
                >
                  {saving ? '등록 중...' : '등록'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
