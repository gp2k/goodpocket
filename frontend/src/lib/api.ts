import { supabase } from './supabase'

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) {
    throw new Error('Not authenticated')
  }
  return {
    'Authorization': `Bearer ${session.access_token}`,
    'Content-Type': 'application/json',
  }
}

async function api<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body } = options
  const headers = await getAuthHeader()

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// Types
export interface Bookmark {
  id: string
  url: string
  canonical_url?: string
  title?: string
  summary?: string
  tags: string[]
  status: 'pending_embedding' | 'embedded' | 'failed'
  cluster_id?: number
  cluster_label?: string
  created_at: string
  updated_at?: string
  embedded_at?: string
}

export interface BookmarkListResponse {
  items: Bookmark[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface Cluster {
  cluster_id: number
  label?: string
  size: number
  updated_at: string
}

export interface ClusterListResponse {
  items: Cluster[]
  total: number
}

export interface ClusterDetail {
  cluster_id: number
  label?: string
  size: number
  bookmarks: Bookmark[]
}

// API functions
export const bookmarksApi = {
  create: (url: string, title?: string) =>
    api<Bookmark>('/api/bookmarks', {
      method: 'POST',
      body: { url, title },
    }),

  list: (page = 1, pageSize = 20) =>
    api<BookmarkListResponse>(`/api/bookmarks?page=${page}&page_size=${pageSize}`),

  get: (id: string) =>
    api<Bookmark>(`/api/bookmarks/${id}`),

  delete: (id: string) =>
    api<{ message: string }>(`/api/bookmarks/${id}`, { method: 'DELETE' }),
}

export const clustersApi = {
  list: () =>
    api<ClusterListResponse>('/api/clusters'),

  get: (clusterId: number) =>
    api<ClusterDetail>(`/api/clusters/${clusterId}`),
}

// Jobs API - for admin operations (use VITE_BATCH_SECRET in production)
const BATCH_SECRET = import.meta.env.VITE_BATCH_SECRET || ''

export const jobsApi = {
  runBatch: async () => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/batch`, {
      method: 'POST',
      headers: {
        'X-Batch-Secret': BATCH_SECRET,
        'Content-Type': 'application/json',
      },
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<{ message: string }>
  },

  regenerateTags: async () => {
    const response = await fetch(`${API_BASE_URL}/api/jobs/regenerate-tags`, {
      method: 'POST',
      headers: {
        'X-Batch-Secret': BATCH_SECRET,
        'Content-Type': 'application/json',
      },
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }
    return response.json() as Promise<{ message: string }>
  },
}
