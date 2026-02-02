import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { clustersApi, Cluster, ClusterDetail as ClusterDetailType } from '../lib/api'
import ClusterList from '../components/ClusterList'
import ClusterDetail from '../components/ClusterDetail'
import ClusterMindmap from '../components/ClusterMindmap'

type ViewMode = 'list' | 'mindmap'

export default function Clusters() {
  const { clusterId } = useParams()
  const navigate = useNavigate()
  
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [selectedCluster, setSelectedCluster] = useState<ClusterDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('mindmap')

  // Load clusters list
  useEffect(() => {
    const loadClusters = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await clustersApi.list()
        setClusters(response.items)
      } catch (err) {
        setError(err instanceof Error ? err.message : '클러스터를 불러오는 중 오류가 발생했습니다')
      } finally {
        setLoading(false)
      }
    }

    loadClusters()
  }, [])

  // Load selected cluster details
  useEffect(() => {
    if (!clusterId) {
      setSelectedCluster(null)
      return
    }

    const loadClusterDetail = async () => {
      try {
        const detail = await clustersApi.get(parseInt(clusterId))
        setSelectedCluster(detail)
      } catch (err) {
        setError(err instanceof Error ? err.message : '클러스터 상세를 불러오는 중 오류가 발생했습니다')
      }
    }

    loadClusterDetail()
  }, [clusterId])

  const handleSelectCluster = (cluster: Cluster) => {
    navigate(`/clusters/${cluster.cluster_id}`)
  }

  const handleBack = () => {
    navigate('/clusters')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">클러스터</h1>
          <p className="text-gray-600">비슷한 북마크들이 자동으로 그룹화됩니다</p>
        </div>
        <div className="flex items-center space-x-2">
          {/* View Mode Toggle */}
          {!selectedCluster && clusters.length > 0 && (
            <div className="flex items-center bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('mindmap')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === 'mindmap'
                    ? 'bg-white text-indigo-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <span className="flex items-center space-x-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>마인드맵</span>
                </span>
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === 'list'
                    ? 'bg-white text-indigo-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <span className="flex items-center space-x-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                  </svg>
                  <span>리스트</span>
                </span>
              </button>
            </div>
          )}
          
          {selectedCluster && (
            <button
              onClick={handleBack}
              className="px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md"
            >
              목록으로
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      )}

      {/* Content */}
      {!loading && !selectedCluster && clusters.length > 0 && (
        viewMode === 'mindmap' ? (
          <ClusterMindmap clusters={clusters} />
        ) : (
          <ClusterList clusters={clusters} onSelect={handleSelectCluster} />
        )
      )}

      {selectedCluster && (
        <ClusterDetail cluster={selectedCluster} />
      )}

      {/* Empty state */}
      {!loading && clusters.length === 0 && (
        <div className="text-center py-12">
          <div className="text-gray-400 text-5xl mb-4">📚</div>
          <h3 className="text-lg font-medium text-gray-900">클러스터가 없습니다</h3>
          <p className="text-gray-600 mt-2">
            북마크가 5개 이상 모이면 자동으로 클러스터링됩니다.<br />
            클러스터링은 3시간마다 실행됩니다.
          </p>
        </div>
      )}
    </div>
  )
}
