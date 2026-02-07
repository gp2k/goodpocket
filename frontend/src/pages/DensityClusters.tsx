import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { densityClustersApi, Cluster, ClusterDetail as ClusterDetailType } from '../lib/api'
import ClusterList from '../components/ClusterList'
import ClusterDetail from '../components/ClusterDetail'

export default function DensityClusters() {
  const { clusterId } = useParams()
  const navigate = useNavigate()

  const [clusters, setClusters] = useState<Cluster[]>([])
  const [selectedCluster, setSelectedCluster] = useState<ClusterDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await densityClustersApi.list({ limit: 30 })
        setClusters(res.items)
      } catch (err) {
        setError(err instanceof Error ? err.message : '밀도 기반 클러스터를 불러오는 중 오류가 발생했습니다')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  useEffect(() => {
    if (!clusterId) {
      setSelectedCluster(null)
      return
    }

    const loadClusterDetail = async () => {
      try {
        const detail = await densityClustersApi.get(clusterId)
        setSelectedCluster(detail)
      } catch (err) {
        setError(err instanceof Error ? err.message : '클러스터 상세를 불러오는 중 오류가 발생했습니다')
      }
    }

    loadClusterDetail()
  }, [clusterId])

  const handleSelectCluster = (cluster: Cluster) => {
    navigate(`/density-clusters/${cluster.id}`)
  }

  const handleBack = () => {
    navigate('/density-clusters')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">밀도 기반 클러스터</h1>
          <p className="text-gray-600">임베딩 기반 HDBSCAN으로 밀도에 따라 그룹화된 북마크입니다</p>
        </div>
        {selectedCluster && (
          <button
            onClick={handleBack}
            className="px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md"
          >
            목록으로
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      )}

      {!loading && !selectedCluster && clusters.length > 0 && (
        <ClusterList clusters={clusters} onSelect={handleSelectCluster} />
      )}

      {selectedCluster && <ClusterDetail cluster={selectedCluster} />}

      {!loading && !selectedCluster && clusters.length === 0 && (
        <div className="text-center py-12">
          <div className="text-gray-400 text-5xl mb-4">📊</div>
          <h3 className="text-lg font-medium text-gray-900">밀도 기반 클러스터가 없습니다</h3>
          <p className="text-gray-600 mt-2">
            북마크가 5개 이상이고 임베딩이 생성되면 배치 작업에서 HDBSCAN 클러스터링이 실행됩니다.
            <br />
            클러스터링은 주기적으로 실행됩니다.
          </p>
        </div>
      )}
    </div>
  )
}
