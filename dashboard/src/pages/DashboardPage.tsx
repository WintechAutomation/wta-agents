// 운영 대시보드 — 에이전트 상태 + 메시지 입력 + 메시지 히스토리 + 팀 헌장
import { useState, useRef, useMemo, useCallback } from 'react'
import { useAgentStore } from '@/store/agentStore'
import agentsConfig from '@agents'

// 바 차트 색상
const BAR_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(agentsConfig)
    .filter(([, a]) => (a as { barColor: string | null }).barColor !== null)
    .map(([id, a]) => [id, (a as { barColor: string }).barColor])
)

function AgentBadge({ id }: { id: string }) {
  const color = BAR_COLORS[id] ?? '#6b7280'
  return (
    <span
      style={{ backgroundColor: color + '33', color, borderColor: color + '4d' }}
      className="inline-flex items-center px-1.5 py-0.5 rounded border text-xs font-medium"
    >
      {id}
    </span>
  )
}

// 간단한 Markdown → HTML 변환
function mdToHtml(md: string): string {
  return md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3 style="color:#e5e7eb;font-size:1rem;font-weight:700;margin:1.2em 0 0.4em">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="color:#f3f4f6;font-size:1.15rem;font-weight:700;margin:1.4em 0 0.5em">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="color:#ffffff;font-size:1.4rem;font-weight:800;margin:0 0 0.6em">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#f3f4f6">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:#1f2937;padding:1px 5px;border-radius:3px;font-size:0.85em">$1</code>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:1.2em;list-style:disc;color:#d1d5db">$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li style="margin-left:1.2em;list-style:decimal;color:#d1d5db">$1</li>')
    .replace(/^---$/gm, '<hr style="border-color:#374151;margin:1em 0" />')
    .replace(/\n{2,}/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
}

export default function DashboardPage() {
  const messages = useAgentStore((s) => s.messages)
  const recent = useMemo(() => [...messages].reverse().slice(0, 50), [messages])

  // 메시지 전송 상태
  const [msgText, setMsgText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [sending, setSending] = useState(false)
  const [sendResult, setSendResult] = useState<{ ok: boolean; text: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // 팀 헌장 모달
  const [charterOpen, setCharterOpen] = useState(false)
  const [charterHtml, setCharterHtml] = useState('')
  const [charterLoading, setCharterLoading] = useState(false)

  // 메시지 상세 모달
  const [selectedMsg, setSelectedMsg] = useState<typeof messages[number] | null>(null)

  const openCharter = useCallback(async () => {
    setCharterOpen(true)
    if (charterHtml) return
    setCharterLoading(true)
    try {
      const res = await fetch('/api/charter')
      if (!res.ok) throw new Error('fetch failed')
      const json = await res.json() as { content: string }
      setCharterHtml(mdToHtml(json.content))
    } catch {
      setCharterHtml('<p style="color:#ef4444">팀 헌장을 불러올 수 없습니다.</p>')
    } finally {
      setCharterLoading(false)
    }
  }, [charterHtml])

  // MAX에게 메시지 전송
  const handleSend = async () => {
    const text = msgText.trim()
    if (!text && files.length === 0) return

    setSending(true)
    setSendResult(null)
    try {
      const formData = new FormData()
      formData.append('to', 'MAX')
      formData.append('message', text)
      for (const file of files) {
        formData.append('files', file)
      }

      const res = await fetch('/api/send-message', {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        setSendResult({ ok: true, text: '전송 완료' })
        setMsgText('')
        setFiles([])
        if (fileRef.current) fileRef.current.value = ''
      } else {
        const err = await res.text()
        setSendResult({ ok: false, text: `전송 실패: ${err}` })
      }
    } catch (e) {
      setSendResult({ ok: false, text: `전송 오류: ${e instanceof Error ? e.message : String(e)}` })
    } finally {
      setSending(false)
      setTimeout(() => setSendResult(null), 3000)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files))
    }
  }

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div className="p-4 md:p-6 space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white" style={{ color: '#ffffff' }}>운영 대시보드</h1>
          <p className="text-gray-400 text-xs">에이전트 상태 · 메시지 전송 · 실시간 로그</p>
        </div>
        <button
          onClick={() => void openCharter()}
          className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm text-gray-300 hover:text-white transition-colors"
        >
          <span>📜</span> 팀 헌장
        </button>
      </div>

      {/* MAX에게 메시지 전송 */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
        <div className="text-sm font-semibold text-gray-300 mb-3">MAX에게 메시지 전송</div>
        <div className="space-y-3">
          <textarea
            value={msgText}
            onChange={(e) => setMsgText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault()
                void handleSend()
              }
            }}
            placeholder="메시지를 입력하세요... (Ctrl+Enter로 전송)"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500 transition-colors"
            rows={3}
          />
          <div className="flex items-center gap-3 flex-wrap">
            {/* 첨부파일 */}
            <label className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200 cursor-pointer transition-colors px-2.5 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
              첨부파일
              <input
                ref={fileRef}
                type="file"
                multiple
                onChange={handleFileChange}
                className="hidden"
              />
            </label>

            {/* 첨부된 파일 목록 */}
            {files.map((f, i) => (
              <span key={i} className="flex items-center gap-1 text-xs bg-gray-800 text-gray-300 px-2 py-1 rounded-lg border border-gray-700">
                {f.name}
                <button onClick={() => removeFile(i)} className="text-gray-500 hover:text-red-400 ml-1">&times;</button>
              </span>
            ))}

            <div className="flex-1" />

            {/* 전송 결과 */}
            {sendResult && (
              <span className={`text-xs ${sendResult.ok ? 'text-green-400' : 'text-red-400'}`}>
                {sendResult.text}
              </span>
            )}

            {/* 전송 버튼 */}
            <button
              onClick={() => void handleSend()}
              disabled={sending || (!msgText.trim() && files.length === 0)}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm rounded-lg transition-colors"
            >
              {sending ? '전송 중...' : '전송'}
            </button>
          </div>
        </div>
      </div>

      {/* 메시지 로그 */}
      <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden flex-1 flex flex-col min-h-0">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between shrink-0">
          <span className="text-sm font-semibold text-gray-300">최근 메시지</span>
          <span className="text-xs text-gray-500">{messages.length}건</span>
        </div>
        <div className="divide-y divide-gray-800 flex-1 overflow-y-auto">
          {recent.length === 0 ? (
            <div className="px-5 py-8 text-center text-gray-500 text-sm">메시지 없음</div>
          ) : (
            recent.map((msg) => (
              <div
                key={msg.id}
                className="px-5 py-3 hover:bg-gray-800/50 transition-colors cursor-pointer"
                onClick={() => setSelectedMsg(msg)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <AgentBadge id={msg.from} />
                  <span className="text-gray-500 text-xs">&rarr;</span>
                  <AgentBadge id={msg.to} />
                  <span className="ml-auto text-xs text-gray-600">{msg.time}</span>
                </div>
                <div className="text-sm text-gray-300 line-clamp-2 pl-0.5">{msg.content}</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 메시지 상세 모달 */}
      {selectedMsg && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setSelectedMsg(null)}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] mx-4 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <AgentBadge id={selectedMsg.from} />
                <span className="text-gray-500 text-xs">&rarr;</span>
                <AgentBadge id={selectedMsg.to} />
                <span className="ml-3 text-xs text-gray-500">{selectedMsg.time}</span>
              </div>
              <button
                onClick={() => setSelectedMsg(null)}
                className="text-gray-400 hover:text-white text-xl px-2 transition-colors"
              >
                &times;
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words font-sans leading-relaxed">
                {selectedMsg.content}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* 팀 헌장 모달 */}
      {charterOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setCharterOpen(false)}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] mx-4 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h2 className="text-lg font-bold" style={{ color: '#ffffff' }}>📜 WTA AI 팀 헌장</h2>
              <button
                onClick={() => setCharterOpen(false)}
                className="text-gray-400 hover:text-white text-xl px-2 transition-colors"
              >
                &times;
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {charterLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
                </div>
              ) : (
                <div
                  className="text-sm leading-relaxed text-gray-300"
                  dangerouslySetInnerHTML={{ __html: charterHtml }}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
