// Knowledge Base 현황판 — WTA AI/데이터 자산 시각화 (실시간 polling)
import { useState, useEffect, useCallback } from 'react'
import knowledgeConfig from '@knowledge'

interface KbItem {
  label: string
  value: number | null
  total: number | null
  unit: string
  status: 'done' | 'in_progress' | 'live' | 'pending'
  type?: 'dual_progress'
  parsed?: number | null
  embedded?: number | null
}

interface KbMeta {
  key: string
  value: string
}

interface KbCategory {
  id: string
  title: string
  icon: string
  color: string
  description: string
  items: KbItem[]
  meta: KbMeta[]
}

// ── 상태 배지 ─────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  done:        { label: '완료',    className: 'bg-green-900/40 text-green-400 border-green-700/50' },
  in_progress: { label: '진행중', className: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50' },
  live:        { label: 'LIVE',   className: 'bg-blue-900/40 text-blue-400 border-blue-700/50' },
  pending:     { label: '대기중', className: 'bg-gray-800 text-gray-500 border-gray-700' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

// ── 진행률 바 ─────────────────────────────────────────────────
function ProgressBar({ value, total, color }: { value: number | null; total: number | null; color: string }) {
  if (!total) return null
  const pct = value !== null ? Math.round((value / total) * 100) : 0
  return (
    <div className="mt-1.5">
      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

// ── dual_progress 행 (파싱 + 임베딩 2단 바) ──────────────────
function DualProgressRow({ item, color }: { item: KbItem; color: string }) {
  const parsed   = item.parsed   ?? 0
  const embedded = item.embedded ?? 0
  const total    = item.total    ?? 1
  const parsedPct   = Math.round((parsed   / total) * 100)
  const embeddedPct = Math.round((embedded / total) * 100)

  return (
    <div className="py-2.5 border-b border-gray-800 last:border-0">
      <div className="flex items-center justify-between gap-3 mb-1.5">
        <span className="text-sm text-gray-300">{item.label}</span>
        <StatusBadge status={item.status} />
      </div>
      {/* 수치 2줄 */}
      <div className="flex gap-3 text-xs mb-1.5">
        <span className="text-blue-400 tabular-nums">
          파싱 <span className="font-semibold">{parsed.toLocaleString()}</span>/{total.toLocaleString()} {item.unit}
          <span className="text-gray-600 ml-1">({parsedPct}%)</span>
        </span>
        <span className="text-gray-600">|</span>
        <span className="tabular-nums" style={{ color }}>
          임베딩 <span className="font-semibold">{embedded.toLocaleString()}</span>/{total.toLocaleString()} {item.unit}
          <span className="text-gray-600 ml-1">({embeddedPct}%)</span>
        </span>
      </div>
      {/* 2색 프로그레스 바 */}
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden relative">
        {/* 파싱 (파란색, 아래 레이어) */}
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${parsedPct}%`, backgroundColor: '#3b82f6', opacity: 0.4 }}
        />
        {/* 임베딩 (팀 컬러, 위 레이어) */}
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${embeddedPct}%`, backgroundColor: color }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-0.5">
        <span>파싱</span>
        <span>임베딩</span>
      </div>
    </div>
  )
}

// ── 아이템 행 ─────────────────────────────────────────────────
function KbItemRow({ item, color }: { item: KbItem; color: string }) {
  if (item.type === 'dual_progress') {
    return <DualProgressRow item={item} color={color} />
  }

  const showProgress = item.total !== null && item.status !== 'live'
  const pct = item.value !== null && item.total
    ? Math.round((item.value / item.total) * 100)
    : null

  return (
    <div className="py-2.5 border-b border-gray-800 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-gray-300">{item.label}</span>
        <div className="flex items-center gap-2 shrink-0">
          {item.value !== null && (
            <span className="text-sm font-semibold tabular-nums" style={{ color }}>
              {item.value.toLocaleString()}
              {item.unit && <span className="text-xs text-gray-500 ml-0.5">{item.unit}</span>}
              {item.total !== null && item.total !== item.value && (
                <span className="text-xs text-gray-600 ml-1">/ {item.total.toLocaleString()}</span>
              )}
            </span>
          )}
          {pct !== null && (
            <span className="text-xs text-gray-500 tabular-nums w-9 text-right">{pct}%</span>
          )}
          <StatusBadge status={item.status} />
        </div>
      </div>
      {showProgress && <ProgressBar value={item.value} total={item.total} color={color} />}
    </div>
  )
}

// ── 카테고리 카드 ─────────────────────────────────────────────
function KbCard({ category }: { category: KbCategory }) {
  const doneCount = category.items.filter((i) => i.status === 'done').length
  const totalCount = category.items.length
  const allDone = doneCount === totalCount && category.items.every((i) => i.status !== 'in_progress')

  return (
    <div
      className="bg-gray-900 rounded-xl border overflow-hidden flex flex-col"
      style={{ borderColor: category.color + '40' }}
    >
      {/* 헤더 */}
      <div
        className="px-4 py-3 border-b flex items-center justify-between"
        style={{ borderColor: category.color + '30', backgroundColor: category.color + '0d' }}
      >
        <div className="flex items-center gap-2">
          <span className="text-xl">{category.icon}</span>
          <div>
            <div className="text-sm font-semibold text-white">{category.title}</div>
            <div className="text-xs text-gray-500 mt-0.5">{category.description}</div>
          </div>
        </div>
        {allDone ? (
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-900/30 text-green-400 border border-green-700/40">
            ✓ 완료
          </span>
        ) : (
          <span className="text-xs text-gray-600">
            {doneCount}/{totalCount}
          </span>
        )}
      </div>

      {/* 아이템 목록 */}
      <div className="px-4 flex-1">
        {category.items.map((item) => (
          <KbItemRow key={item.label} item={item} color={category.color} />
        ))}
      </div>

      {/* 메타 정보 */}
      {category.meta.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-800 bg-gray-950/50">
          <div className="grid grid-cols-1 gap-1">
            {category.meta.map((m) => (
              <div key={m.key} className="flex items-baseline gap-2 text-xs">
                <span className="text-gray-600 shrink-0 w-24">{m.key}</span>
                <span className="text-gray-400 font-mono break-all">{m.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 요약 KPI ─────────────────────────────────────────────────
function SummaryKpi({ label, value, sub, color }: {
  label: string; value: string | number; sub?: string; color: string
}) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 px-4 py-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold tabular-nums" style={{ color }}>{value}</div>
      {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
    </div>
  )
}

// ── 페이지 ────────────────────────────────────────────────────
export default function KnowledgePage() {
  // 초기값: 정적 config, 이후 API polling으로 실시간 갱신
  const [kbData, setKbData] = useState(knowledgeConfig as { categories: KbCategory[]; updated_at: string })
  const [lastRefresh, setLastRefresh] = useState<string | null>(null)

  const fetchKnowledge = useCallback(async () => {
    try {
      const res = await fetch('/api/knowledge')
      if (!res.ok) return
      const data = await res.json()
      if (data.categories) {
        setKbData(data as { categories: KbCategory[]; updated_at: string })
        setLastRefresh(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
      }
    } catch {
      // API 미응답 시 정적 데이터 유지
    }
  }, [])

  useEffect(() => {
    // 즉시 한 번 + 20초 간격 polling
    void fetchKnowledge()
    const id = setInterval(fetchKnowledge, 20000)
    return () => clearInterval(id)
  }, [fetchKnowledge])

  const categories = kbData.categories

  // 전체 통계 계산 — 동적 합산
  const allItems = categories.flatMap((c) => c.items)
  const totalEmbedded = allItems.reduce((sum, item) => {
    if (item.type === 'dual_progress') return sum + (item.embedded ?? 0)
    if (item.status === 'done' && item.value !== null) return sum + item.value
    return sum
  }, 0)
  const inProgressCount = allItems.filter((i) => i.status === 'in_progress').length
  const doneCount = allItems.filter((i) => i.status === 'done').length

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-lg font-bold text-white" style={{ color: '#ffffff' }}>Knowledge Base 현황</h1>
        <p className="text-gray-400 text-sm mt-1">
          WTA AI 지식 자산 현황판 — 데이터: {kbData.updated_at}
          {lastRefresh && (
            <span className="ml-2 text-green-500/60 text-xs">갱신 {lastRefresh}</span>
          )}
        </p>
      </div>

      {/* 요약 KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryKpi
          label="총 임베딩 건수"
          value={totalEmbedded.toLocaleString()}
          sub="자동 합산"
          color="#f97316"
        />
        <SummaryKpi
          label="임베딩 모델"
          value="Qwen3-8B"
          sub="2,000 차원"
          color="#a855f7"
        />
        <SummaryKpi
          label="진행중 작업"
          value={inProgressCount}
          sub="항목"
          color="#eab308"
        />
        <SummaryKpi
          label="완료 항목"
          value={doneCount}
          sub="항목"
          color="#22c55e"
        />
      </div>

      {/* 카테고리 카드 그리드 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {categories.map((cat) => (
          <KbCard key={cat.id} category={cat} />
        ))}
      </div>

      {/* 하단 메모 */}
      <div className="text-xs text-gray-500 border-t border-gray-800 pt-4">
        * 20초 간격 자동 갱신 (knowledge.json 기반). knowledge.json 업데이트 시 실시간 반영.
      </div>
    </div>
  )
}
