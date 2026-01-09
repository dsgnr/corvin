function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE
  }
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:5000/api`
  }
  return 'http://localhost:5000/api'
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const apiBase = getApiBase()
  const res = await fetch(`${apiBase}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.message || `HTTP ${res.status}`)
  }

  if (res.status === 204) return null as T
  return res.json()
}

export const api = {
  // Profiles
  getProfiles: () => request<Profile[]>('/profiles'),
  getProfile: (id: number) => request<Profile>(`/profiles/${id}`),
  getProfileOptions: () => request<ProfileOptions>('/profiles/options'),
  createProfile: (data: Partial<Profile>) =>
    request<Profile>('/profiles', { method: 'POST', body: JSON.stringify(data) }),
  updateProfile: (id: number, data: Partial<Profile>) =>
    request<Profile>(`/profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProfile: (id: number) => request<void>(`/profiles/${id}`, { method: 'DELETE' }),

  // Lists
  getLists: () => request<VideoList[]>('/lists'),
  getList: (id: number, includeVideos = false) =>
    request<VideoList>(`/lists/${id}?include_videos=${includeVideos}`),
  createList: (data: Partial<VideoList>) =>
    request<VideoList>('/lists', { method: 'POST', body: JSON.stringify(data) }),
  updateList: (id: number, data: Partial<VideoList>) =>
    request<VideoList>(`/lists/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteList: (id: number) => request<void>(`/lists/${id}`, { method: 'DELETE' }),

  // Videos
  getVideos: (params?: { list_id?: number; downloaded?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.list_id) query.set('list_id', String(params.list_id))
    if (params?.downloaded !== undefined) query.set('downloaded', String(params.downloaded))
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.offset) query.set('offset', String(params.offset))
    return request<Video[]>(`/videos?${query}`)
  },
  getVideo: (id: number) => request<Video>(`/videos/${id}`),
  retryVideo: (id: number) =>
    request<{ message: string; video: Video }>(`/videos/${id}/retry`, { method: 'POST' }),

  // Tasks
  getTasks: (params?: { type?: string; status?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.type) query.set('type', params.type)
    if (params?.status) query.set('status', params.status)
    if (params?.limit) query.set('limit', String(params.limit))
    return request<Task[]>(`/tasks?${query}`)
  },
  getTask: (id: number) => request<Task>(`/tasks/${id}?include_logs=true`),
  getTaskStats: () => request<TaskStats>('/tasks/stats'),
  getActiveTasks: (params?: { list_id?: number }) => {
    const query = new URLSearchParams()
    if (params?.list_id) query.set('list_id', String(params.list_id))
    const queryStr = query.toString()
    return request<ActiveTasks>(`/tasks/active${queryStr ? `?${queryStr}` : ''}`)
  },
  triggerListSync: (listId: number) => request<Task>(`/tasks/sync/list/${listId}`, { method: 'POST' }),
  triggerAllSyncs: () => request<{ queued: number; skipped: number }>('/tasks/sync/all', { method: 'POST' }),
  triggerVideoDownload: (videoId: number) =>
    request<Task>(`/tasks/download/video/${videoId}`, { method: 'POST' }),
  triggerPendingDownloads: () =>
    request<{ queued: number; skipped: number }>('/tasks/download/pending', { method: 'POST' }),
  retryTask: (id: number) => request<Task>(`/tasks/${id}/retry`, { method: 'POST' }),

  // History
  getHistory: (params?: { limit?: number; entity_type?: string; action?: string }) => {
    const query = new URLSearchParams()
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.entity_type) query.set('entity_type', params.entity_type)
    if (params?.action) query.set('action', params.action)
    return request<HistoryEntry[]>(`/history?${query}`)
  },
}

// Types
export interface Profile {
  id: number
  name: string
  embed_metadata: boolean
  embed_thumbnail: boolean
  exclude_shorts: boolean
  extra_args: string
  download_subtitles: boolean
  embed_subtitles: boolean
  auto_generated_subtitles: boolean
  subtitle_languages: string
  audio_track_language: string
  output_template: string
  output_format: string
  sponsorblock_behavior: string
  sponsorblock_categories: string
  created_at: string
  updated_at: string
}

export interface VideoList {
  id: number
  name: string
  url: string
  list_type: string
  extractor: string | null
  profile_id: number
  from_date: string | null
  sync_frequency: string
  enabled: boolean
  auto_download: boolean
  last_synced: string | null
  next_sync_at: string | null
  description: string | null
  thumbnail: string | null
  tags: string[]
  created_at: string
  updated_at: string
  videos?: Video[]
}

export interface VideoLabels {
  format?: string
  acodec?: string
  resolution?: string
  audio_channels?: number
  dynamic_range?: string
  filesize_approx?: number
}

export interface Video {
  id: number
  video_id: string
  title: string
  url: string
  duration: number | null
  upload_date: string | null
  thumbnail: string | null
  description: string | null
  extractor: string | null
  labels: VideoLabels
  list_id: number
  downloaded: boolean
  download_path: string | null
  error_message: string | null
  retry_count: number
  created_at: string
  updated_at: string
}

export interface Task {
  id: number
  task_type: string
  entity_id: number
  entity_name: string | null
  status: string
  result: string | null
  error: string | null
  retry_count: number
  max_retries: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  logs?: TaskLog[]
}

export interface TaskLog {
  id: number
  attempt: number
  level: string
  message: string
  created_at: string
}

export interface TaskStats {
  pending_sync: number
  pending_download: number
  running_sync: number
  running_download: number
  worker?: Record<string, unknown>
}

export interface ActiveTasks {
  sync: { pending: number[]; running: number[] }
  download: { pending: number[]; running: number[] }
}

export interface HistoryEntry {
  id: number
  action: string
  entity_type: string
  entity_id: number | null
  details: string
  created_at: string
}

export interface DownloadProgress {
  video_id: number
  status: 'pending' | 'downloading' | 'processing' | 'completed' | 'error'
  percent: number
  speed: string | null
  eta: number | null
  error: string | null
}

export type ProgressMap = Record<number, DownloadProgress>

export function getProgressStreamUrl(): string {
  return `${getApiBase()}/progress/stream`
}

export interface SponsorBlockOptions {
  behaviors: string[]
  categories: string[]
  category_labels: Record<string, string>
}

export interface ProfileDefaults {
  output_template: string
  embed_metadata: boolean
  embed_thumbnail: boolean
  exclude_shorts: boolean
  download_subtitles: boolean
  embed_subtitles: boolean
  auto_generated_subtitles: boolean
  subtitle_languages: string
  audio_track_language: string
  output_format: string
  sponsorblock_behavior: string
  sponsorblock_categories: string
  extra_args: string
}

export interface ProfileOptions {
  defaults: ProfileDefaults
  sponsorblock: SponsorBlockOptions
  output_formats: string[]
}
