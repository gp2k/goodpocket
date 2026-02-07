import { ClusterDetail as ClusterDetailType } from '../lib/api'

interface ClusterDetailProps {
  cluster: ClusterDetailType
}

export default function ClusterDetail({ cluster }: ClusterDetailProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const getDomain = (url: string) => {
    try {
      return new URL(url).hostname
    } catch {
      return url
    }
  }

  return (
    <div className="space-y-6">
      {/* Cluster header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900">
          {cluster.label || `그룹 ${cluster.id.slice(0, 8)}`}
        </h2>
        <p className="text-gray-600 mt-1">{cluster.size}개의 북마크</p>
        
        {/* Tags from label */}
        {cluster.label && (
          <div className="flex flex-wrap gap-2 mt-4">
            {cluster.label.split(', ').map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary-100 text-primary-700"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Bookmarks in cluster */}
      <div className="bg-white rounded-lg shadow divide-y">
        {cluster.bookmarks.map((bookmark) => (
          <div key={bookmark.id} className="p-4 hover:bg-gray-50">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                {/* Title */}
                <a
                  href={bookmark.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-base font-medium text-gray-900 hover:text-primary-600 block truncate"
                >
                  {bookmark.title || '(제목 없음)'}
                </a>
                
                {/* URL */}
                <p className="text-sm text-gray-500 truncate mt-1">
                  {getDomain(bookmark.url)}
                </p>

                {/* Tags */}
                {bookmark.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {bookmark.tags.slice(0, 5).map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                      >
                        #{tag}
                      </span>
                    ))}
                    {bookmark.tags.length > 5 && (
                      <span className="text-xs text-gray-500">
                        +{bookmark.tags.length - 5}
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="ml-4 flex flex-col items-end">
                <span className="text-xs text-gray-500">
                  {formatDate(bookmark.created_at)}
                </span>
                <a
                  href={bookmark.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 text-primary-600 hover:text-primary-700 text-sm"
                >
                  열기 →
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
