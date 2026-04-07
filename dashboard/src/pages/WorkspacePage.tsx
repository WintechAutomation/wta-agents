// 업무공간 — 파일 탐색기 (lazy loading) + 업로드
import { useState, useEffect, useCallback, useRef } from 'react'

// ── 타입 ──
interface FileNode {
  name: string
  path: string
  type: 'file' | 'folder'
  size?: number
  modified?: string
  children?: FileNode[]
  _loaded?: boolean  // 하위 항목이 로드되었는지
}

interface FileContent {
  name: string
  path: string
  size: number
  modified: string
  content: string | null
  content_type: 'text' | 'image' | 'binary'
}

// ── 파일 크기 포맷 ──
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── 파일 아이콘 ──
function fileIcon(name: string, type: string): string {
  if (type === 'folder') return '\uD83D\uDCC1'
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const icons: Record<string, string> = {
    md: '\uD83D\uDCDD', txt: '\uD83D\uDCDD', html: '\uD83C\uDF10', htm: '\uD83C\uDF10',
    json: '\uD83D\uDCCB', csv: '\uD83D\uDCCA', py: '\uD83D\uDC0D', js: '\uD83D\uDFE8', ts: '\uD83D\uDD35',
    jpg: '\uD83D\uDDBC\uFE0F', jpeg: '\uD83D\uDDBC\uFE0F', png: '\uD83D\uDDBC\uFE0F', gif: '\uD83D\uDDBC\uFE0F',
    pdf: '\uD83D\uDCC4', log: '\uD83D\uDCDC', yml: '\u2699\uFE0F', yaml: '\u2699\uFE0F',
    pptx: '\uD83D\uDCCA', xlsx: '\uD83D\uDCCA', docx: '\uD83D\uDCDD',
  }
  return icons[ext] ?? '\uD83D\uDCC4'
}

// ── 폴더 하위 로드 함수 ──
async function fetchChildren(folderPath: string): Promise<FileNode[]> {
  try {
    const res = await fetch(`/api/workspace/tree?path=${encodeURIComponent(folderPath)}&depth=1`)
    const data = await res.json()
    return (data.tree ?? []).map((n: FileNode) => ({
      ...n,
      _loaded: n.type === 'file',
    }))
  } catch {
    return []
  }
}

// ── 트리 노드 컴포넌트 (lazy loading) ──
function TreeNode({
  node,
  depth,
  selectedPath,
  onSelect,
  onDelete,
}: {
  node: FileNode
  depth: number
  selectedPath: string | null
  onSelect: (node: FileNode) => void
  onDelete: (node: FileNode) => void
}) {
  const [open, setOpen] = useState(false)
  const [children, setChildren] = useState<FileNode[]>(node.children ?? [])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(node._loaded ?? false)

  const handleToggle = async () => {
    if (open) {
      setOpen(false)
      return
    }
    // 아직 하위를 로드하지 않았으면 fetch
    if (!loaded) {
      setLoading(true)
      const items = await fetchChildren(node.path)
      setChildren(items)
      setLoaded(true)
      setLoading(false)
    }
    setOpen(true)
  }

  if (node.type === 'folder') {
    return (
      <div>
        <button
          onClick={handleToggle}
          className="flex items-center gap-1.5 w-full text-left px-2 py-1 text-sm hover:bg-gray-800 rounded transition-colors text-gray-300"
          style={{ paddingLeft: depth * 16 + 8 }}
        >
          <span className="text-xs text-gray-500 w-3 text-center">
            {loading ? '\u23F3' : open ? '\u25BC' : '\u25B6'}
          </span>
          <span>{fileIcon(node.name, 'folder')}</span>
          <span className="truncate">{node.name}</span>
        </button>
        {open && children.map((child) => (
          <TreeNode
            key={child.path}
            node={child}
            depth={depth + 1}
            selectedPath={selectedPath}
            onSelect={onSelect}
            onDelete={onDelete}
          />
        ))}
      </div>
    )
  }

  const isSelected = selectedPath === node.path
  return (
    <div
      className={`group flex items-center gap-1.5 w-full px-2 py-1 text-sm rounded transition-colors ${
        isSelected
          ? 'bg-blue-600/20 text-blue-300 border-l-2 border-blue-500'
          : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
      }`}
      style={{ paddingLeft: depth * 16 + 8 }}
    >
      <button
        onClick={() => onSelect(node)}
        className="flex items-center gap-1.5 flex-1 min-w-0 text-left truncate"
      >
        <span>{fileIcon(node.name, 'file')}</span>
        <span className="truncate">{node.name}</span>
      </button>
      {node.size !== undefined && (
        <span className="text-xs text-gray-600 flex-shrink-0">{formatSize(node.size)}</span>
      )}
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(node) }}
        className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 text-xs flex-shrink-0 px-1 transition-opacity"
        title="삭제"
      >
        &times;
      </button>
    </div>
  )
}

// ── 미리보기 패널 ──
function PreviewPanel({
  file,
  onDownload,
}: {
  file: FileContent | null
  onDownload: (path: string) => void
}) {
  if (!file) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-600">
        <div className="text-center">
          <div className="text-4xl mb-2">{'\uD83D\uDCC2'}</div>
          <p className="text-sm">파일을 선택하면 미리보기가 표시됩니다</p>
        </div>
      </div>
    )
  }

  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* 파일 정보 헤더 */}
      <div className="flex items-center justify-between p-3 border-b border-gray-800 flex-shrink-0">
        <div>
          <div className="text-sm font-medium text-white">{file.name}</div>
          <div className="text-xs text-gray-500 mt-0.5">
            {formatSize(file.size)} &middot; {new Date(file.modified).toLocaleString('ko-KR')}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {file.name.endsWith('.html') && (
            <button
              onClick={() => {
                const name = file.name.replace(/\.html$/, '')
                const url = `https://agent.mes-wta.com/${name}`
                window.open(url, '_blank')
              }}
              className="px-3 py-1.5 text-xs bg-blue-900 hover:bg-blue-800 text-blue-300 rounded-lg transition-colors"
            >
              🔗 열기
            </button>
          )}
          <button
            onClick={() => onDownload(file.path)}
            className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
          >
            다운로드
          </button>
        </div>
      </div>

      {/* 콘텐츠 영역 */}
      <div className="flex-1 overflow-auto p-4">
        {file.content_type === 'image' && file.content && (
          <img
            src={file.content}
            alt={file.name}
            className="max-w-full h-auto rounded-lg"
          />
        )}

        {file.content_type === 'text' && file.content !== null && (
          ext === 'html' ? (
            <iframe
              srcDoc={file.content}
              title={file.name}
              className="w-full h-full min-h-[500px] bg-white rounded-lg"
              sandbox="allow-same-origin"
            />
          ) : (
            <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words font-mono leading-relaxed bg-gray-900/50 rounded-lg p-4">
              {file.content}
            </pre>
          )
        )}

        {file.content_type === 'binary' && (
          <div className="text-center text-gray-500 py-12">
            <div className="text-4xl mb-3">{fileIcon(file.name, 'file')}</div>
            <p className="text-sm">바이너리 파일은 미리보기를 지원하지 않습니다</p>
            <p className="text-xs text-gray-600 mt-1">다운로드하여 확인하세요</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── 메인 컴포넌트 ──
export default function WorkspacePage() {
  const [tree, setTree] = useState<FileNode[]>([])
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null)
  const [loading, setLoading] = useState(false)
  const [treeLoading, setTreeLoading] = useState(true)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 루트 트리 로드 (depth=1)
  const loadTree = useCallback(() => {
    setTreeLoading(true)
    fetch('/api/workspace/tree?depth=1')
      .then((r) => r.json())
      .then((data) => setTree(data.tree ?? []))
      .catch(() => setTree([]))
      .finally(() => setTreeLoading(false))
  }, [])

  useEffect(() => { loadTree() }, [loadTree])

  // 파일 선택
  const handleSelect = useCallback((node: FileNode) => {
    if (node.type !== 'file') return
    setSelectedPath(node.path)
    setLoading(true)
    fetch(`/api/workspace/file?path=${encodeURIComponent(node.path)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          setSelectedFile(null)
        } else {
          setSelectedFile(data as FileContent)
        }
      })
      .catch(() => setSelectedFile(null))
      .finally(() => setLoading(false))
  }, [])

  // 다운로드
  const handleDownload = useCallback((path: string) => {
    window.open(`/api/workspace/file?path=${encodeURIComponent(path)}&download=1`, '_blank')
  }, [])

  // 삭제
  const handleDelete = useCallback(async (node: FileNode) => {
    if (!confirm(`"${node.name}" 파일을 삭제하시겠습니까?`)) return
    try {
      const res = await fetch(`/api/workspace/file?path=${encodeURIComponent(node.path)}`, { method: 'DELETE' })
      if (res.ok) {
        if (selectedPath === node.path) {
          setSelectedPath(null)
          setSelectedFile(null)
        }
        loadTree()
      }
    } catch { /* ignore */ }
  }, [selectedPath, loadTree])

  // 업로드
  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadMsg(null)
    try {
      const formData = new FormData()
      for (const f of Array.from(files)) {
        formData.append('files', f)
      }
      const res = await fetch('/api/workspace/upload', { method: 'POST', body: formData })
      if (res.ok) {
        const data = await res.json()
        setUploadMsg({ ok: true, text: `${(data.files as string[]).length}개 업로드 완료` })
        loadTree()
      } else {
        const data = await res.json()
        setUploadMsg({ ok: false, text: data.error ?? '업로드 실패' })
      }
    } catch (err) {
      setUploadMsg({ ok: false, text: err instanceof Error ? err.message : '업로드 오류' })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setTimeout(() => setUploadMsg(null), 3000)
    }
  }, [loadTree])

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="p-4 border-b border-gray-800 flex-shrink-0 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white" style={{ color: '#ffffff' }}>{'\uD83D\uDCC1'} 업무공간</h1>
          <p className="text-gray-400 text-sm mt-1">
            문서 탐색기 — 폴더 클릭 시 하위 항목 로드
          </p>
        </div>
        <div className="flex items-center gap-2">
          {uploadMsg && (
            <span className={`text-xs ${uploadMsg.ok ? 'text-green-400' : 'text-red-400'}`}>
              {uploadMsg.text}
            </span>
          )}
          <label className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors cursor-pointer flex items-center gap-1.5">
            {uploading ? '업로드 중...' : '파일 업로드'}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {/* 탐색기 본체 */}
      <div className="flex flex-1 min-h-0">
        {/* 좌측: 트리뷰 */}
        <div className="w-64 lg:w-72 flex-shrink-0 border-r border-gray-800 overflow-auto">
          <div className="p-2">
            {treeLoading ? (
              <div className="text-sm text-gray-500 p-3">불러오는 중...</div>
            ) : tree.length === 0 ? (
              <div className="text-sm text-gray-500 p-3">파일이 없습니다</div>
            ) : (
              tree.map((node) => (
                <TreeNode
                  key={node.path}
                  node={node}
                  depth={0}
                  selectedPath={selectedPath}
                  onSelect={handleSelect}
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>
        </div>

        {/* 우측: 미리보기 */}
        <div className="flex-1 flex flex-col min-h-0 bg-gray-950">
          {loading ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
              불러오는 중...
            </div>
          ) : (
            <PreviewPanel file={selectedFile} onDownload={handleDownload} />
          )}
        </div>
      </div>
    </div>
  )
}
