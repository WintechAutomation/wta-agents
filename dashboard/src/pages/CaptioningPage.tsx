import { useState, useEffect, useCallback } from 'react'

// --- 타입 ---
interface CaptionItem {
  filename?: string
  file?: string
  caption?: string
  description?: string
  category?: string
  type?: string
  status?: string
  timestamp?: string
}

interface CaptioningData {
  total: number
  completed: number
  remaining: number
  progress_pct: number
  captions: CaptionItem[]
  message?: string
}

// --- 유틸 ---
function getFilename(item: CaptionItem): string {
  return item.filename || item.file || '-'
}

function getCaption(item: CaptionItem): string {
  return item.caption || item.description || '-'
}

function getCategory(item: CaptionItem): string {
  return item.category || item.type || '미분류'
}

// 카테고리 색상
const CATEGORY_COLORS: Record<string, string> = {
  '장비외관': 'bg-blue-500/20 text-blue-300',
  'HMI': 'bg-purple-500/20 text-purple-300',
  '부품': 'bg-green-500/20 text-green-300',
  '전장': 'bg-orange-500/20 text-orange-300',
  '기구': 'bg-cyan-500/20 text-cyan-300',
  '미분류': 'bg-gray-500/20 text-gray-400',
}

function getCategoryClass(cat: string): string {
  for (const [key, cls] of Object.entries(CATEGORY_COLORS)) {
    if (cat.includes(key)) return cls
  }
  return CATEGORY_COLORS['미분류']
}

// --- 메인 ---
export default function CaptioningPage() {
  const [data, setData] = useState<CaptioningData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selectedImage, setSelectedImage] = useState<CaptionItem | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/captioning/status')
      const json = await res.json()
      if (json.success) {
        setData(json.data)
        setError(null)
      } else {
        setError(json.error || '데이터 조회 실패')
      }
    } catch (e) {
      setError('서버 연결 실패')
    } finally {
      setLoading(false)
    }
  }, [])

  // 초기 로드
  useEffect(() => {
    void fetchData()
  }, [fetchData])

  // 자동 새로고침 (10초)
  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(() => void fetchData(), 10_000)
    return () => clearInterval(timer)
  }, [autoRefresh, fetchData])

  // 카테고리별 통계
  const categoryStats: Record<string, number> = {}
  if (data) {
    for (const item of data.captions) {
      const cat = getCategory(item)
      categoryStats[cat] = (categoryStats[cat] || 0) + 1
    }
  }
  const sortedCategories = Object.entries(categoryStats).sort((a, b) => b[1] - a[1])
  const maxCatCount = sortedCategories.length > 0 ? sortedCategories[0][1] : 1

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400 animate-pulse text-lg">로딩 중...</div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-bold text-white flex items-center gap-2">
          <span className="text-2xl">📸</span>
          이미지 캡셔닝 모니터링
        </h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            자동 새로고침
          </label>
          <button
            onClick={() => void fetchData()}
            className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
          >
            새로고침
          </button>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* 메시지 (파일 미생성 등) */}
      {data?.message && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 text-yellow-300 text-sm">
          {data.message}
        </div>
      )}

      {data && (
        <>
          {/* 진행률 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400">전체</div>
              <div className="text-3xl font-bold text-white mt-1">{data.total}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400">완료</div>
              <div className="text-3xl font-bold text-green-400 mt-1">{data.completed}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400">남은 건수</div>
              <div className="text-3xl font-bold text-yellow-400 mt-1">{data.remaining}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-sm text-gray-400">진행률</div>
              <div className="text-3xl font-bold text-blue-400 mt-1">{data.progress_pct}%</div>
            </div>
          </div>

          {/* 프로그레스 바 */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-400">캡셔닝 진행 상황</span>
              <span className="text-sm text-gray-300">{data.completed} / {data.total}</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-4 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all duration-500"
                style={{ width: `${data.progress_pct}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 유형별 분포 */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-base font-semibold text-white mb-3">유형별 분포</h2>
              {sortedCategories.length === 0 ? (
                <p className="text-sm text-gray-500">데이터 없음</p>
              ) : (
                <div className="space-y-2">
                  {sortedCategories.map(([cat, count]) => (
                    <div key={cat}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs ${getCategoryClass(cat)}`}>
                          {cat}
                        </span>
                        <span className="text-gray-400">{count}건</span>
                      </div>
                      <div className="w-full bg-gray-800 rounded-full h-2">
                        <div
                          className="h-full bg-blue-500/60 rounded-full"
                          style={{ width: `${(count / maxCatCount) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 최근 완료 목록 */}
            <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h2 className="text-base font-semibold text-white mb-3">
                최근 캡셔닝 완료 목록
                <span className="text-sm text-gray-500 ml-2">({data.captions.length}건)</span>
              </h2>
              {data.captions.length === 0 ? (
                <p className="text-sm text-gray-500">완료된 캡셔닝이 없습니다.</p>
              ) : (
                <div className="overflow-auto max-h-[500px]">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-gray-900">
                      <tr className="border-b border-gray-800 text-gray-400">
                        <th className="text-left py-2 px-2 w-8">#</th>
                        <th className="text-left py-2 px-2">파일명</th>
                        <th className="text-left py-2 px-2">캡션</th>
                        <th className="text-left py-2 px-2 w-20">유형</th>
                        <th className="text-center py-2 px-2 w-16">보기</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...data.captions].reverse().slice(0, 100).map((item, idx) => (
                        <tr
                          key={getFilename(item) + idx}
                          className="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors"
                        >
                          <td className="py-2 px-2 text-gray-500">{data.captions.length - idx}</td>
                          <td className="py-2 px-2 text-gray-300 font-mono text-xs truncate max-w-[200px]" title={getFilename(item)}>
                            {getFilename(item)}
                          </td>
                          <td className="py-2 px-2 text-gray-300 truncate max-w-[300px]" title={getCaption(item)}>
                            {getCaption(item)}
                          </td>
                          <td className="py-2 px-2">
                            <span className={`px-1.5 py-0.5 rounded text-xs ${getCategoryClass(getCategory(item))}`}>
                              {getCategory(item)}
                            </span>
                          </td>
                          <td className="py-2 px-2 text-center">
                            <button
                              onClick={() => setSelectedImage(item)}
                              className="text-blue-400 hover:text-blue-300 text-xs"
                            >
                              미리보기
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* 이미지 미리보기 모달 */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-auto p-4 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-white font-semibold truncate">{getFilename(selectedImage)}</h3>
              <button
                onClick={() => setSelectedImage(null)}
                className="text-gray-400 hover:text-white text-xl px-2"
              >
                ×
              </button>
            </div>
            <img
              src={`/api/captioning/image?path=${encodeURIComponent('한국야금_NC_Press_29-31호기/' + getFilename(selectedImage))}`}
              alt={getFilename(selectedImage)}
              className="w-full rounded-lg bg-gray-800"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none'
              }}
            />
            <div className="space-y-2 text-sm">
              <div>
                <span className="text-gray-400">캡션:</span>
                <p className="text-gray-200 mt-0.5">{getCaption(selectedImage)}</p>
              </div>
              <div className="flex gap-4">
                <div>
                  <span className="text-gray-400">유형: </span>
                  <span className={`px-2 py-0.5 rounded text-xs ${getCategoryClass(getCategory(selectedImage))}`}>
                    {getCategory(selectedImage)}
                  </span>
                </div>
                {selectedImage.timestamp && (
                  <div>
                    <span className="text-gray-400">시간: </span>
                    <span className="text-gray-300">{selectedImage.timestamp}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
