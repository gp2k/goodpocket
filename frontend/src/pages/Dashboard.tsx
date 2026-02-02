import { useState, useEffect } from 'react'
import { bookmarksApi, jobsApi, Bookmark } from '../lib/api'
import BookmarkForm from '../components/BookmarkForm'
import BookmarkList from '../components/BookmarkList'
import BookmarkDetail from '../components/BookmarkDetail'

export default function Dashboard() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [selectedBookmark, setSelectedBookmark] = useState<Bookmark | null>(null)
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchMessage, setBatchMessage] = useState<string | null>(null)

  const loadBookmarks = async (pageNum: number = 1) => {
    try {
      setLoading(true)
      setError(null)
      const response = await bookmarksApi.list(pageNum, 20)
      setBookmarks(response.items)
      setTotalPages(response.total_pages)
      setPage(pageNum)
    } catch (err) {
      setError(err instanceof Error ? err.message : '북마크를 불러오는 중 오류가 발생했습니다')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBookmarks()
  }, [])

  const handleBookmarkCreated = (bookmark: Bookmark) => {
    setBookmarks((prev) => [bookmark, ...prev])
  }

  const handleBookmarkDeleted = (id: string) => {
    setBookmarks((prev) => prev.filter((b) => b.id !== id))
    setSelectedBookmark(null)
  }

  const handleRunBatch = async () => {
    try {
      setBatchRunning(true)
      setBatchMessage(null)
      const result = await jobsApi.runBatch()
      setBatchMessage(result.message || '배치 작업이 시작되었습니다. 잠시 후 새로고침하세요.')
    } catch (err) {
      setBatchMessage(err instanceof Error ? err.message : '배치 작업 실행 중 오류가 발생했습니다')
    } finally {
      setBatchRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">내 북마크</h1>
          <p className="text-gray-600">URL을 저장하면 자동으로 태그가 생성됩니다</p>
        </div>
        <button
          onClick={handleRunBatch}
          disabled={batchRunning}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
        >
          {batchRunning ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>처리 중...</span>
            </>
          ) : (
            <span>클러스터링 실행</span>
          )}
        </button>
      </div>

      {/* Batch job message */}
      {batchMessage && (
        <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded-md">
          {batchMessage}
        </div>
      )}

      {/* Add bookmark form */}
      <BookmarkForm onBookmarkCreated={handleBookmarkCreated} />

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {/* Bookmarks list */}
      <BookmarkList
        bookmarks={bookmarks}
        loading={loading}
        onSelect={setSelectedBookmark}
        selectedId={selectedBookmark?.id}
      />

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center space-x-2">
          <button
            onClick={() => loadBookmarks(page - 1)}
            disabled={page <= 1}
            className="px-4 py-2 border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            이전
          </button>
          <span className="px-4 py-2 text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => loadBookmarks(page + 1)}
            disabled={page >= totalPages}
            className="px-4 py-2 border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            다음
          </button>
        </div>
      )}

      {/* Bookmark detail modal */}
      {selectedBookmark && (
        <BookmarkDetail
          bookmark={selectedBookmark}
          onClose={() => setSelectedBookmark(null)}
          onDelete={handleBookmarkDeleted}
        />
      )}
    </div>
  )
}
