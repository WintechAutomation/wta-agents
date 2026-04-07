// 기술용어집 — 테이블 형태 조회 + 편집 페이지
import { useState, useEffect, useCallback } from 'react'

interface GlossaryCategory {
  id: string
  name: string
  color: string
}

interface GlossaryTerm {
  id: string
  term_ko: string
  term_en: string
  term_zh: string
  category: string
  definition: string
  related: string[]
  source: string
}

const API = '/api/glossary'

export default function GlossaryPage() {
  const [categories, setCategories] = useState<GlossaryCategory[]>([])
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [selectedCat, setSelectedCat] = useState<string>('')
  const [search, setSearch] = useState('')
  const [editTerm, setEditTerm] = useState<GlossaryTerm | null>(null)
  const [isAdding, setIsAdding] = useState(false)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const emptyTerm: GlossaryTerm = {
    id: '', term_ko: '', term_en: '', term_zh: '',
    category: 'equipment', definition: '', related: [], source: '',
  }

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (selectedCat) params.set('category', selectedCat)
      if (search) params.set('q', search)
      const res = await fetch(`${API}?${params}`)
      const data = await res.json()
      setCategories(data.categories || [])
      setTerms(data.terms || [])
    } catch (e) {
      console.error('용어집 로드 실패', e)
    } finally {
      setLoading(false)
    }
  }, [selectedCat, search])

  useEffect(() => { fetchData() }, [fetchData])

  const saveTerm = async (term: GlossaryTerm) => {
    const isNew = !term.id
    const url = isNew ? `${API}/terms` : `${API}/terms/${term.id}`
    const method = isNew ? 'POST' : 'PUT'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(term),
    })
    if (res.ok) {
      setEditTerm(null)
      setIsAdding(false)
      fetchData()
    }
  }

  const deleteTerm = async (id: string) => {
    if (!confirm('이 용어를 삭제하시겠습니까?')) return
    const res = await fetch(`${API}/terms/${id}`, { method: 'DELETE' })
    if (res.ok) {
      if (expandedId === id) setExpandedId(null)
      fetchData()
    }
  }

  const getCatColor = (catId: string) => {
    return categories.find(c => c.id === catId)?.color || '#6B7280'
  }
  const getCatName = (catId: string) => {
    return categories.find(c => c.id === catId)?.name || catId
  }

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id)
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white" style={{ color: '#ffffff' }}>기술용어집</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            WTA 장비 기술 용어 — 한/영/중 3개 국어
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{terms.length}개 용어</span>
          <button
            onClick={() => { setIsAdding(true); setEditTerm({ ...emptyTerm }) }}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
          >
            + 용어 추가
          </button>
        </div>
      </div>

      {/* 필터 바 */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setSelectedCat('')}
          className={`px-3 py-1 text-xs rounded-full border transition-colors ${
            !selectedCat
              ? 'bg-gray-700 text-white border-gray-600'
              : 'bg-gray-900 text-gray-400 border-gray-700 hover:border-gray-500'
          }`}
        >
          전체
        </button>
        {categories.map(cat => (
          <button
            key={cat.id}
            onClick={() => setSelectedCat(selectedCat === cat.id ? '' : cat.id)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${
              selectedCat === cat.id
                ? 'text-white border-opacity-80'
                : 'text-gray-400 border-gray-700 hover:border-gray-500'
            }`}
            style={selectedCat === cat.id ? { backgroundColor: cat.color + '33', borderColor: cat.color } : {}}
          >
            {cat.name}
          </button>
        ))}
        <div className="flex-1" />
        <input
          type="text"
          placeholder="검색..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-48 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* 편집 모달 */}
      {editTerm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => { setEditTerm(null); setIsAdding(false) }}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg space-y-4" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-white">{isAdding ? '용어 추가' : '용어 편집'}</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400">한국어</label>
                <input
                  value={editTerm.term_ko}
                  onChange={e => setEditTerm({ ...editTerm, term_ko: e.target.value })}
                  className="w-full mt-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">English</label>
                <input
                  value={editTerm.term_en}
                  onChange={e => setEditTerm({ ...editTerm, term_en: e.target.value })}
                  className="w-full mt-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">中文</label>
                <input
                  value={editTerm.term_zh}
                  onChange={e => setEditTerm({ ...editTerm, term_zh: e.target.value })}
                  className="w-full mt-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">카테고리</label>
                <select
                  value={editTerm.category}
                  onChange={e => setEditTerm({ ...editTerm, category: e.target.value })}
                  className="w-full mt-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-400">정의</label>
              <textarea
                value={editTerm.definition}
                onChange={e => setEditTerm({ ...editTerm, definition: e.target.value })}
                rows={3}
                className="w-full mt-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400">관련 용어 (쉼표 구분)</label>
                <input
                  value={editTerm.related.join(', ')}
                  onChange={e => setEditTerm({ ...editTerm, related: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                  className="w-full mt-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">출처</label>
                <input
                  value={editTerm.source}
                  onChange={e => setEditTerm({ ...editTerm, source: e.target.value })}
                  className="w-full mt-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => { setEditTerm(null); setIsAdding(false) }}
                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm rounded-lg"
              >
                취소
              </button>
              <button
                onClick={() => saveTerm(editTerm)}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg"
              >
                저장
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 테이블 */}
      {loading ? (
        <div className="text-center py-20 text-gray-500">로딩 중...</div>
      ) : terms.length === 0 ? (
        <div className="text-center py-20 text-gray-500">등록된 용어가 없습니다</div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/80">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-400 w-[18%]">용어 (한)</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-400 w-[16%]">English</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-400 w-[14%]">中文</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-400 w-[12%]">카테고리</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-400">정의</th>
                <th className="px-4 py-2.5 text-xs font-medium text-gray-400 w-[80px] text-center">작업</th>
              </tr>
            </thead>
            <tbody>
              {terms.map(term => (
                <TermRow
                  key={term.id}
                  term={term}
                  expanded={expandedId === term.id}
                  onToggle={() => toggleExpand(term.id)}
                  onEdit={() => { setEditTerm({ ...term }); setIsAdding(false) }}
                  onDelete={() => deleteTerm(term.id)}
                  catColor={getCatColor(term.category)}
                  catName={getCatName(term.category)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function TermRow({
  term,
  expanded,
  onToggle,
  onEdit,
  onDelete,
  catColor,
  catName,
}: {
  term: GlossaryTerm
  expanded: boolean
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
  catColor: string
  catName: string
}) {
  const defShort = term.definition.length > 40
    ? term.definition.slice(0, 40) + '...'
    : term.definition

  return (
    <>
      <tr
        className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
          expanded ? 'bg-gray-800/40' : 'hover:bg-gray-800/30'
        }`}
        onClick={onToggle}
      >
        <td className="px-4 py-2 text-white font-medium">{term.term_ko}</td>
        <td className="px-4 py-2 text-gray-300">{term.term_en}</td>
        <td className="px-4 py-2 text-gray-400">{term.term_zh}</td>
        <td className="px-4 py-2">
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-medium"
            style={{
              backgroundColor: catColor + '22',
              color: catColor,
              border: `1px solid ${catColor}44`,
            }}
          >
            {catName}
          </span>
        </td>
        <td className="px-4 py-2 text-gray-400 text-xs">{expanded ? term.definition : defShort}</td>
        <td className="px-4 py-2 text-center">
          <div className="flex justify-center gap-1">
            <button
              onClick={e => { e.stopPropagation(); onEdit() }}
              className="text-xs px-2 py-0.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded"
            >
              편집
            </button>
            <button
              onClick={e => { e.stopPropagation(); onDelete() }}
              className="text-xs px-2 py-0.5 bg-gray-800 hover:bg-red-900/50 text-gray-300 hover:text-red-400 rounded"
            >
              삭제
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-800/20">
          <td colSpan={6} className="px-4 py-3">
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-gray-500">정의</span>
                <p className="text-gray-300 mt-1 leading-relaxed">{term.definition}</p>
              </div>
              <div>
                <span className="text-gray-500">관련 용어</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {term.related.length > 0 ? term.related.map((r, i) => (
                    <span key={i} className="px-1.5 py-0.5 bg-gray-700 text-gray-300 rounded">
                      {r}
                    </span>
                  )) : (
                    <span className="text-gray-600">-</span>
                  )}
                </div>
              </div>
              <div>
                <span className="text-gray-500">출처</span>
                <p className="text-gray-400 mt-1">{term.source || '-'}</p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
