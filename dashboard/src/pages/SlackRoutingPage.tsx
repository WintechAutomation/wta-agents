import { useState, useEffect, useCallback } from 'react'

interface SlackOverride {
  mention_required?: boolean
  auto_response?: boolean
  ack_message?: boolean
  context_hint?: string
}

interface RoutingEntry {
  agent_id: string
  agent_name: string
  emoji: string
  slack_channels: string[]
  slack_prefix: string[]
  mention_required: boolean
  auto_response: boolean
  ack_message: boolean
  context_hint: string
  slack_overrides: Record<string, SlackOverride>
}

export default function SlackRoutingPage() {
  const [routing, setRouting] = useState<RoutingEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const fetchRouting = useCallback(async () => {
    try {
      const res = await fetch('/api/slack-routing')
      const data = await res.json()
      setRouting(data.routing ?? [])
      setDirty(false)
    } catch {
      setMessage({ type: 'err', text: '라우팅 설정 로드 실패' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchRouting() }, [fetchRouting])

  function updateEntry(idx: number, field: keyof RoutingEntry, value: unknown) {
    setRouting(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], [field]: value }
      return next
    })
    setDirty(true)
  }

  function updateChannels(idx: number, raw: string) {
    const channels = raw.split(',').map(s => s.trim()).filter(Boolean)
    updateEntry(idx, 'slack_channels', channels)
  }

  function updatePrefix(idx: number, raw: string) {
    const prefixes = raw.split(',').map(s => s.trim()).filter(Boolean)
    updateEntry(idx, 'slack_prefix', prefixes)
  }

  async function handleSave() {
    setSaving(true)
    setMessage(null)
    try {
      const res = await fetch('/api/slack-routing', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ routing }),
      })
      const data = await res.json()
      if (data.ok) {
        setMessage({ type: 'ok', text: '저장 완료' })
        setDirty(false)
      } else {
        setMessage({ type: 'err', text: data.error || '저장 실패' })
      }
    } catch {
      setMessage({ type: 'err', text: '저장 요청 실패' })
    } finally {
      setSaving(false)
    }
  }

  async function handleReload() {
    setReloading(true)
    setMessage(null)
    try {
      const res = await fetch('/api/slack-routing/reload', { method: 'POST' })
      const data = await res.json()
      if (data.ok) {
        setMessage({ type: 'ok', text: `리로드 완료 (채널 ${data.slack_bot?.channels ?? '?'}개)` })
      } else {
        setMessage({ type: 'err', text: data.error || '리로드 실패' })
      }
    } catch {
      setMessage({ type: 'err', text: '리로드 요청 실패 — slack-bot 오프라인?' })
    } finally {
      setReloading(false)
    }
  }

  async function handleSaveAndReload() {
    setSaving(true)
    setMessage(null)
    try {
      const saveRes = await fetch('/api/slack-routing', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ routing }),
      })
      const saveData = await saveRes.json()
      if (!saveData.ok) {
        setMessage({ type: 'err', text: saveData.error || '저장 실패' })
        return
      }
      setDirty(false)
      // 리로드 시도 (실패해도 저장은 성공)
      try {
        const reloadRes = await fetch('/api/slack-routing/reload', { method: 'POST' })
        const reloadData = await reloadRes.json()
        if (reloadData.ok) {
          setMessage({ type: 'ok', text: `저장 + 리로드 완료 (채널 ${reloadData.slack_bot?.channels ?? '?'}개)` })
        } else {
          setMessage({ type: 'ok', text: `저장 완료. 리로드 실패 (slack-bot 재시작 시 자동 반영): ${reloadData.error || ''}` })
        }
      } catch {
        setMessage({ type: 'ok', text: '저장 완료. 리로드 실패 — slack-bot 재시작 시 자동 반영됩니다.' })
      }
    } catch {
      setMessage({ type: 'err', text: '저장 요청 실패' })
    } finally {
      setSaving(false)
    }
  }

  // 전체 채널 목록 (flat view)
  const allChannels: { agent: RoutingEntry; channel: string; isPrefix: boolean }[] = []
  for (const entry of routing) {
    for (const ch of entry.slack_channels) {
      allChannels.push({ agent: entry, channel: ch, isPrefix: false })
    }
    for (const pf of entry.slack_prefix) {
      allChannels.push({ agent: entry, channel: pf, isPrefix: true })
    }
  }

  if (loading) {
    return <div className="p-6 text-gray-400">로딩 중...</div>
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto space-y-6">
      {/* 헤더 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-sm font-bold text-white">슬랙 채널 라우팅 설정</h1>
          <p className="text-xs text-gray-500 mt-0.5">채널별 에이전트 매핑 · 멘션 필수 여부 · 자동응답 설정</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSaveAndReload}
            disabled={!dirty || saving || reloading}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white transition-colors"
          >
            {saving ? '저장 중...' : reloading ? '리로드 중...' : '저장 + 리로드'}
          </button>
          <button
            onClick={handleReload}
            disabled={reloading}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 text-gray-200 transition-colors"
          >
            {reloading ? '리로드 중...' : '리로드만'}
          </button>
        </div>
      </div>

      {/* 메시지 */}
      {message && (
        <div className={`px-4 py-2 rounded-lg text-sm ${message.type === 'ok' ? 'bg-green-900/40 text-green-300 border border-green-800' : 'bg-red-900/40 text-red-300 border border-red-800'}`}>
          {message.text}
        </div>
      )}

      {/* 채널 매핑 요약 (읽기 전용) */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h2 className="text-sm font-bold text-gray-300 mb-3">채널 → 에이전트 매핑 ({allChannels.length}개)</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {allChannels.map(({ agent, channel, isPrefix }) => (
            <div key={`${agent.agent_id}-${channel}`} className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2 text-sm">
              <span>{agent.emoji}</span>
              <span className="text-gray-400">#{isPrefix ? `${channel}*` : channel}</span>
              <span className="text-gray-500">→</span>
              <span className="text-white font-medium truncate">{agent.agent_name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 에이전트별 설정 테이블 */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800/50 text-gray-400">
                <th className="text-left px-4 py-3 font-semibold">에이전트</th>
                <th className="text-left px-4 py-3 font-semibold">채널 (콤마 구분)</th>
                <th className="text-left px-4 py-3 font-semibold">Prefix</th>
                <th className="text-center px-4 py-3 font-semibold">멘션 필수</th>
                <th className="text-center px-4 py-3 font-semibold">자동응답</th>
                <th className="text-center px-4 py-3 font-semibold">Ack 메시지</th>
                <th className="text-left px-4 py-3 font-semibold">Context Hint</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {routing.map((entry, idx) => (
                <tr key={entry.agent_id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="mr-1.5">{entry.emoji}</span>
                    <span className="text-white font-medium">{entry.agent_name}</span>
                    <span className="text-gray-500 ml-1 text-xs">({entry.agent_id})</span>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="text"
                      value={entry.slack_channels.join(', ')}
                      onChange={e => updateChannels(idx, e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-200 text-sm focus:border-blue-500 focus:outline-none"
                      placeholder="채널명..."
                    />
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="text"
                      value={entry.slack_prefix.join(', ')}
                      onChange={e => updatePrefix(idx, e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-200 text-sm focus:border-blue-500 focus:outline-none"
                      placeholder="prefix..."
                    />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => updateEntry(idx, 'mention_required', !entry.mention_required)}
                      className={`w-8 h-8 rounded-lg text-xs font-bold transition-colors ${entry.mention_required ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-500'}`}
                    >
                      {entry.mention_required ? 'ON' : 'OFF'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => updateEntry(idx, 'auto_response', !entry.auto_response)}
                      className={`w-8 h-8 rounded-lg text-xs font-bold transition-colors ${entry.auto_response ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-500'}`}
                    >
                      {entry.auto_response ? 'ON' : 'OFF'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => updateEntry(idx, 'ack_message', !entry.ack_message)}
                      className={`w-8 h-8 rounded-lg text-xs font-bold transition-colors ${entry.ack_message ? 'bg-yellow-600 text-white' : 'bg-gray-700 text-gray-500'}`}
                    >
                      {entry.ack_message ? 'ON' : 'OFF'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="text"
                      value={entry.context_hint}
                      onChange={e => updateEntry(idx, 'context_hint', e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-200 text-sm focus:border-blue-500 focus:outline-none"
                      placeholder="힌트 메시지..."
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 설명 */}
      <div className="bg-gray-900/50 rounded-lg border border-gray-800 p-4 text-xs text-gray-500 space-y-1">
        <p><strong className="text-gray-400">멘션 필수</strong>: ON이면 @WTA-AI 멘션이 있는 메시지만 에이전트에 전달. OFF면 모든 메시지 전달.</p>
        <p><strong className="text-gray-400">자동응답</strong>: 채널의 기본 자동응답 활성화 여부.</p>
        <p><strong className="text-gray-400">Ack 메시지</strong>: ON이면 에이전트 응답 전에 "처리 중" 메시지를 먼저 발송.</p>
        <p><strong className="text-gray-400">Context Hint</strong>: 멘션 없는 메시지에 추가되는 맥락 안내 문구.</p>
        <p><strong className="text-gray-400">저장 + 리로드</strong>: agents.json 저장 후 slack-bot에 리로드 신호를 보내 즉시 반영 (재시작 불필요).</p>
      </div>
    </div>
  )
}
