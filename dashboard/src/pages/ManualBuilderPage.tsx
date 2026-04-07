// 매뉴얼 빌더 — 매뉴얼 PDF 업로드, 파싱, 임베딩, 검색 테스트
import { useState, useEffect, useCallback, useRef } from 'react'

// ── 타입 ──────────────────────────────────────────────────────
interface ManualFile {
  id: number
  filename: string
  category: string
  status: 'uploaded' | 'parsing' | 'parsed' | 'embedding' | 'embedded' | 'error'
  pages: number | null
  chunks: number | null
  created_at: string
  error_message?: string
}

interface SearchResult {
  content: string
  source: string
  score: number
  page?: number
}

interface EmbedStats {
  total_files: number
  embedded: number
  parsed: number
  pending: number
  error: number
}

// ── 상태 배지 ─────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  uploaded:  { label: '대기',    className: 'bg-gray-800 text-gray-400 border-gray-700' },
  parsing:   { label: '파싱중',  className: 'bg-blue-900/40 text-blue-400 border-blue-700/50' },
  parsed:    { label: '파싱완료', className: 'bg-cyan-900/40 text-cyan-400 border-cyan-700/50' },
  embedding: { label: '임베딩중', className: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50' },
  embedded:  { label: '완료',    className: 'bg-green-900/40 text-green-400 border-green-700/50' },
  error:     { label: '오류',    className: 'bg-red-900/40 text-red-400 border-red-700/50' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.uploaded
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

// ── 통계 카드 ─────────────────────────────────────────────────
function StatCard({ label, value, icon, color }: { label: string; value: number; icon: string; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{icon}</span>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</div>
    </div>
  )
}

// ── 진행률 바 ─────────────────────────────────────────────────
function ProgressBar({ value, total, label, color }: { value: number; total: number; label: string; color: string }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-500">{value}/{total} ({pct}%)</span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────
export default function ManualBuilderPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'upload' | 'files' | 'search'>('overview')
  const [files, setFiles] = useState<ManualFile[]>([])
  const [stats, setStats] = useState<EmbedStats>({ total_files: 0, embedded: 0, parsed: 0, pending: 0, error: 0 })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // API 호출
  const fetchData = useCallback(async () => {
    try {
      const [filesRes, statsRes] = await Promise.all([
        fetch('/api/manual-builder/files'),
        fetch('/api/manual-builder/stats'),
      ])
      if (filesRes.ok) setFiles(await filesRes.json())
      if (statsRes.ok) setStats(await statsRes.json())
    } catch {
      // API 미구현 시 빈 데이터 유지
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  // 파일 업로드
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadFiles = e.target.files
    if (!uploadFiles?.length) return

    setUploading(true)
    const formData = new FormData()
    for (const file of uploadFiles) {
      formData.append('files', file)
    }

    try {
      const res = await fetch('/api/manual-builder/upload', { method: 'POST', body: formData })
      if (res.ok) {
        await fetchData()
      }
    } catch {
      // 오류 처리
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // 검색
  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await fetch(`/api/manual-builder/search?q=${encodeURIComponent(searchQuery)}`)
      if (res.ok) setSearchResults(await res.json())
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  // 파싱/임베딩 트리거
  const triggerAction = async (fileId: number, action: 'parse' | 'embed') => {
    try {
      await fetch(`/api/manual-builder/${action}/${fileId}`, { method: 'POST' })
      await fetchData()
    } catch {
      // 오류 처리
    }
  }

  const filteredFiles = filterStatus === 'all' ? files : files.filter(f => f.status === filterStatus)

  const tabs = [
    { id: 'overview' as const, label: '현황', icon: '📊' },
    { id: 'upload' as const,   label: '업로드', icon: '📤' },
    { id: 'files' as const,    label: '파일 관리', icon: '📁' },
    { id: 'search' as const,   label: '검색 테스트', icon: '🔍' },
  ]

  return (
    <div className="p-6">
      {/* 헤더 */}
      <div className="mb-6">
        <h1 className="text-lg font-bold text-white flex items-center gap-2" style={{ color: '#ffffff' }}>
          <span>📖</span> 매뉴얼 빌더
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          매뉴얼 PDF 업로드, 파싱, 벡터 임베딩, 검색 테스트
        </p>
      </div>

      {/* 탭 네비게이션 */}
      <div className="flex gap-1 mb-6 bg-gray-900 rounded-lg p-1 w-fit">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
            }`}
          >
            <span className="mr-1.5">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══ 현황 탭 ═══ */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* 통계 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard label="전체 파일" value={stats.total_files} icon="📄" color="text-white" />
            <StatCard label="임베딩 완료" value={stats.embedded} icon="✅" color="text-green-400" />
            <StatCard label="파싱 완료" value={stats.parsed} icon="📋" color="text-cyan-400" />
            <StatCard label="대기중" value={stats.pending} icon="⏳" color="text-gray-400" />
            <StatCard label="오류" value={stats.error} icon="❌" color="text-red-400" />
          </div>

          {/* 진행률 */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">파이프라인 진행률</h3>
            <ProgressBar
              value={stats.parsed + stats.embedded}
              total={stats.total_files}
              label="파싱 진행률"
              color="#22d3ee"
            />
            <ProgressBar
              value={stats.embedded}
              total={stats.total_files}
              label="임베딩 진행률"
              color="#4ade80"
            />
          </div>

          {/* 파이프라인 설명 */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">처리 파이프라인</h3>
            <div className="flex items-center gap-2 text-sm flex-wrap">
              <div className="flex items-center gap-1.5 bg-gray-800 px-3 py-1.5 rounded-lg">
                <span>📤</span><span className="text-gray-300">업로드</span>
              </div>
              <span className="text-gray-600">→</span>
              <div className="flex items-center gap-1.5 bg-blue-900/30 px-3 py-1.5 rounded-lg border border-blue-800/50">
                <span>📋</span><span className="text-blue-400">파싱</span>
              </div>
              <span className="text-gray-600">→</span>
              <div className="flex items-center gap-1.5 bg-yellow-900/30 px-3 py-1.5 rounded-lg border border-yellow-800/50">
                <span>🧮</span><span className="text-yellow-400">임베딩</span>
              </div>
              <span className="text-gray-600">→</span>
              <div className="flex items-center gap-1.5 bg-green-900/30 px-3 py-1.5 rounded-lg border border-green-800/50">
                <span>✅</span><span className="text-green-400">벡터DB 저장</span>
              </div>
            </div>
          </div>

          {loading && (
            <div className="text-center text-gray-500 py-8">
              데이터를 불러오는 중...
            </div>
          )}
        </div>
      )}

      {/* ═══ 업로드 탭 ═══ */}
      {activeTab === 'upload' && (
        <div className="space-y-6">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-8">
            <div className="border-2 border-dashed border-gray-700 rounded-xl p-12 text-center hover:border-blue-600 transition-colors">
              <div className="text-5xl mb-4">📄</div>
              <h3 className="text-lg font-semibold text-gray-300 mb-2">매뉴얼 PDF 업로드</h3>
              <p className="text-sm text-gray-500 mb-6">
                PDF 파일을 선택하여 업로드하세요. 여러 파일 동시 업로드 가능합니다.
              </p>
              <label className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg cursor-pointer transition-colors">
                <span>📤</span>
                <span>{uploading ? '업로드 중...' : '파일 선택'}</span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  multiple
                  className="hidden"
                  onChange={handleUpload}
                  disabled={uploading}
                />
              </label>
              <p className="text-xs text-gray-600 mt-4">지원 형식: PDF (최대 50MB)</p>
            </div>
          </div>

          {/* 업로드 가이드 */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">업로드 가이드</h3>
            <ul className="text-sm text-gray-500 space-y-2">
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-0.5">1.</span>
                <span>PDF 파일 선택 후 업로드 — 자동으로 파일 목록에 등록됩니다</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-0.5">2.</span>
                <span>파일 관리 탭에서 개별 또는 일괄 파싱을 실행합니다</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-0.5">3.</span>
                <span>파싱 완료 후 임베딩을 실행하면 벡터DB에 저장됩니다</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-0.5">4.</span>
                <span>검색 테스트 탭에서 벡터 검색 품질을 확인할 수 있습니다</span>
              </li>
            </ul>
          </div>
        </div>
      )}

      {/* ═══ 파일 관리 탭 ═══ */}
      {activeTab === 'files' && (
        <div className="space-y-4">
          {/* 필터 */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">상태 필터:</span>
            {['all', 'uploaded', 'parsed', 'embedded', 'error'].map(s => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  filterStatus === s
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200'
                }`}
              >
                {s === 'all' ? '전체' : STATUS_CONFIG[s]?.label ?? s}
              </button>
            ))}
            <span className="text-xs text-gray-600 ml-2">{filteredFiles.length}개</span>
          </div>

          {/* 파일 테이블 */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-xs text-gray-500">
                  <th className="text-left px-4 py-3 font-medium">파일명</th>
                  <th className="text-left px-4 py-3 font-medium">카테고리</th>
                  <th className="text-center px-4 py-3 font-medium">상태</th>
                  <th className="text-right px-4 py-3 font-medium">페이지</th>
                  <th className="text-right px-4 py-3 font-medium">청크</th>
                  <th className="text-center px-4 py-3 font-medium">액션</th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-12 text-gray-600">
                      {loading ? '불러오는 중...' : files.length === 0 ? '업로드된 파일이 없습니다' : '해당 상태의 파일이 없습니다'}
                    </td>
                  </tr>
                ) : (
                  filteredFiles.map(file => (
                    <tr key={file.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="px-4 py-3">
                        <div className="text-gray-300 truncate max-w-[300px]" title={file.filename}>
                          {file.filename}
                        </div>
                        {file.error_message && (
                          <div className="text-xs text-red-400 mt-0.5 truncate max-w-[300px]">{file.error_message}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500">{file.category || '-'}</td>
                      <td className="px-4 py-3 text-center"><StatusBadge status={file.status} /></td>
                      <td className="px-4 py-3 text-right text-gray-500">{file.pages ?? '-'}</td>
                      <td className="px-4 py-3 text-right text-gray-500">{file.chunks?.toLocaleString() ?? '-'}</td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {(file.status === 'uploaded' || file.status === 'error') && (
                            <button
                              onClick={() => triggerAction(file.id, 'parse')}
                              className="text-xs px-2 py-1 bg-blue-600/20 text-blue-400 rounded hover:bg-blue-600/40 transition-colors"
                              title="파싱 실행"
                            >
                              파싱
                            </button>
                          )}
                          {file.status === 'parsed' && (
                            <button
                              onClick={() => triggerAction(file.id, 'embed')}
                              className="text-xs px-2 py-1 bg-green-600/20 text-green-400 rounded hover:bg-green-600/40 transition-colors"
                              title="임베딩 실행"
                            >
                              임베딩
                            </button>
                          )}
                          {(file.status === 'parsing' || file.status === 'embedding') && (
                            <span className="text-xs text-yellow-500 animate-pulse">처리중...</span>
                          )}
                          {file.status === 'embedded' && (
                            <span className="text-xs text-green-500">완료</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ 검색 테스트 탭 ═══ */}
      {activeTab === 'search' && (
        <div className="space-y-6">
          {/* 검색 입력 */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">벡터 검색 테스트</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="매뉴얼 검색어를 입력하세요 (예: PVD 로딩 절차, 프레스 에러코드)"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
              />
              <button
                onClick={handleSearch}
                disabled={searching || !searchQuery.trim()}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm rounded-lg transition-colors"
              >
                {searching ? '검색중...' : '검색'}
              </button>
            </div>
          </div>

          {/* 검색 결과 */}
          {searchResults.length > 0 && (
            <div className="space-y-3">
              <div className="text-sm text-gray-500">{searchResults.length}개 결과</div>
              {searchResults.map((result, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded border border-blue-800/50">
                        #{i + 1}
                      </span>
                      <span className="text-xs text-gray-500 truncate max-w-[400px]">{result.source}</span>
                      {result.page && (
                        <span className="text-xs text-gray-600">p.{result.page}</span>
                      )}
                    </div>
                    <span className="text-xs text-gray-600">
                      유사도: <span className="text-cyan-400 font-mono">{(result.score * 100).toFixed(1)}%</span>
                    </span>
                  </div>
                  <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{result.content}</p>
                </div>
              ))}
            </div>
          )}

          {searchResults.length === 0 && searchQuery && !searching && (
            <div className="text-center py-12 text-gray-600">
              검색 버튼을 누르면 벡터DB에서 유사 문서를 검색합니다
            </div>
          )}

          {!searchQuery && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
              <div className="text-4xl mb-3">🔍</div>
              <p className="text-sm text-gray-500">검색어를 입력하고 벡터 검색 품질을 확인하세요</p>
              <div className="flex flex-wrap justify-center gap-2 mt-4">
                {['PVD 로딩 절차', '프레스 에러코드', '검사기 캘리브레이션', '연삭 핸들러 유지보수'].map(q => (
                  <button
                    key={q}
                    onClick={() => { setSearchQuery(q); }}
                    className="text-xs px-3 py-1.5 bg-gray-800 text-gray-400 rounded-full hover:text-blue-400 hover:bg-gray-700 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
