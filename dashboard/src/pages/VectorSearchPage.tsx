// 벡터 검색 페이지 — pgvector 유사도 검색
import { useState, useCallback } from 'react'

interface SearchResult {
  id: number
  source_file: string
  category: string
  chunk_index: number
  chunk_type: string
  page_number: number | null
  content: string
  image_url: string | null
  pdf_url: string | null
  similarity: number
}

interface SearchResponse {
  query: string
  table: string
  count: number
  results: SearchResult[]
}

const API = '/api/vector-search'

export default function VectorSearchPage() {
  const [query, setQuery] = useState('')
  const [table, setTable] = useState('wta_documents')
  const [limit, setLimit] = useState(20)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const handleSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) return
    setLoading(true)
    setError('')
    setData(null)
    setExpandedId(null)
    try {
      const resp = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, table, limit }),
      })
      const json = await resp.json()
      if (!resp.ok) {
        setError(json.error || '검색 실패')
        return
      }
      setData(json)
    } catch (e) {
      setError(`네트워크 오류: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [query, table, limit])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') void handleSearch()
  }

  const similarityColor = (s: number) => {
    if (s >= 0.8) return '#16a34a'
    if (s >= 0.6) return '#2563eb'
    if (s >= 0.4) return '#d97706'
    return '#9ca3af'
  }

  const similarityBg = (s: number) => {
    if (s >= 0.8) return '#f0fdf4'
    if (s >= 0.6) return '#eff6ff'
    if (s >= 0.4) return '#fffbeb'
    return '#f9fafb'
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      {/* 헤더 */}
      <div style={{ marginBottom: 4 }}>
        <h1 style={{ fontSize: 14, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          🔍 벡터 검색
        </h1>
        <p style={{ color: '#6b7280', fontSize: 12, marginTop: 2 }}>
          pgvector 코사인 유사도 기반 문서 검색 (Qwen3-Embedding-8B)
        </p>
      </div>

      {/* 검색 입력 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="검색어를 입력하세요..."
          style={{
            flex: 1, minWidth: 240, padding: '10px 14px', fontSize: 14,
            border: '1px solid #d1d5db', borderRadius: 8,
            outline: 'none',
          }}
        />
        <select
          value={table}
          onChange={e => setTable(e.target.value)}
          style={{ padding: '10px 12px', fontSize: 13, border: '1px solid #d1d5db', borderRadius: 8 }}
        >
          <option value="wta_documents">WTA 매뉴얼</option>
          <option value="documents">부품 매뉴얼</option>
        </select>
        <select
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          style={{ padding: '10px 12px', fontSize: 13, border: '1px solid #d1d5db', borderRadius: 8 }}
        >
          <option value={10}>10건</option>
          <option value={20}>20건</option>
          <option value={30}>30건</option>
          <option value={50}>50건</option>
        </select>
        <button
          onClick={() => void handleSearch()}
          disabled={loading || !query.trim()}
          style={{
            padding: '10px 20px', fontSize: 14, fontWeight: 600,
            background: loading ? '#9ca3af' : '#2563eb', color: '#fff',
            border: 'none', borderRadius: 8, cursor: loading ? 'wait' : 'pointer',
          }}
        >
          {loading ? '검색 중...' : '검색'}
        </button>
      </div>

      {/* 에러 */}
      {error && (
        <div style={{ padding: '12px 16px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#dc2626', fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* 결과 요약 */}
      {data && (
        <div style={{ marginBottom: 12, fontSize: 13, color: '#6b7280' }}>
          <strong>"{data.query}"</strong> 검색 결과: {data.count}건
          ({data.table === 'wta_documents' ? 'WTA 매뉴얼' : '부품 매뉴얼'})
        </div>
      )}

      {/* 결과 목록 */}
      {data?.results.map((item, idx) => (
        <div
          key={item.id}
          onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
          style={{
            border: '1px solid #e5e7eb', borderRadius: 8, marginBottom: 8,
            background: expandedId === item.id ? '#f8fafc' : '#fff',
            cursor: 'pointer', transition: 'background 0.15s',
          }}
        >
          {/* 헤더 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px' }}>
            <span style={{ fontSize: 12, color: '#9ca3af', minWidth: 24 }}>
              {String(idx + 1).padStart(2, '0')}
            </span>
            <span
              style={{
                fontSize: 12, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                color: similarityColor(item.similarity),
                background: similarityBg(item.similarity),
                minWidth: 52, textAlign: 'center',
              }}
            >
              {(item.similarity * 100).toFixed(1)}%
            </span>
            {item.category && (
              <span style={{ fontSize: 11, padding: '2px 8px', background: '#e0e7ff', color: '#4338ca', borderRadius: 4, fontWeight: 600 }}>
                {item.category}
              </span>
            )}
            <span style={{ fontSize: 13, fontWeight: 600, color: '#111827', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {item.source_file}
            </span>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>
              #{item.chunk_index} · {item.chunk_type}
              {item.page_number != null && ` · p.${item.page_number}`}
            </span>
          </div>

          {/* 미리보기 (접힌 상태) */}
          {expandedId !== item.id && (
            <div style={{ padding: '0 16px 12px 50px', fontSize: 13, color: '#6b7280', lineHeight: 1.6 }}>
              {item.content.length > 200 ? item.content.slice(0, 200) + '...' : item.content}
            </div>
          )}

          {/* 전체 내용 (펼친 상태) */}
          {expandedId === item.id && (
            <div style={{ padding: '0 16px 16px 16px' }}>
              <div style={{
                background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 6,
                padding: '14px 16px', fontSize: 13, color: '#374151',
                lineHeight: 1.8, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                maxHeight: 400, overflowY: 'auto',
              }}>
                {item.content}
              </div>
              {(item.image_url || item.pdf_url) && (
                <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                  {item.pdf_url && (
                    <a href={item.pdf_url} target="_blank" rel="noreferrer"
                      style={{ fontSize: 12, color: '#2563eb', textDecoration: 'underline' }}>
                      📄 PDF 원본
                    </a>
                  )}
                  {item.image_url && (
                    <a href={item.image_url} target="_blank" rel="noreferrer"
                      style={{ fontSize: 12, color: '#2563eb', textDecoration: 'underline' }}>
                      🖼️ 이미지
                    </a>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {/* 빈 상태 */}
      {!loading && !data && !error && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#9ca3af' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
          <p style={{ fontSize: 14 }}>검색어를 입력하고 검색 버튼을 클릭하세요</p>
          <p style={{ fontSize: 12, marginTop: 4 }}>WTA 매뉴얼, 부품 매뉴얼에서 유사한 문서를 찾아줍니다</p>
        </div>
      )}
    </div>
  )
}
