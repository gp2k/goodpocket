import { useState, FormEvent } from 'react'
import { bookmarksApi, Bookmark } from '../lib/api'

interface BookmarkFormProps {
  onBookmarkCreated: (bookmark: Bookmark) => void
}

export default function BookmarkForm({ onBookmarkCreated }: BookmarkFormProps) {
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showTitleInput, setShowTitleInput] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    setError(null)

    try {
      const bookmark = await bookmarksApi.create(
        url.trim(),
        title.trim() || undefined
      )
      onBookmarkCreated(bookmark)
      setUrl('')
      setTitle('')
      setShowTitleInput(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : '북마크 저장 중 오류가 발생했습니다')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4">
      <div className="flex gap-3">
        <div className="flex-1">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            required
            disabled={loading}
          />
        </div>
        <button
          type="button"
          onClick={() => setShowTitleInput(!showTitleInput)}
          className="px-3 py-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md"
          title="제목 직접 입력"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </button>
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="px-6 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
        >
          {loading ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              저장 중...
            </>
          ) : (
            '저장'
          )}
        </button>
      </div>

      {/* Optional title input */}
      {showTitleInput && (
        <div className="mt-3">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="제목 (선택사항 - 비워두면 자동 추출)"
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            disabled={loading}
          />
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="mt-3 text-red-600 text-sm bg-red-50 p-3 rounded-md">
          {error}
        </div>
      )}
    </form>
  )
}
