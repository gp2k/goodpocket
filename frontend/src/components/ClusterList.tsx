import { Cluster } from '../lib/api'

interface ClusterListProps {
  clusters: Cluster[]
  onSelect: (cluster: Cluster) => void
}

export default function ClusterList({ clusters, onSelect }: ClusterListProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {clusters.map((cluster) => (
        <div
          key={cluster.id}
          onClick={() => onSelect(cluster)}
          className="bg-white rounded-lg shadow p-5 cursor-pointer hover:shadow-md transition-shadow"
        >
          {/* Cluster label */}
          <h3 className="text-base font-medium text-gray-900 mb-2">
            {cluster.label || `그룹 ${cluster.id.slice(0, 8)}`}
          </h3>

          {/* Stats */}
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span className="flex items-center">
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              {cluster.size}개 북마크
            </span>
            <span>{formatDate(cluster.updated_at)}</span>
          </div>

          {/* Tags preview from label */}
          {cluster.label && (
            <div className="flex flex-wrap gap-1 mt-3">
              {cluster.label.split(', ').slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-700"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
