function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE
  }
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:5000/api`
  }
  // Server-side: use Docker service name
  return process.env.INTERNAL_API_BASE || 'http://backend:5000/api'
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
  getProfileOptions: () => request<ProfileOptions>('/profiles/options'),
  createProfile: (data: Partial<Profile>) =>
    request<Profile>('/profiles', { method: 'POST', body: JSON.stringify(data) }),
  updateProfile: (id: number, data: Partial<Profile>) =>
    request<Profile>(`/profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProfile: (id: number) => request<void>(`/profiles/${id}`, { method: 'DELETE' }),

  // Lists
  getLists: () => request<VideoList[]>('/lists'),
  getList: (id: number) => request<VideoList>(`/lists/${id}`),
  createList: (data: Partial<VideoList>) =>
    request<VideoList>('/lists', { method: 'POST', body: JSON.stringify(data) }),
  createListsBulk: (data: BulkListCreate) =>
    request<BulkListResponse>('/lists/bulk', { method: 'POST', body: JSON.stringify(data) }),
  updateList: (id: number, data: Partial<VideoList>) =>
    request<VideoList>(`/lists/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteList: (id: number) => request<void>(`/lists/${id}`, { method: 'DELETE' }),

  // Download Schedules
  getSchedules: () => request<DownloadSchedule[]>('/schedules'),
  getScheduleStatus: () => request<ScheduleStatus>('/schedules/status'),
  createSchedule: (data: ScheduleCreate) =>
    request<DownloadSchedule>('/schedules', { method: 'POST', body: JSON.stringify(data) }),
  updateSchedule: (id: number, data: Partial<ScheduleCreate>) =>
    request<DownloadSchedule>(`/schedules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSchedule: (id: number) => request<void>(`/schedules/${id}`, { method: 'DELETE' }),

  // Videos
  getVideoListStats: (listId: number) =>
    request<{ stats: VideoListStats; tasks: ActiveTasks }>(`/lists/${listId}/videos/stats`),
  getVideosPaginated: (
    listId: number,
    params: {
      page: number
      pageSize: number
      downloaded?: boolean
      failed?: boolean
      blacklisted?: boolean
      search?: string
    }
  ): Promise<VideosPaginatedResponse> => {
    const query = new URLSearchParams()
    query.set('page', String(params.page))
    query.set('page_size', String(params.pageSize))
    if (params.downloaded !== undefined) query.set('downloaded', String(params.downloaded))
    if (params.failed !== undefined) query.set('failed', String(params.failed))
    if (params.blacklisted !== undefined) query.set('blacklisted', String(params.blacklisted))
    if (params.search) query.set('search', params.search)
    return request<VideosPaginatedResponse>(`/lists/${listId}/videos?${query}`)
  },
  getVideosByIds: (listId: number, ids: number[]) =>
    request<Video[]>(`/lists/${listId}/videos/by-ids?ids=${ids.join(',')}`),
  getVideo: (id: number) => request<Video>(`/videos/${id}`),
  retryVideo: (id: number) =>
    request<{ message: string; video: Video }>(`/videos/${id}/retry`, { method: 'POST' }),
  toggleVideoBlacklist: (id: number) =>
    request<Video>(`/videos/${id}/blacklist`, { method: 'POST' }),

  // Tasks
  getTasksPaginated: (params: {
    page: number
    pageSize: number
    type?: string
    status?: string
    search?: string
  }) => {
    const query = new URLSearchParams()
    query.set('page', String(params.page))
    query.set('page_size', String(params.pageSize))
    if (params.type) query.set('type', params.type)
    if (params.status) query.set('status', params.status)
    if (params.search) query.set('search', params.search)
    return request<TasksPaginatedResponse>(`/tasks?${query}`)
  },
  getTaskStats: () => request<TaskStats>('/tasks/stats'),
  triggerListSync: (listId: number) =>
    request<Task>(`/tasks/sync/list/${listId}`, { method: 'POST' }),
  triggerAllSyncs: () =>
    request<{ queued: number; skipped: number }>('/tasks/sync/all', { method: 'POST' }),
  triggerVideoDownload: (videoId: number) =>
    request<Task>(`/tasks/download/video/${videoId}`, { method: 'POST' }),
  triggerPendingDownloads: () =>
    request<{ queued: number; skipped: number }>('/tasks/download/pending', { method: 'POST' }),
  retryTask: (id: number) => request<Task>(`/tasks/${id}/retry`, { method: 'POST' }),
  pauseTask: (id: number) => request<Task>(`/tasks/${id}/pause`, { method: 'POST' }),
  resumeTask: (id: number) => request<Task>(`/tasks/${id}/resume`, { method: 'POST' }),
  cancelTask: (id: number) => request<Task>(`/tasks/${id}/cancel`, { method: 'POST' }),
  pauseAllTasks: () => request<BulkTaskResult>('/tasks/pause/all', { method: 'POST' }),
  resumeAllTasks: () => request<BulkTaskResult>('/tasks/resume/all', { method: 'POST' }),
  cancelAllTasks: () => request<BulkTaskResult>('/tasks/cancel/all', { method: 'POST' }),
  retryFailedTasks: () => request<BulkTaskResult>('/tasks/retry/failed', { method: 'POST' }),
  pauseSyncTasks: () => request<BulkTaskResult>('/tasks/pause/sync', { method: 'POST' }),
  resumeSyncTasks: () => request<BulkTaskResult>('/tasks/resume/sync', { method: 'POST' }),
  pauseDownloadTasks: () => request<BulkTaskResult>('/tasks/pause/download', { method: 'POST' }),
  resumeDownloadTasks: () => request<BulkTaskResult>('/tasks/resume/download', { method: 'POST' }),

  // History
  getHistory: (params?: { limit?: number; entity_type?: string; action?: string }) => {
    const query = new URLSearchParams()
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.entity_type) query.set('entity_type', params.entity_type)
    if (params?.action) query.set('action', params.action)
    return request<HistoryEntry[]>(`/history?${query}`)
  },
  getHistoryPaginated: (params: {
    page: number
    pageSize: number
    entity_type?: string
    action?: string
    search?: string
  }): Promise<HistoryPaginatedResponse> => {
    const query = new URLSearchParams()
    query.set('page', String(params.page))
    query.set('page_size', String(params.pageSize))
    if (params.entity_type) query.set('entity_type', params.entity_type)
    if (params.action) query.set('action', params.action)
    if (params.search) query.set('search', params.search)
    return request<HistoryPaginatedResponse>(`/history?${query}`)
  },

  // List-specific tasks and history (paginated)
  getListTasksPaginated: (
    listId: number,
    params: { page: number; pageSize: number; search?: string }
  ) => {
    const query = new URLSearchParams()
    query.set('page', String(params.page))
    query.set('page_size', String(params.pageSize))
    if (params.search) query.set('search', params.search)
    return request<ListTasksPaginatedResponse>(`/lists/${listId}/tasks?${query}`)
  },
  getListHistoryPaginated: (
    listId: number,
    params: { page: number; pageSize: number; search?: string }
  ) => {
    const query = new URLSearchParams()
    query.set('page', String(params.page))
    query.set('page_size', String(params.pageSize))
    if (params.search) query.set('search', params.search)
    return request<ListHistoryPaginatedResponse>(`/lists/${listId}/history?${query}`)
  },
}

// Types
export interface Profile {
  id: number
  name: string
  embed_metadata: boolean
  embed_thumbnail: boolean
  include_shorts: boolean
  extra_args: string
  download_subtitles: boolean
  embed_subtitles: boolean
  auto_generated_subtitles: boolean
  subtitle_languages: string
  audio_track_language: string
  output_template: string
  output_format: string
  sponsorblock_behaviour: string
  sponsorblock_categories: string[]
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
  blacklist_regex: string | null
  last_synced: string | null
  next_sync_at: string | null
  description: string | null
  thumbnail: string | null
  tags: string[]
  deleting?: boolean
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
  was_live?: boolean
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
  media_type: string | null
  labels: VideoLabels
  list_id: number
  list?: VideoList
  downloaded: boolean
  blacklisted: boolean
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
  schedule_paused?: boolean
  worker?: {
    running_sync: number
    running_download: number
    max_sync_workers: number
    max_download_workers: number
    paused: boolean
    sync_paused: boolean
    download_paused: boolean
  }
}

export interface ActiveTasks {
  sync: { pending: number[]; running: number[] }
  download: { pending: number[]; running: number[] }
}

export interface BulkTaskResult {
  affected: number
  skipped: number
}

export interface HistoryEntry {
  id: number
  action: string
  entity_type: string
  entity_id: number | null
  details: Record<string, unknown>
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

export interface VideosPaginatedResponse {
  videos: Video[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface VideoListStats {
  total: number
  downloaded: number
  failed: number
  pending: number
  blacklisted: number
  newest_id: number | null
  last_updated: string | null
}

export interface VideoListStatsUpdate {
  stats: VideoListStats
  tasks: ActiveTasks
  changed_video_ids: number[]
}

export interface HistoryPaginatedResponse {
  entries: HistoryEntry[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ListTasksPaginatedResponse {
  tasks: Task[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ListHistoryPaginatedResponse {
  entries: HistoryEntry[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TasksPaginatedResponse {
  tasks: Task[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export function getProgressStreamUrl(): string {
  return `${getApiBase()}/progress`
}

export function getVideoListStreamUrl(listId: number): string {
  return `${getApiBase()}/lists/${listId}/videos/stats`
}

export function getTasksStreamUrl(params?: {
  type?: string
  status?: string
  search?: string
  page?: number
  pageSize?: number
}): string {
  const query = new URLSearchParams()
  if (params?.type) query.set('type', params.type)
  if (params?.status) query.set('status', params.status)
  if (params?.search) query.set('search', params.search)
  if (params?.page) query.set('page', String(params.page))
  if (params?.pageSize) query.set('page_size', String(params.pageSize))
  const queryStr = query.toString()
  return `${getApiBase()}/tasks${queryStr ? `?${queryStr}` : ''}`
}

export function getHistoryStreamUrl(params?: {
  entity_type?: string
  action?: string
  search?: string
  page?: number
  page_size?: number
}): string {
  const query = new URLSearchParams()
  if (params?.entity_type) query.set('entity_type', params.entity_type)
  if (params?.action) query.set('action', params.action)
  if (params?.search) query.set('search', params.search)
  if (params?.page) query.set('page', String(params.page))
  if (params?.page_size) query.set('page_size', String(params.page_size))
  const queryStr = query.toString()
  return `${getApiBase()}/history${queryStr ? `?${queryStr}` : ''}`
}

export function getTaskStatsStreamUrl(): string {
  return `${getApiBase()}/tasks/stats`
}

export function getListTasksStreamUrl(
  listId: number,
  params?: { page?: number; pageSize?: number; search?: string }
): string {
  const query = new URLSearchParams()
  if (params?.page) query.set('page', String(params.page))
  if (params?.pageSize) query.set('page_size', String(params.pageSize))
  if (params?.search) query.set('search', params.search)
  const queryStr = query.toString()
  return `${getApiBase()}/lists/${listId}/tasks${queryStr ? `?${queryStr}` : ''}`
}

export function getListHistoryStreamUrl(
  listId: number,
  params?: { page?: number; pageSize?: number; search?: string }
): string {
  const query = new URLSearchParams()
  if (params?.page) query.set('page', String(params.page))
  if (params?.pageSize) query.set('page_size', String(params.pageSize))
  if (params?.search) query.set('search', params.search)
  const queryStr = query.toString()
  return `${getApiBase()}/lists/${listId}/history${queryStr ? `?${queryStr}` : ''}`
}

export function getListsStreamUrl(): string {
  return `${getApiBase()}/lists`
}

export function getListVideosStreamUrl(
  listId: number,
  params?: {
    page?: number
    pageSize?: number
    downloaded?: boolean
    failed?: boolean
    blacklisted?: boolean
    search?: string
  }
): string {
  const query = new URLSearchParams()
  if (params?.page) query.set('page', String(params.page))
  if (params?.pageSize) query.set('page_size', String(params.pageSize))
  if (params?.downloaded !== undefined) query.set('downloaded', String(params.downloaded))
  if (params?.failed !== undefined) query.set('failed', String(params.failed))
  if (params?.blacklisted !== undefined) query.set('blacklisted', String(params.blacklisted))
  if (params?.search) query.set('search', params.search)
  const queryStr = query.toString()
  return `${getApiBase()}/lists/${listId}/videos${queryStr ? `?${queryStr}` : ''}`
}

export interface SponsorBlockOptions {
  behaviours: string[]
  categories: string[]
  category_labels: Record<string, string>
}

export interface DownloadSchedule {
  id: number
  name: string
  enabled: boolean
  days_of_week: string[]
  start_time: string
  end_time: string
  created_at: string
  updated_at: string
}

export interface ScheduleCreate {
  name: string
  enabled?: boolean
  days_of_week: string[]
  start_time: string
  end_time: string
}

export interface BulkListCreate {
  urls: string[]
  profile_id: number
  list_type: string
  sync_frequency: string
  enabled: boolean
  auto_download: boolean
}

export interface BulkListResponse {
  message: string
  count: number
}

export interface ScheduleStatus {
  downloads_allowed: boolean
  active_schedules: number
}

export interface ProfileDefaults {
  output_template: string
  embed_metadata: boolean
  embed_thumbnail: boolean
  include_shorts: boolean
  download_subtitles: boolean
  embed_subtitles: boolean
  auto_generated_subtitles: boolean
  subtitle_languages: string
  audio_track_language: string
  output_format: string
  sponsorblock_behaviour: string
  sponsorblock_categories: string[]
  extra_args: string
}

export interface ProfileOptions {
  defaults: ProfileDefaults
  sponsorblock: SponsorBlockOptions
  output_formats: string[]
}
