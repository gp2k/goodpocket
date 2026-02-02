import { useState, useEffect, useRef, useCallback } from 'react'
import { Cluster, ClusterDetail, clustersApi } from '../lib/api'
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force'

interface ClusterMindmapProps {
  clusters: Cluster[]
}

interface ExpandedClusters {
  [key: number]: ClusterDetail | null
}

interface MindmapNode extends SimulationNodeDatum {
  id: string
  type: 'root' | 'cluster' | 'bookmark'
  label: string
  size?: number
  url?: string
  clusterId?: number
  radius: number
  x?: number
  y?: number
  fx?: number
  fy?: number
}

interface MindmapLink extends SimulationLinkDatum<MindmapNode> {
  source: string | MindmapNode
  target: string | MindmapNode
}

interface SavedPosition {
  x: number
  y: number
}

interface ClusterSector {
  startAngle: number
  endAngle: number
  centerAngle: number
}

export default function ClusterMindmap({ clusters }: ClusterMindmapProps) {
  const [expandedClusters, setExpandedClusters] = useState<ExpandedClusters>({})
  const [loadingCluster, setLoadingCluster] = useState<number | null>(null)
  const [nodes, setNodes] = useState<MindmapNode[]>([])
  const [links, setLinks] = useState<MindmapLink[]>([])
  const [isSimulating, setIsSimulating] = useState(true)
  const simulationRef = useRef<ReturnType<typeof forceSimulation<MindmapNode>> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Track if initial cluster layout is complete
  const [initialLayoutDone, setInitialLayoutDone] = useState(false)
  const clusterPositionsRef = useRef<Map<string, SavedPosition>>(new Map())
  
  // Sector boundaries for each cluster
  const clusterSectorsRef = useRef<Map<number, ClusterSector>>(new Map())

  // Zoom and Pan state
  const [scale, setScale] = useState(0.85)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const lastMousePos = useRef({ x: 0, y: 0 })

  const totalBookmarks = clusters.reduce((sum, c) => sum + c.size, 0)
  
  const WIDTH = 1400
  const HEIGHT = 1000
  const CENTER_X = WIDTH / 2
  const CENTER_Y = HEIGHT / 2

  // Build nodes and links from clusters and expanded bookmarks
  const buildGraph = useCallback(() => {
    const newNodes: MindmapNode[] = []
    const newLinks: MindmapLink[] = []

    // Root node - always fixed at center
    newNodes.push({
      id: 'root',
      type: 'root',
      label: '내 북마크',
      radius: 60,
      x: CENTER_X,
      y: CENTER_Y,
      fx: CENTER_X,
      fy: CENTER_Y,
    })

    // Cluster nodes
    clusters.forEach((cluster, index) => {
      const clusterId = `cluster-${cluster.cluster_id}`
      const angle = (2 * Math.PI * index) / clusters.length - Math.PI / 2
      const initialRadius = 280
      
      // Check if we have a saved position for this cluster
      const savedPos = clusterPositionsRef.current.get(clusterId)
      
      if (initialLayoutDone && savedPos) {
        // Use saved fixed position
        newNodes.push({
          id: clusterId,
          type: 'cluster',
          label: cluster.label || `클러스터 ${cluster.cluster_id}`,
          size: cluster.size,
          clusterId: cluster.cluster_id,
          radius: 55,
          x: savedPos.x,
          y: savedPos.y,
          fx: savedPos.x,  // Fix position
          fy: savedPos.y,
        })
      } else {
        // Initial position (will be adjusted by simulation)
        newNodes.push({
          id: clusterId,
          type: 'cluster',
          label: cluster.label || `클러스터 ${cluster.cluster_id}`,
          size: cluster.size,
          clusterId: cluster.cluster_id,
          radius: 55,
          x: CENTER_X + Math.cos(angle) * initialRadius,
          y: CENTER_Y + Math.sin(angle) * initialRadius,
        })
      }

      newLinks.push({
        source: 'root',
        target: clusterId,
      })

      // Bookmark nodes (if expanded)
      const expanded = expandedClusters[cluster.cluster_id]
      if (expanded) {
        // Get cluster position for bookmark placement
        const clusterPos = clusterPositionsRef.current.get(clusterId) || {
          x: CENTER_X + Math.cos(angle) * initialRadius,
          y: CENTER_Y + Math.sin(angle) * initialRadius,
        }
        
        // Calculate angle from center to cluster for radial bookmark placement
        const clusterAngle = Math.atan2(clusterPos.y - CENTER_Y, clusterPos.x - CENTER_X)
        
        expanded.bookmarks.slice(0, 8).forEach((bookmark, bIndex) => {
          const spreadAngle = Math.PI * 0.5
          const startAngle = clusterAngle - spreadAngle / 2
          const bookmarkCount = Math.min(expanded.bookmarks.length, 8)
          const bookmarkAngle = bookmarkCount > 1
            ? startAngle + (spreadAngle * bIndex) / (bookmarkCount - 1)
            : clusterAngle
          const bookmarkDistance = 180  // Distance from cluster
          
          newNodes.push({
            id: `bookmark-${bookmark.id}`,
            type: 'bookmark',
            label: bookmark.title || '(제목 없음)',
            url: bookmark.url,
            clusterId: cluster.cluster_id,
            radius: 55,
            x: clusterPos.x + Math.cos(bookmarkAngle) * bookmarkDistance,
            y: clusterPos.y + Math.sin(bookmarkAngle) * bookmarkDistance,
          })

          newLinks.push({
            source: clusterId,
            target: `bookmark-${bookmark.id}`,
          })
        })
      }
    })

    return { nodes: newNodes, links: newLinks }
  }, [clusters, expandedClusters, CENTER_X, CENTER_Y, initialLayoutDone])

  // Run force simulation
  useEffect(() => {
    const { nodes: newNodes, links: newLinks } = buildGraph()

    if (simulationRef.current) {
      simulationRef.current.stop()
    }

    setIsSimulating(true)

    // Different simulation settings based on whether initial layout is done
    const simulation = forceSimulation<MindmapNode>(newNodes)
      .force('link', forceLink<MindmapNode, MindmapLink>(newLinks)
        .id((d: MindmapNode) => d.id)
        .distance((d: SimulationLinkDatum<MindmapNode>) => {
          const source = d.source as MindmapNode
          const target = d.target as MindmapNode
          if (source.type === 'root') return 250
          if (target.type === 'bookmark') return 160
          return 150
        })
        .strength((d: SimulationLinkDatum<MindmapNode>) => {
          const target = d.target as MindmapNode
          // Weaker link strength for bookmarks when clusters are fixed
          if (initialLayoutDone && target.type === 'bookmark') return 0.5
          return 0.8
        })
      )
      .force('charge', forceManyBody<MindmapNode>()
        .strength((d: MindmapNode) => {
          if (d.type === 'root') return -1500
          if (d.type === 'cluster') return initialLayoutDone ? -200 : -1000
          return -300  // Bookmarks repel each other
        })
      )
      .force('center', forceCenter(CENTER_X, CENTER_Y).strength(initialLayoutDone ? 0 : 0.02))
      .force('collision', forceCollide<MindmapNode>()
        .radius((d: MindmapNode) => {
          if (d.type === 'cluster') return d.radius + 70
          if (d.type === 'root') return d.radius + 50
          return d.radius + 35
        })
        .strength(1)
        .iterations(5)
      )
      .alphaDecay(initialLayoutDone ? 0.05 : 0.025)  // Faster decay when just adding bookmarks
      .velocityDecay(0.4)

    simulation.on('tick', () => {
      // Constrain bookmarks to their cluster's sector and minimum distance
      newNodes.forEach(node => {
        if (node.type === 'bookmark' && node.clusterId !== undefined && 
            node.x !== undefined && node.y !== undefined) {
          const sector = clusterSectorsRef.current.get(node.clusterId)
          
          // Find parent cluster's distance from center
          const parentClusterNode = newNodes.find(
            n => n.type === 'cluster' && n.clusterId === node.clusterId
          )
          
          if (sector) {
            // Calculate current angle from center
            const dx = node.x - CENTER_X
            const dy = node.y - CENTER_Y
            let currentAngle = Math.atan2(dy, dx)
            let distance = Math.sqrt(dx * dx + dy * dy)
            
            // Ensure bookmark is further from center than its parent cluster
            if (parentClusterNode && parentClusterNode.x !== undefined && parentClusterNode.y !== undefined) {
              const clusterDx = parentClusterNode.x - CENTER_X
              const clusterDy = parentClusterNode.y - CENTER_Y
              const clusterDistance = Math.sqrt(clusterDx * clusterDx + clusterDy * clusterDy)
              const minDistance = clusterDistance + 100  // Minimum 100px further than cluster
              
              if (distance < minDistance) {
                distance = minDistance
              }
            }
            
            // Normalize angle to be relative to sector center
            let angleDiff = currentAngle - sector.centerAngle
            // Normalize to -PI to PI range
            while (angleDiff > Math.PI) angleDiff -= 2 * Math.PI
            while (angleDiff < -Math.PI) angleDiff += 2 * Math.PI
            
            // Calculate sector half-width
            const sectorHalfWidth = (sector.endAngle - sector.startAngle) / 2
            
            // Clamp to sector boundaries
            if (angleDiff > sectorHalfWidth) {
              currentAngle = sector.centerAngle + sectorHalfWidth
            } else if (angleDiff < -sectorHalfWidth) {
              currentAngle = sector.centerAngle - sectorHalfWidth
            }
            
            // Update position with constrained angle and distance
            node.x = CENTER_X + Math.cos(currentAngle) * distance
            node.y = CENTER_Y + Math.sin(currentAngle) * distance
          }
        }
      })
      
      setNodes([...newNodes])
      setLinks([...newLinks])
    })

    simulation.on('end', () => {
      setIsSimulating(false)
      
      // Save cluster positions after initial layout
      if (!initialLayoutDone) {
        newNodes.forEach(node => {
          if (node.type === 'cluster' && node.x !== undefined && node.y !== undefined) {
            clusterPositionsRef.current.set(node.id, { x: node.x, y: node.y })
          }
        })
        setInitialLayoutDone(true)
      }
    })

    // Let simulation run
    setTimeout(() => {
      simulation.alpha(initialLayoutDone ? 0.3 : 0.5)
    }, 100)

    simulationRef.current = simulation

    return () => {
      simulation.stop()
    }
  }, [buildGraph, CENTER_X, CENTER_Y, initialLayoutDone])

  // Reset initial layout and calculate sectors when clusters change
  useEffect(() => {
    setInitialLayoutDone(false)
    clusterPositionsRef.current.clear()
    
    // Calculate sector boundaries for each cluster
    clusterSectorsRef.current.clear()
    const sectorSize = (2 * Math.PI) / clusters.length
    const padding = sectorSize * 0.08  // Small padding between sectors
    
    clusters.forEach((cluster, index) => {
      const centerAngle = (2 * Math.PI * index) / clusters.length - Math.PI / 2
      clusterSectorsRef.current.set(cluster.cluster_id, {
        centerAngle,
        startAngle: centerAngle - sectorSize / 2 + padding,
        endAngle: centerAngle + sectorSize / 2 - padding,
      })
    })
  }, [clusters])

  // Mouse wheel zoom handler
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault()
      const delta = e.deltaY > 0 ? 0.92 : 1.08
      setScale(prev => Math.min(2, Math.max(0.3, prev * delta)))
    }

    container.addEventListener('wheel', handleWheel, { passive: false })
    return () => container.removeEventListener('wheel', handleWheel)
  }, [])

  // Right-click panning handlers
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
      setPan(prev => ({
        x: prev.x + dx,
        y: prev.y + dy
      }))
      lastMousePos.current = { x: e.clientX, y: e.clientY }
    }
  }

  const handleMouseUp = () => {
    setIsPanning(false)
  }

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
  }

  const resetView = () => {
    setScale(0.85)
    setPan({ x: 0, y: 0 })
  }

  const toggleCluster = async (cluster: Cluster) => {
    const clusterId = cluster.cluster_id

    if (expandedClusters[clusterId]) {
      setExpandedClusters((prev) => {
        const newState = { ...prev }
        delete newState[clusterId]
        return newState
      })
      return
    }

    try {
      setLoadingCluster(clusterId)
      const detail = await clustersApi.get(clusterId)
      setExpandedClusters((prev) => ({
        ...prev,
        [clusterId]: detail,
      }))
    } catch (error) {
      console.error('Failed to load cluster details:', error)
    } finally {
      setLoadingCluster(null)
    }
  }

  const getDomain = (url: string) => {
    try {
      return new URL(url).hostname.replace('www.', '')
    } catch {
      return url
    }
  }

  const getNodePosition = (nodeRef: string | MindmapNode): { x: number; y: number } | null => {
    if (typeof nodeRef === 'object' && nodeRef.x !== undefined && nodeRef.y !== undefined) {
      return { x: nodeRef.x, y: nodeRef.y }
    }
    const node = nodes.find(n => n.id === nodeRef)
    if (node && node.x !== undefined && node.y !== undefined) {
      return { x: node.x, y: node.y }
    }
    return null
  }

  return (
    <div 
      ref={containerRef}
      className="radial-mindmap-container relative overflow-hidden cursor-grab select-none"
      style={{ height: '700px' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onContextMenu={handleContextMenu}
    >
      {/* Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center space-x-2">
        <div className="bg-white/90 backdrop-blur rounded-lg shadow-md px-3 py-1.5 text-xs text-gray-600">
          휠: 줌 | 우클릭 드래그: 이동
        </div>
        <button
          onClick={resetView}
          className="bg-white/90 backdrop-blur rounded-lg shadow-md px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-100 transition-colors"
        >
          초기화
        </button>
        <div className="bg-white/90 backdrop-blur rounded-lg shadow-md px-3 py-1.5 text-xs text-gray-600">
          {Math.round(scale * 100)}%
        </div>
      </div>

      {/* Transformed content */}
      <div 
        className="radial-mindmap absolute"
        style={{ 
          width: `${WIDTH}px`, 
          height: `${HEIGHT}px`,
          left: '50%',
          top: '50%',
          transform: `translate(-50%, -50%) translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
          transformOrigin: 'center center',
          transition: isPanning || isSimulating ? 'none' : 'transform 0.1s ease-out',
          cursor: isPanning ? 'grabbing' : 'grab',
        }}
      >
        {/* SVG for connection lines */}
        <svg 
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 1, overflow: 'visible' }}
        >
          <defs>
            <linearGradient id="linkGradientRoot" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.6" />
            </linearGradient>
            <linearGradient id="linkGradientBookmark" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#34d399" stopOpacity="0.4" />
            </linearGradient>
          </defs>
          
          {links.map((link, i) => {
            const sourcePos = getNodePosition(link.source)
            const targetPos = getNodePosition(link.target)
            if (!sourcePos || !targetPos) return null
            
            const sourceNode = typeof link.source === 'object' ? link.source : nodes.find(n => n.id === link.source)
            const isRootLink = sourceNode?.type === 'root'
            
            return (
              <line
                key={`link-${i}`}
                x1={sourcePos.x}
                y1={sourcePos.y}
                x2={targetPos.x}
                y2={targetPos.y}
                stroke={isRootLink ? 'url(#linkGradientRoot)' : 'url(#linkGradientBookmark)'}
                strokeWidth={isRootLink ? 3 : 2}
                style={{ transition: isSimulating ? 'none' : 'all 0.1s ease-out' }}
              />
            )
          })}
        </svg>

        {/* Nodes */}
        {nodes.map((node) => {
          if (node.x === undefined || node.y === undefined) return null

          // Root Node
          if (node.type === 'root') {
            return (
              <div
                key={node.id}
                className="absolute transform -translate-x-1/2 -translate-y-1/2"
                style={{ 
                  left: node.x, 
                  top: node.y, 
                  zIndex: 10,
                  transition: isSimulating ? 'none' : 'all 0.1s ease-out'
                }}
              >
                <div className="root-node bg-gradient-to-br from-indigo-600 to-purple-600 text-white px-6 py-4 rounded-2xl shadow-xl font-semibold text-center">
                  <div className="flex items-center justify-center space-x-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                    </svg>
                    <span>{node.label}</span>
                  </div>
                  <div className="text-indigo-200 text-sm mt-1">
                    {totalBookmarks}개 · {clusters.length}개 클러스터
                  </div>
                </div>
              </div>
            )
          }

          // Cluster Node
          if (node.type === 'cluster') {
            const cluster = clusters.find(c => c.cluster_id === node.clusterId)
            if (!cluster) return null
            
            const isExpanded = !!expandedClusters[node.clusterId!]
            const isLoading = loadingCluster === node.clusterId

            return (
              <div
                key={node.id}
                className="absolute transform -translate-x-1/2 -translate-y-1/2"
                style={{ 
                  left: node.x, 
                  top: node.y, 
                  zIndex: 5,
                  transition: isSimulating ? 'none' : 'all 0.1s ease-out'
                }}
              >
                <div
                  onClick={() => toggleCluster(cluster)}
                  className={`cluster-node cursor-pointer transition-all duration-200 ${
                    isExpanded
                      ? 'bg-emerald-100 border-emerald-500 shadow-lg scale-105'
                      : 'bg-emerald-50 border-emerald-300 hover:border-emerald-500 hover:scale-105 hover:shadow-lg'
                  } border-2 px-5 py-3 rounded-xl shadow-md text-center`}
                  style={{ minWidth: '140px', maxWidth: '180px' }}
                >
                  <div className="flex items-center justify-center space-x-2">
                    {isLoading ? (
                      <svg className="animate-spin h-4 w-4 text-emerald-600" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <div className={`w-2.5 h-2.5 rounded-full ${isExpanded ? 'bg-emerald-600' : 'bg-emerald-400'}`} />
                    )}
                    <span className="font-semibold text-emerald-900 text-sm leading-tight">
                      {node.label}
                    </span>
                  </div>
                  <div className="text-xs text-emerald-700 mt-1.5 font-medium">
                    {node.size}개 북마크
                  </div>
                </div>
              </div>
            )
          }

          // Bookmark Node
          if (node.type === 'bookmark') {
            return (
              <div
                key={node.id}
                className="absolute transform -translate-x-1/2 -translate-y-1/2"
                style={{ 
                  left: node.x, 
                  top: node.y, 
                  zIndex: 3,
                  transition: isSimulating ? 'none' : 'all 0.1s ease-out'
                }}
              >
                <a
                  href={node.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bookmark-node block bg-white hover:bg-blue-50 border border-gray-200 hover:border-blue-400 px-3 py-2.5 rounded-lg shadow-sm hover:shadow-md transition-all duration-150 text-center"
                  style={{ maxWidth: '200px', minWidth: '120px' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div 
                    className="text-xs text-gray-800 hover:text-blue-600 font-medium leading-relaxed"
                    style={{ 
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      wordBreak: 'keep-all',
                    }}
                  >
                    {node.label}
                  </div>
                  <div className="text-[10px] text-gray-400 mt-1.5 truncate">
                    {getDomain(node.url || '')}
                  </div>
                </a>
              </div>
            )
          }

          return null
        })}
      </div>
    </div>
  )
}
