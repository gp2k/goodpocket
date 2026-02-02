import { Bookmark } from '../lib/api'

interface BookmarkListProps {
  bookmarks: Bookmark[]
  loading: boolean
  onSelect: (bookmark: Bookmark) => void
  selectedId?: string
}

export default function BookmarkList({
  bookmarks,
  loading,
  onSelect,
  selectedId,
}: BookmarkListProps) {
  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (bookmarks.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg shadow">
        <div className="text-gray-400 text-5xl mb-4">🔖</div>
        <h3 className="text-lg font-medium text-gray-900">북마크가 없습니다</h3>
        <p className="text-gray-600 mt-2">위 입력창에 URL을 입력해서 첫 북마크를 저장하세요!</p>
      </div>
    )
  }

  const getStatusBadge = (status: Bookmark['status']) => {
    switch (status) {
      case 'embedded':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            완료
          </span>
        )
      case 'pending_embedding':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
            처리 중
          </span>
        )
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
            실패
          </span>
        )
    }
  }

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
    <div className="bg-white rounded-lg shadow divide-y">
      {bookmarks.map((bookmark) => (
        <div
          key={bookmark.id}
          onClick={() => onSelect(bookmark)}
          className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
            selectedId === bookmark.id ? 'bg-primary-50' : ''
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              {/* Title */}
              <h3 className="text-base font-medium text-gray-900 truncate">
                {bookmark.title || '(제목 없음)'}
              </h3>
              
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

              {/* Cluster label */}
              {bookmark.cluster_label && (
                <div className="mt-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-700">
                    📁 {bookmark.cluster_label}
                  </span>
                </div>
              )}
            </div>

            <div className="ml-4 flex flex-col items-end space-y-2">
              {getStatusBadge(bookmark.status)}
              <span className="text-xs text-gray-500">
                {formatDate(bookmark.created_at)}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
