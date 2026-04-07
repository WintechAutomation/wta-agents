import { useState, useEffect, useCallback, useRef } from 'react'
import { InteractiveNvlWrapper } from '@neo4j-nvl/react'
import type { MouseEventCallbacks } from '@neo4j-nvl/react'
import type { Node, Relationship, HitTargets } from '@neo4j-nvl/base'
import NVL from '@neo4j-nvl/base'

// 라벨별 색상 맵
const LABEL_COLORS: Record<string, string> = {
  Equipment: '#3b82f6',
  Component: '#10b981',
  Customer: '#f59e0b',
  Issue: '#ef4444',
  Person: '#8b5cf6',
  Process: '#06b6d4',
  Product: '#ec4899',
  Resolution: '#84cc16',
  Tool: '#d97706',
  Phase2: '#6366f1',
  Phase3: '#0ea5e9',
  base: '#64748b',
}
const DEFAULT_COLOR = '#64748b'

function labelColor(labels: string[]): string {
  for (const l of labels) {
    if (LABEL_COLORS[l]) return LABEL_COLORS[l]
  }
  return DEFAULT_COLOR
}

interface GraphNode {
  id: string
  labels: string[]
  properties: Record<string, unknown>
  caption: string
}

interface GraphRel {
  id: string
  from: string
  to: string
  type: string
  properties: Record<string, unknown>
}

interface LabelInfo {
  label: string
  count: number
}

export default function GraphRAGPage() {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [rels, setRels] = useState<GraphRel[]>([])
  const [labels, setLabels] = useState<LabelInfo[]>([])
  const [activeLabel, setActiveLabel] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [cypherQuery, setCypherQuery] = useState('')
  const [cypherRows, setCypherRows] = useState<Record<string, unknown>[]>([])
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState({ nodes: 0, rels: 0 })
  const nvlRef = useRef<NVL | null>(null)

  // NVL 포맷으로 변환
  const nvlNodes: Node[] = nodes.map(n => ({
    id: n.id,
    size: 25,
    color: labelColor(n.labels),
    captions: [{ value: n.caption }],
  }))

  const nvlRels: Relationship[] = rels
    .filter(r => {
      const nodeIds = new Set(nodes.map(n => n.id))
      return nodeIds.has(r.from) && nodeIds.has(r.to)
    })
    .map(r => ({
      id: r.id,
      from: r.from,
      to: r.to,
      captions: [{ value: r.type }],
    }))

  // 라벨 목록 로드
  const loadLabels = useCallback(async () => {
    try {
      const res = await fetch('/api/graphrag/labels')
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      setLabels(data.labels ?? [])
    } catch {
      setError('Neo4j 연결 실패')
    }
  }, [])

  // 전체 노드 로드
  const loadAll = useCallback(async (label?: string) => {
    setLoading(true)
    setError(null)
    setCypherRows([])
    try {
      const url = label
        ? `/api/graphrag/nodes?limit=200&label=${encodeURIComponent(label)}`
        : '/api/graphrag/nodes?limit=200'
      const res = await fetch(url)
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      setNodes(data.nodes ?? [])
      setRels(data.rels ?? [])
      setStats({ nodes: data.nodes?.length ?? 0, rels: data.rels?.length ?? 0 })
      setSelectedNode(null)
    } catch {
      setError('데이터 로드 실패')
    } finally {
      setLoading(false)
    }
  }, [])

  // 검색
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return
    setLoading(true)
    setError(null)
    setCypherRows([])
    try {
      const res = await fetch(`/api/graphrag/search?q=${encodeURIComponent(searchQuery)}`)
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      setNodes(data.nodes ?? [])
      setRels(data.rels ?? [])
      setStats({ nodes: data.nodes?.length ?? 0, rels: data.rels?.length ?? 0 })
      setActiveLabel('')
      setSelectedNode(null)
    } catch {
      setError('검색 실패')
    } finally {
      setLoading(false)
    }
  }, [searchQuery])

  // 노드 확장
  const expandNode = useCallback(async (nodeId: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/graphrag/expand?node_id=${encodeURIComponent(nodeId)}`)
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      // 기존 노드에 추가 (중복 제거)
      setNodes(prev => {
        const existing = new Set(prev.map(n => n.id))
        const newNodes = (data.nodes ?? []).filter((n: GraphNode) => !existing.has(n.id))
        return [...prev, ...newNodes]
      })
      setRels(prev => {
        const existing = new Set(prev.map(r => r.id))
        const newRels = (data.rels ?? []).filter((r: GraphRel) => !existing.has(r.id))
        return [...prev, ...newRels]
      })
      setStats(prev => ({
        nodes: prev.nodes + (data.nodes ?? []).length,
        rels: prev.rels + (data.rels ?? []).length,
      }))
    } catch {
      setError('확장 실패')
    } finally {
      setLoading(false)
    }
  }, [])

  // Cypher 실행
  const runCypher = useCallback(async () => {
    if (!cypherQuery.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/graphrag/cypher', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cypher: cypherQuery }),
      })
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      if (data.nodes?.length) {
        setNodes(data.nodes)
        setRels(data.rels ?? [])
        setStats({ nodes: data.nodes.length, rels: data.rels?.length ?? 0 })
      }
      setCypherRows(data.rows ?? [])
      setActiveLabel('')
      setSelectedNode(null)
    } catch {
      setError('쿼리 실행 실패')
    } finally {
      setLoading(false)
    }
  }, [cypherQuery])

  // 마우스 인터랙션 콜백 (모두 활성화)
  const mouseCallbacks: MouseEventCallbacks = {
    // 클릭
    onNodeClick: (clickedNode: Node, _hitTargets: HitTargets, _event: MouseEvent) => {
      const found = nodes.find(n => n.id === clickedNode.id)
      setSelectedNode(found ?? null)
    },
    onNodeDoubleClick: (clickedNode: Node, _hitTargets: HitTargets, _event: MouseEvent) => {
      expandNode(clickedNode.id)
    },
    onCanvasClick: () => {
      setSelectedNode(null)
    },
    onCanvasDoubleClick: true,
    onNodeRightClick: true,
    onRelationshipClick: true,
    onRelationshipDoubleClick: true,
    onRelationshipRightClick: true,
    onCanvasRightClick: true,
    // 줌 (마우스 휠 + 트랙패드 핀치)
    onZoom: true,
    onZoomAndPan: true,
    // 팬 (드래그로 뷰 이동)
    onPan: true,
    // 노드 드래그 이동
    onDrag: true,
    onDragStart: true,
    onDragEnd: true,
    // 호버 (마우스 올리면 하이라이트)
    onHover: true,
  }

  useEffect(() => {
    loadLabels()
    loadAll()
  }, [loadLabels, loadAll])

  return (
    <div className="p-2 h-full flex flex-col gap-1.5 overflow-hidden">
      {/* 툴바: 헤더 + 검색 + Cypher + 라벨 — 한 줄로 압축 */}
      <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
        {/* 제목 + 통계 */}
        <h1 className="text-base font-bold text-white whitespace-nowrap">지식그래프</h1>
        <span className="text-xs text-gray-500 whitespace-nowrap">
          {stats.nodes}노드 · {stats.rels}관계
          {loading && ' · 로딩...'}
        </span>
        <div className="w-px h-5 bg-gray-700" />

        {/* 검색 */}
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="검색..."
          className="w-36 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 focus:border-blue-500 focus:outline-none"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-2 py-1 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-700"
        >
          검색
        </button>
        <div className="w-px h-5 bg-gray-700" />

        {/* Cypher */}
        <input
          type="text"
          value={cypherQuery}
          onChange={e => setCypherQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runCypher()}
          placeholder="Cypher..."
          className="w-48 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 font-mono focus:border-green-500 focus:outline-none"
        />
        <button
          onClick={runCypher}
          disabled={loading}
          className="px-2 py-1 rounded text-xs font-semibold bg-green-600 hover:bg-green-700 text-white disabled:bg-gray-700"
        >
          실행
        </button>
        <div className="w-px h-5 bg-gray-700" />

        {/* 버튼 */}
        <button
          onClick={() => { setActiveLabel(''); loadAll() }}
          className="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-300"
        >
          전체
        </button>
        <button
          onClick={() => nvlRef.current?.fit?.(nodes.map(n => n.id))}
          className="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-300"
        >
          맞춤
        </button>
      </div>

      {/* 에러 */}
      {error && (
        <div className="px-3 py-1.5 rounded text-xs bg-red-900/40 text-red-300 border border-red-800 flex-shrink-0">
          {error}
        </div>
      )}

      {/* 라벨 필터 */}
      {labels.length > 0 && (
        <div className="flex gap-1.5 flex-wrap flex-shrink-0">
          {labels.map(l => (
            <button
              key={l.label}
              onClick={() => { setActiveLabel(l.label); loadAll(l.label) }}
              className={`px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors ${
                activeLabel === l.label
                  ? 'text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
              style={activeLabel === l.label
                ? { backgroundColor: LABEL_COLORS[l.label] || DEFAULT_COLOR }
                : undefined
              }
            >
              {l.label} ({l.count})
            </button>
          ))}
        </div>
      )}

      {/* 메인: 그래프 + 상세 패널 — 남은 공간 전부 사용 */}
      <div className="flex-1 flex gap-2 min-h-0">
        {/* 그래프 시각화 — 전체 확장 */}
        <div className="flex-1 bg-gray-900 rounded-lg border border-gray-800 overflow-hidden relative">
          {nvlNodes.length > 0 ? (
            <InteractiveNvlWrapper
              ref={nvlRef}
              nodes={nvlNodes}
              rels={nvlRels}
              mouseEventCallbacks={mouseCallbacks}
              interactionOptions={{
                selectOnClick: true,
                drawShadowOnHover: true,
              }}
              nvlOptions={{
                allowDynamicMinZoom: true,
                disableWebGL: false,
                initialZoom: 1,
              }}
              style={{ width: '100%', height: '100%' }}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm">
              {loading ? '그래프 로딩 중...' : '노드가 없습니다'}
            </div>
          )}

          {/* Cypher 결과 — 그래프 위에 오버레이 */}
          {cypherRows.length > 0 && (
            <div className="absolute bottom-0 left-0 right-0 bg-gray-900/95 border-t border-gray-700 p-3 max-h-40 overflow-auto">
              <h3 className="text-xs font-bold text-gray-300 mb-1.5">
                쿼리 결과 ({cypherRows.length}건)
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    {Object.keys(cypherRows[0]).map(k => (
                      <th key={k} className="text-left px-2 py-0.5">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {cypherRows.slice(0, 50).map((row, i) => (
                    <tr key={i} className="border-b border-gray-800/50">
                      {Object.values(row).map((v, j) => (
                        <td key={j} className="px-2 py-0.5 text-gray-300">
                          {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 상세 패널 — 노드 선택 시에만 표시 */}
        {selectedNode && (
          <div className="w-72 bg-gray-900 rounded-lg border border-gray-800 p-3 overflow-y-auto flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-white truncate">{selectedNode.caption}</h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-500 hover:text-gray-300 text-lg leading-none"
              >
                x
              </button>
            </div>

            <div className="flex gap-1 mb-2 flex-wrap">
              {selectedNode.labels.map(l => (
                <span
                  key={l}
                  className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                  style={{ backgroundColor: LABEL_COLORS[l] || DEFAULT_COLOR }}
                >
                  {l}
                </span>
              ))}
            </div>

            <div className="space-y-1.5">
              {Object.entries(selectedNode.properties).map(([key, val]) => (
                <div key={key}>
                  <div className="text-[11px] text-gray-500">{key}</div>
                  <div className="text-xs text-gray-200 break-words">
                    {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => expandNode(selectedNode.id)}
              disabled={loading}
              className="mt-3 w-full px-2 py-1.5 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-700"
            >
              이웃 노드 확장
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
