import { useState, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { TopicTreeEntry } from '../lib/api'

interface TopicTreeMindmapProps {
  tree: TopicTreeEntry
}

const WIDTH = 1400
const HEIGHT = 1000
const CENTER_X = WIDTH / 2
const CENTER_Y = HEIGHT / 2
const R1 = 280
const R2 = 150

const SENTINEL_LABEL = '__no_auto_tags__'

function displayLabel(label: string): string {
  if (label === SENTINEL_LABEL) return '태그 없음'
  return label
}

interface NodeLayout {
  id: string
  label: string
  x: number
  y: number
  level: 0 | 1 | 2
  dup_group_count: number
  dup_group_ids: string[]
  children: NodeLayout[]
  totalCount: number // self + descendants for display
}

function buildNodeLayout(
  entry: TopicTreeEntry,
  level: 0 | 1 | 2,
  x: number,
  y: number,
): NodeLayout {
  const children = (entry.children || []).map((c, j) => {
    const angle = (2 * Math.PI * j) / Math.max(entry.children!.length, 1) - Math.PI / 2
    return buildNodeLayout(
      c,
      2,
      x + Math.cos(angle) * R2,
      y + Math.sin(angle) * R2,
    )
  })
  const totalCount = entry.dup_group_count + children.reduce((s, c) => s + c.totalCount, 0)
  return {
    id: entry.id,
    label: entry.label,
    x,
    y,
    level,
    dup_group_count: entry.dup_group_count,
    dup_group_ids: entry.dup_group_ids || [],
    children,
    totalCount,
  }
}

function layoutTreeCollapsed(root: TopicTreeEntry): { rootNode: NodeLayout; level1Nodes: NodeLayout[] } {
  const rootNode = buildNodeLayout(root, 0, CENTER_X, CENTER_Y)
  const level1 = root.children || []
  const level1Nodes: NodeLayout[] = level1.map((c1, i) => {
    const angle1 = (2 * Math.PI * i) / Math.max(level1.length, 1) - Math.PI / 2
    return buildNodeLayout(
      c1,
      1,
      CENTER_X + Math.cos(angle1) * R1,
      CENTER_Y + Math.sin(angle1) * R1,
    )
  })
  return { rootNode, level1Nodes }
}

function buildLinksCollapsed(
  level1Nodes: NodeLayout[],
  expandedIds: Set<string>,
): { x1: number; y1: number; x2: number; y2: number }[] {
  const links: { x1: number; y1: number; x2: number; y2: number }[] = []
  level1Nodes.forEach((n1) => {
    links.push({ x1: CENTER_X, y1: CENTER_Y, x2: n1.x, y2: n1.y })
    if (expandedIds.has(n1.id) && n1.children.length > 0) {
      n1.children.forEach((n2) => {
        links.push({ x1: n1.x, y1: n1.y, x2: n2.x, y2: n2.y })
      })
    }
  })
  return links
}

export default function TopicTreeMindmap({ tree }: TopicTreeMindmapProps) {
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.85)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const lastMousePos = useRef({ x: 0, y: 0 })

  const { rootNode, level1Nodes } = useMemo(() => layoutTreeCollapsed(tree), [tree])
  const links = useMemo(
    () => buildLinksCollapsed(level1Nodes, expandedIds),
    [level1Nodes, expandedIds],
  )

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.92 : 1.08
    setScale((s) => Math.min(2, Math.max(0.3, s * delta)))
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 2) {
      e.preventDefault()
      setIsPanning(true)
      lastMousePos.current = { x: e.clientX, y: e.clientY }
    }
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      const dx = e.clientX - lastMousePos.current.x
      const dy = e.clientY - lastMousePos.current.y
      setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }))
      lastMousePos.current = { x: e.clientX, y: e.clientY }
    }
  }

  const handleMouseUp = () => setIsPanning(false)
  const handleContextMenu = (e: React.MouseEvent) => e.preventDefault()

  const handleNodeClick = (node: NodeLayout, isLevel1: boolean) => {
    if (isLevel1) {
      if (node.children.length > 0) {
        toggleExpand(node.id)
      } else if (node.dup_group_ids.length > 0) {
        navigate(`/clusters/${node.dup_group_ids[0]}`)
      }
    } else {
      if (node.dup_group_ids.length > 0) {
        navigate(`/clusters/${node.dup_group_ids[0]}`)
      }
    }
  }

  const totalGroups = level1Nodes.reduce((s, n) => s + n.totalCount, 0)
  const hasHierarchy = level1Nodes.length > 0

  if (!hasHierarchy) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center text-gray-600">
        카테고리 트리가 없습니다. 마이그레이션을 실행하면 태그 기반 계층이 생성됩니다.
      </div>
    )
  }

  const visibleLevel2Nodes: NodeLayout[] = []
  level1Nodes.forEach((n1) => {
    if (expandedIds.has(n1.id)) {
      n1.children.forEach((n2) => visibleLevel2Nodes.push(n2))
    }
  })

  return (
    <div
      ref={containerRef}
      className="relative overflow-hidden cursor-grab select-none"
      style={{ height: '700px' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onContextMenu={handleContextMenu}
      onWheel={handleWheel}
    >
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <span className="bg-white/90 backdrop-blur rounded-lg shadow px-3 py-1.5 text-xs text-gray-600">
          휠: 줌 | 우클릭 드래그: 이동 | 클릭: 펼치기/이동
        </span>
        <button
          type="button"
          onClick={() => { setScale(0.85); setPan({ x: 0, y: 0 }) }}
          className="bg-white/90 backdrop-blur rounded-lg shadow px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-100"
        >
          초기화
        </button>
        <span className="bg-white/90 backdrop-blur rounded-lg shadow px-3 py-1.5 text-xs text-gray-600">
          {Math.round(scale * 100)}%
        </span>
      </div>

      <div
        className="absolute"
        style={{
          width: WIDTH,
          height: HEIGHT,
          left: '50%',
          top: '50%',
          transform: `translate(-50%, -50%) translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
          transformOrigin: 'center center',
          cursor: isPanning ? 'grabbing' : 'grab',
        }}
      >
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="topicLinkGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.6" />
            </linearGradient>
          </defs>
          {links.map((link, i) => (
            <line
              key={i}
              x1={link.x1}
              y1={link.y1}
              x2={link.x2}
              y2={link.y2}
              stroke="url(#topicLinkGrad)"
              strokeWidth={2}
            />
          ))}
        </svg>

        {/* Root */}
        <div
          className="absolute transform -translate-x-1/2 -translate-y-1/2"
          style={{ left: rootNode.x, top: rootNode.y, zIndex: 10 }}
        >
          <div className="bg-gradient-to-br from-indigo-600 to-purple-600 text-white px-6 py-4 rounded-2xl shadow-xl font-semibold text-center">
            <div>{displayLabel(rootNode.label)}</div>
            <div className="text-indigo-200 text-sm mt-1">
              {totalGroups}개 그룹 · {level1Nodes.length}개 카테고리
            </div>
          </div>
        </div>

        {/* Level1: 항상 표시, 접힌 상태로 개수만 표시 */}
        {level1Nodes.map((node) => (
          <div
            key={node.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2"
            style={{ left: node.x, top: node.y, zIndex: 5 }}
          >
            <button
              type="button"
              onClick={() => handleNodeClick(node, true)}
              title={node.label}
              className={`text-center rounded-xl shadow-md border-2 px-4 py-2.5 transition-all min-w-[120px] max-w-[200px] ${
                node.totalCount > 0
                  ? 'bg-emerald-50 border-emerald-300 hover:border-emerald-500 hover:shadow-lg cursor-pointer'
                  : 'bg-gray-50 border-gray-200 cursor-default'
              }`}
            >
              <div
                className="font-semibold text-gray-900 text-sm break-words leading-tight"
                style={{ wordBreak: 'break-word' }}
              >
                {displayLabel(node.label)}
              </div>
              <div className="text-xs text-emerald-700 mt-1">
                {node.totalCount > 0 ? `${node.totalCount}개` : '0개'}
                {node.children.length > 0 && !expandedIds.has(node.id) && ' · 클릭하여 펼치기'}
              </div>
            </button>
          </div>
        ))}

        {/* Level2: 펼쳐진 부모의 자식만 표시 */}
        {visibleLevel2Nodes.map((node) => (
          <div
            key={node.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2"
            style={{ left: node.x, top: node.y, zIndex: 4 }}
          >
            <button
              type="button"
              onClick={() => handleNodeClick(node, false)}
              title={node.label}
              className={`text-center rounded-lg shadow border-2 px-3 py-2 transition-all min-w-[100px] max-w-[180px] ${
                node.dup_group_count > 0
                  ? 'bg-white border-emerald-200 hover:border-emerald-400 hover:shadow cursor-pointer'
                  : 'bg-gray-50 border-gray-200 cursor-default'
              }`}
            >
              <div
                className="font-medium text-gray-800 text-xs break-words leading-tight"
                style={{ wordBreak: 'break-word' }}
              >
                {displayLabel(node.label)}
              </div>
              {node.dup_group_count > 0 && (
                <div className="text-xs text-emerald-600 mt-0.5">{node.dup_group_count}개 그룹</div>
              )}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
