// CS 질의응답 세션 뷰어
import { useState, useEffect, useCallback } from 'react'

interface SessionSummary {
  session_id: string
  first_timestamp: string
  last_timestamp: string
  user: string
  channel: string
  question_source: string
  question_summary: string
  message_count: number
  equipment_type: string
  last_status: string
}

interface Attachment {
  type: string
  url: string
}

interface SessionMessage {
  timestamp: string
  question: string
  answer: string
  status: string
  image_paths: string[]
  attachments: Attachment[]
  rag_sources: { table: string; score: number; content?: string }[]
  tools_used: string[]
  model: string
  response_time_ms: number | null
  full_conversation: string
}

interface SessionDetail {
  session_id: string
  user: string
  channel: string
  question_source: string
  equipment_type: string
  language: string
  message_count: number
  first_timestamp: string
  last_timestamp: string
  messages: SessionMessage[]
}

interface SessionListResponse {
  items: SessionSummary[]
  total: number
  page: number
  limit: number
}

const SOURCE_COLORS: Record<string, string> = {
  slack: 'bg-purple-900/40 text-purple-400 border-purple-700/50',
  telegram: 'bg-blue-900/40 text-blue-400 border-blue-700/50',
  web: 'bg-green-900/40 text-green-400 border-green-700/50',
}

function SourceBadge({ source }: { source: string }) {
  const cls = SOURCE_COLORS[source.toLowerCase()] ?? 'bg-gray-800 text-gray-400 border-gray-700'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${cls}`}>
      {source || '?'}
    </span>
  )
}

function formatMs(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(ts: string): string {
  if (!ts) return '-'
  try {
    // "2026-03-31 14:03:11 KST" → "2026-03-31T14:03:11+09:00"
    const cleaned = ts.replace(/\s+KST$/i, '').replace(' ', 'T') + '+09:00'
    const d = new Date(cleaned)
    if (isNaN(d.getTime())) return ts.slice(0, 16)
    return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts.slice(0, 16)
  }
}

// 간이 마크다운 렌더러 (볼드, 헤딩, 리스트, 코드블록)
function renderMarkdown(md: string) {
  const lines = md.split('\n')
  const elements: React.ReactNode[] = []
  let inCodeBlock = false
  let codeLines: string[] = []
  let key = 0

  for (const line of lines) {
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={key++} className="bg-gray-900 border border-gray-800 rounded p-2 text-xs font-mono overflow-x-auto my-1">
            {codeLines.join('\n')}
          </pre>
        )
        codeLines = []
      }
      inCodeBlock = !inCodeBlock
      continue
    }
    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }
    // 헤딩
    if (line.startsWith('### ')) {
      elements.push(<h4 key={key++} className="text-sm font-semibold text-gray-200 mt-3 mb-1">{line.slice(4)}</h4>)
    } else if (line.startsWith('## ')) {
      elements.push(<h3 key={key++} className="text-sm font-bold text-gray-100 mt-3 mb-1">{line.slice(3)}</h3>)
    } else if (line.startsWith('# ')) {
      elements.push(<h2 key={key++} className="text-base font-bold text-white mt-3 mb-1">{line.slice(2)}</h2>)
    } else if (line.startsWith('- ')) {
      // 볼드 처리
      const content = line.slice(2).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      elements.push(
        <li key={key++} className="text-sm text-gray-300 ml-4 list-disc" dangerouslySetInnerHTML={{ __html: content }} />
      )
    } else if (line.trim() === '') {
      elements.push(<div key={key++} className="h-1.5" />)
    } else {
      const content = line.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      elements.push(
        <p key={key++} className="text-sm text-gray-300" dangerouslySetInnerHTML={{ __html: content }} />
      )
    }
  }

  if (inCodeBlock && codeLines.length > 0) {
    elements.push(
      <pre key={key++} className="bg-gray-900 border border-gray-800 rounded p-2 text-xs font-mono overflow-x-auto my-1">
        {codeLines.join('\n')}
      </pre>
    )
  }

  return elements
}

// 상태 배지
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    responded: 'bg-green-900/40 text-green-400 border-green-700/50',
    awaiting_error_code: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
    awaiting_model_info: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
    awaiting_param_info: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
  }
  const cls = colors[status] ?? 'bg-gray-800 text-gray-400 border-gray-700'
  const label = status.startsWith('awaiting') ? '대기중' : status === 'responded' ? '완료' : status
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${cls}`}>{label}</span>
  )
}

// 대화 메시지 버블
function MessageBubble({ msg, index }: { msg: SessionMessage; index: number }) {
  const [showMd, setShowMd] = useState(false)
  const hasMd = !!msg.full_conversation

  return (
    <div className="space-y-2">
      {/* 타임스탬프 구분 */}
      <div className="flex items-center gap-2 pt-2">
        <div className="h-px flex-1 bg-gray-800" />
        <span className="text-[10px] text-gray-600 shrink-0">#{index + 1} {formatTime(msg.timestamp)}</span>
        <div className="h-px flex-1 bg-gray-800" />
      </div>

      {/* 질문 (유저) */}
      <div className="flex justify-end">
        <div className="max-w-[85%]">
          <div className="text-[10px] text-gray-600 text-right mb-0.5">사용자</div>
          <div className="bg-blue-950/40 border border-blue-900/30 rounded-lg rounded-tr-sm p-3 text-sm text-gray-200 whitespace-pre-wrap max-h-[400px] overflow-y-auto">
            {msg.question}
          </div>
        </div>
      </div>

      {/* 첨부 이미지 */}
      {msg.image_paths && msg.image_paths.length > 0 && (
        <div className="flex justify-end">
          <div className="flex gap-1.5 flex-wrap max-w-[85%]">
            {msg.image_paths.map((path, i) => (
              <div key={i} className="w-16 h-16 bg-gray-800 rounded border border-gray-700 overflow-hidden">
                <img src={path} alt={`img-${i}`} className="w-full h-full object-cover" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 응답 (AI) */}
      <div className="flex justify-start">
        <div className="max-w-[85%]">
          <div className="text-[10px] text-gray-600 mb-0.5 flex items-center gap-2">
            <span>cs-agent</span>
            {msg.model && <span className="text-gray-700">{msg.model}</span>}
            {msg.response_time_ms != null && <span className="text-gray-700">{formatMs(msg.response_time_ms)}</span>}
            {msg.status && <StatusBadge status={msg.status} />}
          </div>
          <div className="bg-green-950/20 border border-green-900/30 rounded-lg rounded-tl-sm p-3 text-sm text-gray-200 whitespace-pre-wrap max-h-[600px] overflow-y-auto">
            {msg.answer}
          </div>
          {/* 첨부파일 */}
          {msg.attachments && msg.attachments.length > 0 && (
            <div className="flex flex-col gap-1 mt-1.5">
              {msg.attachments.map((att, i) => (
                <a key={i} href={att.url} target="_blank" rel="noopener noreferrer"
                   className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 truncate">
                  <span>{att.type === 'pdf' ? '📎' : att.type === 'image' ? '🖼️' : '🔗'}</span>
                  <span className="underline">{att.url.split('/').pop() || att.url}</span>
                </a>
              ))}
            </div>
          )}
          {/* RAG/도구 요약 */}
          {((msg.rag_sources && msg.rag_sources.length > 0) || (msg.tools_used && msg.tools_used.length > 0)) && (
            <div className="flex gap-2 mt-1 flex-wrap">
              {msg.rag_sources && msg.rag_sources.length > 0 && (
                <span className="text-[10px] text-purple-500">RAG:{msg.rag_sources.length}</span>
              )}
              {msg.tools_used && msg.tools_used.map((t, i) => (
                <span key={i} className="text-[10px] text-orange-600">{t}</span>
              ))}
            </div>
          )}
          {/* MD 원문 토글 */}
          {hasMd && (
            <button
              onClick={() => setShowMd(!showMd)}
              className="text-[10px] text-gray-600 hover:text-gray-400 mt-1 underline"
            >
              {showMd ? '원문 접기' : '원문 보기'}
            </button>
          )}
          {showMd && hasMd && (
            <div className="mt-2 border border-gray-800 rounded-lg p-3 bg-gray-900/50 space-y-1">
              {renderMarkdown(msg.full_conversation)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// 상세 패널
function DetailPanel({ session, onClose }: { session: SessionDetail; onClose: () => void }) {
  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800 flex-shrink-0">
        <div>
          <div className="text-sm font-medium text-white flex items-center gap-2">
            <SourceBadge source={session.question_source} />
            <span className="text-gray-500 text-xs font-mono">{session.session_id}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700">
              {session.message_count}건
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1 flex items-center gap-3 flex-wrap">
            {session.user && <span>사용자: {session.user}</span>}
            {session.channel && <span>채널: {session.channel}</span>}
            {session.equipment_type && <span>장비: {session.equipment_type}</span>}
            {session.language && <span>언어: {session.language}</span>}
          </div>
          <div className="text-xs text-gray-600 mt-0.5">
            {formatTime(session.first_timestamp)}
            {session.message_count > 1 && <> ~ {formatTime(session.last_timestamp)}</>}
          </div>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg px-2">&times;</button>
      </div>

      {/* 대화 흐름 */}
      <div className="flex-1 overflow-auto p-4 space-y-1">
        {session.messages.map((msg, idx) => (
          <MessageBubble key={msg.timestamp + idx} msg={msg} index={idx} />
        ))}
      </div>
    </div>
  )
}

// ── 파이프라인 순서도 (4단계, 2026-04-09 업데이트) ──
function PipelineModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-[95vw] max-w-2xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-lg font-bold text-white">CS 질의응답 파이프라인</h2>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-gray-600">cs_pipeline.py</span>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-xl leading-none">&times;</button>
          </div>
        </div>

        {/* 순서도 */}
        <div className="flex-1 overflow-auto px-6 py-5">
          <div className="flex flex-col items-center gap-0">
            {/* 진입 */}
            <div className="w-full max-w-md flex gap-2 justify-center mb-1">
              <FlowBox color="purple" icon="💬" title="슬랙 CS 채널" sub="질문 수신" small />
              <FlowBox color="green" icon="🌐" title="웹챗" sub="cs-wta.com" small />
              <FlowBox color="blue" icon="📱" title="텔레그램" sub="직접 질문" small />
            </div>
            <FlowArrow />

            <FlowBox color="blue" icon="🤖" title="cs_pipeline.py" sub="단일 진입점 — 세션 그룹핑 (message_history 기반)" />
            <FlowArrow />

            {/* Stage 1: 세션 이력 검색 */}
            <div className="w-full max-w-lg relative">
              <div className="absolute -left-1 top-3 text-[10px] font-bold text-cyan-500 bg-cyan-950/60 border border-cyan-800/40 rounded px-1.5 py-0.5">1</div>
              <FlowDiamond title="세션 이력 검색" sub="cs-sessions.jsonl에서 동일 질의 우선 조회" />
            </div>
            <div className="flex items-start w-full max-w-md">
              <div className="flex-1 flex flex-col items-center">
                <div className="text-xs text-green-400 font-semibold mb-1">매칭</div>
                <FlowArrow short />
                <FlowBox color="green" icon="⚡" title="즉답 반환" sub="캐시 히트 — 빠른 경로" small />
                <FlowArrow short />
                <div className="text-xs text-gray-600 mb-1">&#8595; 답변 전송</div>
              </div>
              <div className="flex-1 flex flex-col items-center">
                <div className="text-xs text-yellow-400 font-semibold mb-1">미매칭</div>
                <FlowArrow short />
                <div className="text-xs text-gray-500 mb-1">&#8595; Self RAG</div>
              </div>
            </div>

            {/* Stage 2: Self RAG */}
            <div className="w-full max-w-lg relative">
              <div className="absolute -left-1 top-3 text-[10px] font-bold text-blue-500 bg-blue-950/60 border border-blue-800/40 rounded px-1.5 py-0.5">2</div>
              <div className="w-full border border-blue-800/40 rounded-xl bg-blue-950/20 p-3 my-1">
                <div className="text-xs text-blue-400 font-semibold text-center mb-1">Self RAG — pgvector 코사인 유사도 (임계값 0.60)</div>
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <DbBox name="부품매뉴얼" table="manual.documents" count="265,635건" color="green" />
                  <DbBox name="WTA매뉴얼" table="manual.wta_documents" count="120,084건" color="purple" />
                  <DbBox name="CS 이력" table="csagent.vector_embeddings" count="3,318건" color="orange" />
                </div>
                <div className="text-[10px] text-gray-600 text-center">Qwen3-Embedding-8B (2000차원) | 3개 테이블 병렬 검색</div>
              </div>
            </div>

            {/* 분기: 결과 충분/부족 */}
            <div className="flex items-start w-full max-w-md">
              <div className="flex-1 flex flex-col items-center">
                <div className="text-xs text-green-400 font-semibold mb-1">결과 충분</div>
                <FlowArrow short />
                <div className="text-xs text-gray-500 mb-1">&#8595; 답변 생성</div>
              </div>
              <div className="flex-1 flex flex-col items-center">
                <div className="text-xs text-orange-400 font-semibold mb-1">결과 부족</div>
                <FlowArrow short />
                <div className="text-xs text-gray-500 mb-1">&#8595; db-manager 폴백</div>
              </div>
            </div>

            {/* Stage 3: db-manager 폴백 */}
            <div className="w-full max-w-lg relative">
              <div className="absolute -left-1 top-3 text-[10px] font-bold text-orange-500 bg-orange-950/60 border border-orange-800/40 rounded px-1.5 py-0.5">3</div>
              <div className="w-full border border-orange-800/40 rounded-xl bg-orange-950/20 p-3 my-1">
                <div className="flex items-center justify-center gap-2 mb-1">
                  <span>📊</span>
                  <span className="text-sm font-semibold text-white">db-manager 폴백</span>
                </div>
                <div className="text-xs text-gray-400 text-center">파일 기반 추가 검색</div>
                <div className="text-[10px] text-orange-400/70 text-center mt-1">"추가 검색 중..." 안내 → 사용자 대기</div>
              </div>
            </div>
            <FlowArrow />

            {/* 답변 생성 */}
            <div className="w-full max-w-md border border-purple-800/40 rounded-xl bg-purple-950/20 p-3 my-1">
              <div className="flex items-center justify-center gap-2 mb-1">
                <span>✨</span>
                <span className="text-sm font-semibold text-white">답변 생성</span>
              </div>
              <div className="text-xs text-gray-400 text-center">Claude 모델 (sonnet/opus) — 이미지 첨부 시 멀티모달 분석</div>
              <div className="text-xs text-gray-600 text-center mt-1">통합 랭킹: 유사도 기준 상위 K개 선별 후 프롬프트 구성</div>
            </div>
            <FlowArrow />

            {/* Stage 4: PDF 첨부 + 최적 답변 */}
            <div className="w-full max-w-lg relative">
              <div className="absolute -left-1 top-3 text-[10px] font-bold text-green-500 bg-green-950/60 border border-green-800/40 rounded px-1.5 py-0.5">4</div>
              <div className="w-full border border-green-800/40 rounded-xl bg-green-950/20 p-3 my-1">
                <div className="flex items-center justify-center gap-2 mb-1">
                  <span>📎</span>
                  <span className="text-sm font-semibold text-white">최적 답변 + PDF 첨부</span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="bg-gray-900/60 border border-gray-800 rounded-lg px-2 py-2 text-center">
                    <div className="text-xs font-semibold text-green-400">PDF 추출</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">해당 페이지 ±1 추출</div>
                    <div className="text-[10px] text-gray-600 mt-0.5">캐시 재활용</div>
                  </div>
                  <div className="bg-gray-900/60 border border-gray-800 rounded-lg px-2 py-2 text-center">
                    <div className="text-xs font-semibold text-blue-400">Cloudflare 전달</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">agent.mes-wta.com URL</div>
                    <div className="text-[10px] text-gray-600 mt-0.5">"준비 중" → 링크 전송</div>
                  </div>
                </div>
              </div>
            </div>
            <FlowArrow />

            {/* 응답 전송 */}
            <FlowBox color="purple" icon="📤" title="채널 답변 전송" sub="슬랙 / 웹챗 / 텔레그램 — 텍스트 + PDF 링크" />
            <FlowArrow />

            {/* 로깅 */}
            <FlowBox color="gray" icon="📝" title="세션 JSONL 로깅" sub="질문 + 전문답변 + RAG소스 + 도구 + 응답시간 + session_id" />
          </div>
        </div>
      </div>
    </div>
  )
}

function FlowBox({ color, icon, title, sub, small }: { color: string; icon: string; title: string; sub: string; small?: boolean }) {
  const colorMap: Record<string, string> = {
    purple: 'border-purple-700/50 bg-purple-950/30',
    blue: 'border-blue-700/50 bg-blue-950/30',
    cyan: 'border-cyan-700/50 bg-cyan-950/30',
    green: 'border-green-700/50 bg-green-950/30',
    indigo: 'border-indigo-700/50 bg-indigo-950/30',
    orange: 'border-orange-700/50 bg-orange-950/30',
    gray: 'border-gray-700/50 bg-gray-800/30',
  }
  const cls = colorMap[color] ?? colorMap.gray
  return (
    <div className={`border rounded-xl ${cls} ${small ? 'px-3 py-2 w-full max-w-[180px]' : 'px-4 py-3 w-full max-w-md'} text-center`}>
      <div className={`flex items-center justify-center gap-1.5 ${small ? 'text-xs' : 'text-sm'}`}>
        <span>{icon}</span>
        <span className="font-semibold text-white">{title}</span>
      </div>
      <div className={`text-gray-400 mt-0.5 ${small ? 'text-[10px]' : 'text-xs'}`}>{sub}</div>
    </div>
  )
}

function FlowDiamond({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="w-full max-w-md border border-yellow-700/50 bg-yellow-950/20 rounded-xl px-4 py-3 text-center my-1" style={{ clipPath: 'none' }}>
      <div className="text-xs text-yellow-400 font-semibold mb-0.5">&#9670; 분기점</div>
      <div className="text-sm font-semibold text-white">{title}</div>
      <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
    </div>
  )
}

function FlowArrow({ short }: { short?: boolean }) {
  return (
    <div className={`flex flex-col items-center ${short ? 'my-0.5' : 'my-1'}`}>
      <div className={`w-px bg-gray-700 ${short ? 'h-3' : 'h-5'}`} />
      <div className="w-0 h-0 border-l-[5px] border-r-[5px] border-t-[6px] border-l-transparent border-r-transparent border-t-gray-700" />
    </div>
  )
}

function DbBox({ name, table, count, color }: { name: string; table: string; count: string; color: string }) {
  const colorMap: Record<string, string> = {
    orange: 'text-orange-400',
    green: 'text-green-400',
    purple: 'text-purple-400',
  }
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-lg px-2 py-2 text-center">
      <div className={`text-xs font-semibold ${colorMap[color] ?? 'text-gray-300'}`}>{name}</div>
      <div className="text-[10px] text-gray-600 font-mono mt-0.5 truncate">{table}</div>
      <div className="text-[10px] text-gray-500 mt-0.5">{count}</div>
    </div>
  )
}

export default function CsSessionsPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showPipeline, setShowPipeline] = useState(false)
  const limit = 20

  const fetchList = useCallback((pg: number, q: string, src: string) => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(pg), limit: String(limit) })
    if (q) params.set('search', q)
    if (src) params.set('source', src)
    fetch(`/api/cs-sessions?${params}`)
      .then((r) => r.json())
      .then((d: SessionListResponse) => {
        setSessions(d.items)
        setTotal(d.total)
      })
      .catch(() => { setSessions([]); setTotal(0) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchList(page, search, sourceFilter)
  }, [page, search, sourceFilter, fetchList])

  const handleSearch = () => {
    setPage(1)
    setSearch(searchInput)
  }

  const handleSelect = (id: string) => {
    setSelectedId(id)
    setDetailLoading(true)
    fetch(`/api/cs-sessions/${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then((d: SessionDetail) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false))
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="p-4 border-b border-gray-800 flex-shrink-0 flex items-start justify-between">
        <div>
          <h1 className="text-sm font-bold text-white" style={{ color: '#ffffff' }}>CS 질의응답 세션</h1>
          <p className="text-gray-500 text-xs mt-0.5">
            cs-agent의 CS RAG 질의응답 기록 ({total}건)
          </p>
        </div>
        <button
          onClick={() => setShowPipeline(true)}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors flex items-center gap-1.5 shrink-0"
        >
          <span>🔄</span> 파이프라인
        </button>
      </div>

      {showPipeline && <PipelineModal onClose={() => setShowPipeline(false)} />}

      {/* 필터 바 */}
      <div className="px-4 py-3 border-b border-gray-800 flex gap-2 flex-shrink-0 flex-wrap">
        <input
          type="text"
          placeholder="질문/답변 검색..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 min-w-[200px] bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
        />
        <select
          value={sourceFilter}
          onChange={(e) => { setSourceFilter(e.target.value); setPage(1) }}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none"
        >
          <option value="">전체 소스</option>
          <option value="slack">Slack</option>
          <option value="telegram">Telegram</option>
          <option value="web">Web</option>
        </select>
        <button
          onClick={handleSearch}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
        >
          검색
        </button>
      </div>

      {/* 본체: 리스트 + 상세 */}
      <div className="flex flex-1 min-h-0">
        {/* 좌측 리스트 */}
        <div className="w-full md:w-96 lg:w-[420px] flex-shrink-0 border-r border-gray-800 flex flex-col">
          <div className="flex-1 overflow-auto">
            {loading ? (
              <div className="text-sm text-gray-500 p-4">불러오는 중...</div>
            ) : sessions.length === 0 ? (
              <div className="text-sm text-gray-600 p-4 text-center">
                <div className="text-3xl mb-2">💬</div>
                <p>CS 세션 기록이 없습니다</p>
              </div>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => handleSelect(s.session_id)}
                  className={`w-full text-left px-4 py-3 border-b border-gray-800/50 transition-colors ${
                    selectedId === s.session_id
                      ? 'bg-blue-600/10 border-l-2 border-l-blue-500'
                      : 'hover:bg-gray-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <SourceBadge source={s.question_source} />
                      <span className="text-xs text-gray-500">{formatTime(s.first_timestamp)}</span>
                      {s.message_count > 1 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-600/20 text-blue-400 font-medium">
                          {s.message_count}
                        </span>
                      )}
                    </div>
                    {s.last_status && <StatusBadge status={s.last_status} />}
                  </div>
                  <div className="text-sm text-gray-300 truncate">{s.question_summary || '(질문 없음)'}</div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-600">
                    {s.user && <span>{s.user}</span>}
                    {s.channel && <span>{s.channel}</span>}
                    {s.equipment_type && <span>{s.equipment_type}</span>}
                  </div>
                </button>
              ))
            )}
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-gray-800 text-xs flex-shrink-0">
              <span className="text-gray-500">{total}건</span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-2 py-1 rounded bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
                >
                  &laquo;
                </button>
                <span className="px-2 py-1 text-gray-400">{page}/{totalPages}</span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-2 py-1 rounded bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
                >
                  &raquo;
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 우측 상세 */}
        <div className="hidden md:flex flex-1 flex-col min-h-0 bg-gray-950">
          {detailLoading ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">불러오는 중...</div>
          ) : detail && selectedId ? (
            <DetailPanel session={detail} onClose={() => { setSelectedId(null); setDetail(null) }} />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-600">
              <div className="text-center">
                <div className="text-4xl mb-2">💬</div>
                <p className="text-sm">세션을 선택하면 상세 내용이 표시됩니다</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
