import { useState, useCallback } from 'react'

interface VectorResult {
  source_file: string
  category: string
  chunk_type: string
  page_number: number | null
  content: string
  similarity: number
  source_table?: string
  error?: string
}

interface GraphResult {
  id: string
  labels: string[]
  name: string
  properties: Record<string, string>
}

interface VectorAnswerResponse {
  query: string
  results: VectorResult[]
  count: number
  answer: string | null
  timing: { vector_ms: number; llm_ms?: number; total_ms: number }
}

interface HybridResponse {
  query: string
  vector_results: VectorResult[]
  vector_count: number
  graph_results: GraphResult[]
  graph_count: number
  answer: string | null
  timing: { vector_ms: number; graph_ms: number; llm_ms?: number; total_ms: number }
}

const LABEL_COLORS: Record<string, string> = {
  Equipment: '#3b82f6', Component: '#10b981', Customer: '#f59e0b',
  Issue: '#ef4444', Person: '#8b5cf6', Process: '#06b6d4',
  Product: '#ec4899', Resolution: '#84cc16', Tool: '#d97706',
}

export default function HybridSearchPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [vectorRes, setVectorRes] = useState<VectorAnswerResponse | null>(null)
  const [hybridRes, setHybridRes] = useState<HybridResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setVectorRes(null)
    setHybridRes(null)

    try {
      // 두 검색을 병렬 실행 (각각 LLM 답변 포함)
      const [vecData, hybData] = await Promise.all([
        // 벡터 검색 + LLM 답변
        fetch('/api/search/vector-answer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, limit: 10, table: 'documents' }),
        }).then(r => r.json()),
        // 하이브리드 검색 + LLM 답변
        fetch('/api/search/hybrid', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            vector_limit: 10,
            graph_limit: 20,
            tables: ['documents', 'wta_documents'],
            generate_answer: true,
          }),
        }).then(r => r.json()),
      ])

      setVectorRes(vecData as VectorAnswerResponse)
      setHybridRes(hybData as HybridResponse)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [query])

  return (
    <div className="p-4 md:p-6 h-full flex flex-col gap-4 overflow-hidden">
      {/* 헤더 + 검색 */}
      <div className="flex-shrink-0">
        <h1 className="text-xl font-bold text-white mb-1">하이브리드 검색 비교</h1>
        <p className="text-sm text-gray-400 mb-3">
          같은 질문, 같은 LLM — 검색 소스만 다르게 해서 답변 차이를 비교
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()}
            placeholder="검색할 질문을 입력하세요..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
          />
          <button
            onClick={search}
            disabled={loading}
            className="px-6 py-2.5 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-700 whitespace-nowrap"
          >
            {loading ? '검색 중...' : '검색'}
          </button>
        </div>
      </div>

      {error && (
        <div className="px-4 py-2 rounded-lg text-sm bg-red-900/40 text-red-300 border border-red-800 flex-shrink-0">
          {error}
        </div>
      )}

      {/* 비교 패널 */}
      <div className="flex-1 grid grid-cols-2 gap-4 min-h-0 overflow-hidden">
        {/* 좌측: 벡터 검색 */}
        <div className="flex flex-col bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between flex-shrink-0">
            <div>
              <h2 className="text-sm font-bold text-white">Vector 검색</h2>
              <p className="text-xs text-gray-500">pgvector 유사도 → Haiku 답변</p>
            </div>
            <div className="text-right">
              {vectorRes && (
                <>
                  <div className="text-xs text-gray-400">{vectorRes.count}건</div>
                  <div className="text-xs text-yellow-500">{vectorRes.timing.total_ms}ms</div>
                </>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {!vectorRes && !loading && (
              <div className="text-center text-gray-500 text-sm py-8">검색어를 입력하세요</div>
            )}

            {/* LLM 답변 */}
            {vectorRes && (
              <div className="bg-yellow-900/30 border-2 border-yellow-600/60 rounded-lg p-4 mb-2">
                <div className="text-sm font-bold text-yellow-400 mb-2 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse" />
                  AI 답변 (Vector → Haiku)
                  {vectorRes.timing.llm_ms != null && (
                    <span className="text-xs font-normal text-yellow-600">{vectorRes.timing.llm_ms}ms</span>
                  )}
                </div>
                <div className="text-sm text-gray-100 whitespace-pre-wrap leading-relaxed">
                  {vectorRes.answer || '(답변 생성되지 않음)'}
                </div>
              </div>
            )}

            {/* 검색 결과 */}
            {vectorRes?.results.filter(r => !r.error).map((r, i) => (
              <div key={i} className="bg-gray-800/60 rounded-lg p-3 border border-gray-700/50">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-blue-400 truncate max-w-[70%]">
                    {r.source_file}
                  </span>
                  <span className="text-xs font-mono text-yellow-400">
                    {(r.similarity * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="text-xs text-gray-400 mb-1.5">
                  {r.category && <span className="mr-2">{r.category}</span>}
                  {r.chunk_type && <span className="mr-2">{r.chunk_type}</span>}
                  {r.page_number != null && <span>p.{r.page_number}</span>}
                </div>
                <div className="text-xs text-gray-300 leading-relaxed line-clamp-4">
                  {r.content}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 우측: 하이브리드 검색 */}
        <div className="flex flex-col bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between flex-shrink-0">
            <div>
              <h2 className="text-sm font-bold text-white">Hybrid 검색</h2>
              <p className="text-xs text-gray-500">Graph + Vector → Haiku 답변</p>
            </div>
            <div className="text-right">
              {hybridRes && (
                <>
                  <div className="text-xs text-gray-400">
                    V:{hybridRes.vector_count} G:{hybridRes.graph_count}
                  </div>
                  <div className="text-xs text-green-500">{hybridRes.timing.total_ms}ms</div>
                </>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {!hybridRes && !loading && (
              <div className="text-center text-gray-500 text-sm py-8">검색어를 입력하세요</div>
            )}

            {/* LLM 답변 */}
            {hybridRes && (
              <div className="bg-blue-900/30 border-2 border-blue-600/60 rounded-lg p-4 mb-2">
                <div className="text-sm font-bold text-blue-400 mb-2 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse" />
                  AI 답변 (Hybrid → Haiku)
                  {hybridRes.timing.llm_ms != null && (
                    <span className="text-xs font-normal text-blue-500">{hybridRes.timing.llm_ms}ms</span>
                  )}
                </div>
                <div className="text-sm text-gray-100 whitespace-pre-wrap leading-relaxed">
                  {hybridRes.answer || '(답변 생성되지 않음)'}
                </div>
              </div>
            )}

            {/* 그래프 결과 */}
            {hybridRes && hybridRes.graph_results.length > 0 && (
              <div className="mb-2">
                <div className="text-xs font-semibold text-purple-400 mb-1.5 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-purple-400" />
                  그래프 노드 ({hybridRes.graph_count})
                  <span className="text-gray-500 font-normal">{hybridRes.timing.graph_ms}ms</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {hybridRes.graph_results.slice(0, 15).map(g => (
                    <div
                      key={g.id}
                      className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-xs"
                      title={Object.entries(g.properties).map(([k, v]) => `${k}: ${v}`).join('\n')}
                    >
                      {g.labels.map(l => (
                        <span
                          key={l}
                          className="inline-block w-2 h-2 rounded-full mr-1"
                          style={{ backgroundColor: LABEL_COLORS[l] || '#64748b' }}
                        />
                      ))}
                      <span className="text-gray-300">{g.name || g.id}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 벡터 결과 */}
            {hybridRes && hybridRes.vector_results.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-blue-400 mb-1.5 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-blue-400" />
                  벡터 매치 ({hybridRes.vector_count})
                  <span className="text-gray-500 font-normal">{hybridRes.timing.vector_ms}ms</span>
                </div>
                {hybridRes.vector_results.map((r, i) => (
                  <div key={i} className="bg-gray-800/60 rounded-lg p-3 border border-gray-700/50 mb-2">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-blue-400 truncate max-w-[70%]">
                        {r.source_file}
                        {r.source_table && (
                          <span className="ml-1 text-gray-500">({r.source_table})</span>
                        )}
                      </span>
                      <span className="text-xs font-mono text-yellow-400">
                        {(r.similarity * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mb-1.5">
                      {r.category && <span className="mr-2">{r.category}</span>}
                      {r.chunk_type && <span className="mr-2">{r.chunk_type}</span>}
                      {r.page_number != null && <span>p.{r.page_number}</span>}
                    </div>
                    <div className="text-xs text-gray-300 leading-relaxed line-clamp-4">
                      {r.content}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
