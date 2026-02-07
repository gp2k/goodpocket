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
const R2 = 160

interface NodeLayout {
  id: string
  label: string
  x: number
  y: number
  level: 0 | 1 | 2
  dup_group_count: number
  dup_group_ids: string[]
  children: NodeLayout[]
}

function layoutTree(root: TopicTreeEntry): NodeLayout[] {
  const nodes: NodeLayout[] = []
  const rootNode: NodeLayout = {
    id: root.id,
    label: root.label,
    x: CENTER_X,
    y: CENTER_Y,
    level: 0,
    dup_group_count: root.dup_group_count,
    dup_group_ids: root.dup_group_ids || [],
    children: [],
  }
  nodes.push(rootNode)

  const level1 = root.children || []
  level1.forEach((c1, i) => {
    const angle1 = (2 * Math.PI * i) / Math.max(level1.length, 1) - Math.PI / 2
    const child1: NodeLayout = {
      id: c1.id,
      label: c1.label,
      x: CENTER_X + Math.cos(angle1) * R1,
      y: CENTER_Y + Math.sin(angle1) * R1,
      level: 1,
      dup_group_count: c1.dup_group_count,
      dup_group_ids: c1.dup_group_ids || [],
      children: [],
    }
    nodes.push(child1)
    const level2 = c1.children || []
    level2.forEach((c2, j) => {
      const angle2 = angle1 + (Math.PI * 0.6 * (j - (level2.length - 1) / 2)) / Math.max(level2.length, 1)
      const child2: NodeLayout = {
        id: c2.id,
        label: c2.label,
        x: child1.x + Math.cos(angle2) * R2,
        y: child1.y + Math.sin(angle2) * R2,
        level: 2,
        dup_group_count: c2.dup_group_count,
        dup_group_ids: c2.dup_group_ids || [],
        children: [],
      }
      nodes.push(child2)
    })
  })

  return nodes
}

function buildLinks(root: TopicTreeEntry): { x1: number; y1: number; x2: number; y2: number }[] {
  const nodeMap = new Map<string, { x: number; y: number }>()
  nodeMap.set(root.id, { x: CENTER_X, y: CENTER_Y })
  const level1 = root.children || []
  level1.forEach((c1, i) => {
    const angle1 = (2 * Math.PI * i) / Math.max(level1.length, 1) - Math.PI / 2
    nodeMap.set(c1.id, {
      x: CENTER_X + Math.cos(angle1) * R1,
      y: CENTER_Y + Math.sin(angle1) * R1,
    })
    const level2 = c1.children || []
    level2.forEach((c2, j) => {
      const angle2 = angle1 + (Math.PI * 0.6 * (j - (level2.length - 1) / 2)) / Math.max(level2.length, 1)
      const x1 = CENTER_X + Math.cos(angle1) * R1
      const y1 = CENTER_Y + Math.sin(angle1) * R1
      nodeMap.set(c2.id, {
        x: x1 + Math.cos(angle2) * R2,
        y: y1 + Math.sin(angle2) * R2,
      })
    })
  })

  const links: { x1: number; y1: number; x2: number; y2: number }[] = []
  level1.forEach((c1, i) => {
    const angle1 = (2 * Math.PI * i) / Math.max(level1.length, 1) - Math.PI / 2
    const p1 = { x: CENTER_X + Math.cos(angle1) * R1, y: CENTER_Y + Math.sin(angle1) * R1 }
    links.push({ x1: CENTER_X, y1: CENTER_Y, x2: p1.x, y2: p1.y })
    const level2 = c1.children || []
    level2.forEach((_, j) => {
      const angle2 = angle1 + (Math.PI * 0.6 * (j - (level2.length - 1) / 2)) / Math.max(level2.length, 1)
      const p2 = { x: p1.x + Math.cos(angle2) * R2, y: p1.y + Math.sin(angle2) * R2 }
      links.push({ x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y })
    })
  })
  return links
}

export default function TopicTreeMindmap({ tree }: TopicTreeMindmapProps) {
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.85)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const lastMousePos = useRef({ x: 0, y: 0 })

  const nodes = useMemo(() => layoutTree(tree), [tree])
  const links = useMemo(() => buildLinks(tree), [tree])

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

  const handleNodeClick = (node: NodeLayout) => {
    if (node.level > 0 && node.dup_group_ids.length > 0) {
      navigate(`/clusters/${node.dup_group_ids[0]}`)
    }
  }

  const totalGroups = nodes.reduce((s, n) => s + n.dup_group_count, 0)
  const hasHierarchy = (tree.children?.length ?? 0) > 0

  if (!hasHierarchy) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center text-gray-600">
        카테고리 트리가 없습니다. 마이그레이션을 실행하면 태그 기반 계층이 생성됩니다.
      </div>
    )
  }

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
          휠: 줌 | 우클릭 드래그: 이동
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

        {nodes.map((node) => (
          <div
            key={node.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2"
            style={{ left: node.x, top: node.y, zIndex: node.level === 0 ? 10 : 5 }}
          >
            {node.level === 0 ? (
              <div className="bg-gradient-to-br from-indigo-600 to-purple-600 text-white px-6 py-4 rounded-2xl shadow-xl font-semibold text-center">
                <div>{node.label}</div>
                <div className="text-indigo-200 text-sm mt-1">
                  {totalGroups}개 그룹 · {tree.children?.length ?? 0}개 카테고리
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => handleNodeClick(node)}
                className={`text-center rounded-xl shadow-md border-2 px-4 py-2.5 transition-all ${
                  node.dup_group_count > 0
                    ? 'bg-emerald-50 border-emerald-300 hover:border-emerald-500 hover:shadow-lg cursor-pointer'
                    : 'bg-gray-50 border-gray-200 cursor-default'
                }`}
                style={{ minWidth: '100px', maxWidth: '180px' }}
              >
                <div className="font-semibold text-gray-900 text-sm truncate">{node.label}</div>
                {node.dup_group_count > 0 && (
                  <div className="text-xs text-emerald-700 mt-1">{node.dup_group_count}개 그룹</div>
                )}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
