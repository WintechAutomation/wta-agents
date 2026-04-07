import { useState, useEffect, useCallback } from 'react'

interface Skill {
  id: string
  title: string
  filename: string
  source: string
  category: string
  triggers: string
  overview: string
  path: string
}

const CATEGORY_COLORS: Record<string, string> = {
  '문서작성': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  '매뉴얼': 'bg-green-500/20 text-green-300 border-green-500/30',
  '분석': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  '개발': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  '영업': 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  '기타': 'bg-gray-500/20 text-gray-300 border-gray-500/30',
}

const CATEGORY_ICONS: Record<string, string> = {
  '문서작성': '📝',
  '매뉴얼': '📖',
  '분석': '📊',
  '개발': '💻',
  '영업': '💰',
  '기타': '🔧',
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCat, setSelectedCat] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const fetchSkills = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (selectedCat) params.set('category', selectedCat)
      if (search) params.set('q', search)
      const res = await fetch(`/api/skills?${params}`)
      const data = await res.json()
      setSkills(data.skills || [])
      setCategories(data.categories || [])
    } catch (e) {
      console.error('스킬 로드 실패', e)
    } finally {
      setLoading(false)
    }
  }, [selectedCat, search])

  useEffect(() => {
    fetchSkills()
  }, [fetchSkills])

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            🧠 AI 스킬 라이브러리
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            전사 AI 에이전트가 사용하는 스킬 목록
          </p>
        </div>
        <div className="text-sm text-gray-500">
          총 {skills.length}개 스킬
        </div>
      </div>

      {/* 검색 + 필터 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="스킬 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedCat('')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              !selectedCat
                ? 'bg-blue-600 text-white border-blue-500'
                : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600'
            }`}
          >
            전체
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCat(selectedCat === cat ? '' : cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                selectedCat === cat
                  ? 'bg-blue-600 text-white border-blue-500'
                  : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600'
              }`}
            >
              {CATEGORY_ICONS[cat] || '🔧'} {cat}
            </button>
          ))}
        </div>
      </div>

      {/* 스킬 목록 */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">로딩 중...</div>
      ) : skills.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          등록된 스킬이 없습니다
        </div>
      ) : (
        <div className="grid gap-3">
          {skills.map((skill) => {
            const isExpanded = expandedId === skill.id
            const colorClass = CATEGORY_COLORS[skill.category] || CATEGORY_COLORS['기타']
            return (
              <div
                key={skill.id}
                className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden hover:border-gray-700 transition-colors"
              >
                <button
                  onClick={() => setExpandedId(isExpanded ? null : skill.id)}
                  className="w-full px-4 py-3 flex items-center gap-3 text-left"
                >
                  <span className="text-2xl">
                    {CATEGORY_ICONS[skill.category] || '🔧'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-white text-sm">
                        {skill.title}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${colorClass}`}>
                        {skill.category}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-700/50 text-gray-400 border border-gray-600/50">
                        {skill.source}
                      </span>
                    </div>
                    {skill.triggers && (
                      <div className="text-xs text-gray-500 mt-1 truncate">
                        키워드: {skill.triggers}
                      </div>
                    )}
                  </div>
                  <span className="text-gray-500 text-sm flex-shrink-0">
                    {isExpanded ? '▲' : '▼'}
                  </span>
                </button>
                {isExpanded && (
                  <div className="px-4 pb-4 border-t border-gray-800">
                    <div className="mt-3 space-y-3">
                      {skill.overview && (
                        <div>
                          <div className="text-xs font-medium text-gray-400 mb-1">개요</div>
                          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                            {skill.overview}
                          </p>
                        </div>
                      )}
                      {skill.triggers && (
                        <div>
                          <div className="text-xs font-medium text-gray-400 mb-1">트리거 키워드</div>
                          <div className="flex flex-wrap gap-1.5">
                            {skill.triggers.split(/[,，、]/).map((t, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300"
                              >
                                {t.trim()}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      <div>
                        <div className="text-xs font-medium text-gray-400 mb-1">사용법</div>
                        <p className="text-sm text-gray-300">
                          슬랙이나 텔레그램에서 트리거 키워드를 포함하여 요청하면 자동으로 해당 스킬이 활성화됩니다.
                        </p>
                      </div>
                      <div className="text-xs text-gray-600 mt-2">
                        파일: {skill.filename}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
