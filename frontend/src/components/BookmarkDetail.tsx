import { useState } from 'react'
import { Bookmark, bookmarksApi } from '../lib/api'

/** Hide or normalize meaningless cluster labels like "Cluster 47". */
function clusterLabelDisplay(label: string | null | undefined): string {
  if (!label?.trim()) return ''
  if (/^cluster\s*_?\s*\d+$/i.test(label.trim())) return '그룹'
  return label
}

interface BookmarkDetailProps {
  bookmark: Bookmark
  onClose: () => void
  onDelete: (id: string) => void
}

export default function BookmarkDetail({
  bookmark,
  onClose,
  onDelete,
}: BookmarkDetailProps) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDelete = async () => {
    if (!confirm('이 북마크를 삭제하시겠습니까?')) return

    setDeleting(true)
    setError(null)

    try {
      await bookmarksApi.delete(bookmark.id)
      onDelete(bookmark.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '삭제 중 오류가 발생했습니다')
    } finally {
      setDeleting(false)
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-'
    const date = new Date(dateString)
    return date.toLocaleString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
        <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl">
          {/* Header */}
          <div className="bg-white px-6 pt-6 pb-4 border-b">
            <div className="flex items-start justify-between">
              <h3 className="text-lg font-semibold text-gray-900 pr-8">
                {bookmark.title || '(제목 없음)'}
              </h3>
              <button
                onClick={onClose}
                className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="bg-white px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
            {/* URL */}
            <div>
              <h4 className="text-sm font-medium text-gray-500">URL</h4>
              <a
                href={bookmark.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 hover:underline break-all"
              >
                {bookmark.url}
              </a>
            </div>

            {/* Summary */}
            {bookmark.summary && (
              <div>
                <h4 className="text-sm font-medium text-gray-500">요약</h4>
                <p className="text-gray-700 whitespace-pre-wrap">{bookmark.summary}</p>
              </div>
            )}

            {/* Tags */}
            {bookmark.tags.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">태그</h4>
                <div className="flex flex-wrap gap-2">
                  {bookmark.tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-700"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Cluster */}
            {clusterLabelDisplay(bookmark.cluster_label) && (
              <div>
                <h4 className="text-sm font-medium text-gray-500">클러스터</h4>
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary-100 text-primary-700">
                  📁 {clusterLabelDisplay(bookmark.cluster_label)}
                </span>
              </div>
            )}

            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
              <div>
                <h4 className="text-sm font-medium text-gray-500">생성일</h4>
                <p className="text-gray-700">{formatDate(bookmark.created_at)}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500">임베딩 완료일</h4>
                <p className="text-gray-700">{formatDate(bookmark.embedded_at)}</p>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="text-red-600 text-sm bg-red-50 p-3 rounded-md">
                {error}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-6 py-4 flex justify-between">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-4 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md disabled:opacity-50"
            >
              {deleting ? '삭제 중...' : '삭제'}
            </button>
            <a
              href={bookmark.url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
            >
              페이지 열기
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
