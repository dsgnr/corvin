'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  api,
  VideoList,
  Video,
  Profile,
  ActiveTasks,
  VideoListStats,
  Task,
  HistoryEntry,
  ListTasksPaginatedResponse,
  ListHistoryPaginatedResponse,
  VideosPaginatedResponse,
  getListTasksStreamUrl,
  getListHistoryStreamUrl,
  getListVideosStreamUrl,
} from '@/lib/api'
import { useProgress } from '@/lib/ProgressContext'
import { useVideoListStream } from '@/lib/useVideoListStream'
import { useEventSource } from '@/lib/useEventSource'
import { formatDuration } from '@/lib/utils'
import { linkifyText } from '@/lib/text'
import {
  ArrowLeft,
  Download,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ExternalLink,
  CircleSlash,
  Edit2,
  Search,
  ChevronDown,
  ChevronUp,
  ListVideo,
  Film,
  Plus,
  Trash2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'
import { DownloadProgress } from '@/components/DownloadProgress'
import { ListForm } from '@/components/ListForm'
import { Select } from '@/components/Select'
import { TaskStatusIcon } from '@/components/TaskStatusIcon'
import { VideoLabels } from '@/components/VideoLabels'
import { ExtractorIcon } from '@/components/ExtractorIcon'
import { PAGE_SIZE_OPTIONS, DEFAULT_PAGE_SIZE } from '@/lib/utils'

export default function ListDetailPage() {
  const params = useParams()
  const listId = Number(params.id)
  const [list, setList] = useState<VideoList | null>(null)
  const [videos, setVideos] = useState<Video[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [syncStatus, setSyncStatus] = useState<'idle' | 'queued' | 'running'>('idle')
  const [downloadingPending, setDownloadingPending] = useState(false)
  const [retryingFailed, setRetryingFailed] = useState(false)
  const [downloadingIds, setDownloadingIds] = useState<Set<number>>(new Set())
  const [queuedDownloadIds, setQueuedDownloadIds] = useState<Set<number>>(new Set())
  const [runningDownloadIds, setRunningDownloadIds] = useState<Set<number>>(new Set())
  const [filter, setFilter] = useState<'all' | 'pending' | 'downloaded' | 'failed' | 'blacklisted'>(
    'all'
  )
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalVideos, setTotalVideos] = useState<number | null>(null)
  const [descriptionExpanded, setDescriptionExpanded] = useState(false)

  // Tasks state (server-side pagination)
  const [tasks, setTasks] = useState<Task[]>([])
  const [tasksTotal, setTasksTotal] = useState(0)
  const [tasksTotalPages, setTasksTotalPages] = useState(1)
  const [tasksSearch, setTasksSearch] = useState('')
  const [debouncedTasksSearch, setDebouncedTasksSearch] = useState('')
  const [tasksPageSize, setTasksPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [tasksCurrentPage, setTasksCurrentPage] = useState(1)

  // History state (server-side pagination)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyTotalPages, setHistoryTotalPages] = useState(1)
  const [historySearch, setHistorySearch] = useState('')
  const [debouncedHistorySearch, setDebouncedHistorySearch] = useState('')
  const [historyPageSize, setHistoryPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1)

  // Stats from SSE (accurate totals)
  const [serverStats, setServerStats] = useState<VideoListStats | null>(null)

  // Handle SSE stream updates (stats + change notifications)
  const handleStreamUpdate = useCallback(
    (stats: VideoListStats, tasks: ActiveTasks) => {
      // Update server stats
      setServerStats(stats)

      const isRunning = tasks.sync.running.includes(listId)
      const isQueued = tasks.sync.pending.includes(listId)

      if (isRunning) {
        setSyncStatus('running')
      } else if (isQueued) {
        setSyncStatus('queued')
      } else {
        setSyncStatus('idle')
      }

      setRunningDownloadIds(new Set(tasks.download.running))
      setQueuedDownloadIds(new Set(tasks.download.pending))
    },
    [listId]
  )

  // Use SSE stream for real-time stats and change notifications
  useVideoListStream(listId, !loading, handleStreamUpdate)

  // SSE stream URLs for tasks and history (with pagination params)
  const tasksStreamUrl = useMemo(
    () =>
      loading
        ? null
        : getListTasksStreamUrl(listId, {
            page: tasksCurrentPage,
            pageSize: tasksPageSize,
            search: debouncedTasksSearch || undefined,
          }),
    [listId, loading, tasksCurrentPage, tasksPageSize, debouncedTasksSearch]
  )
  const historyStreamUrl = useMemo(
    () =>
      loading
        ? null
        : getListHistoryStreamUrl(listId, {
            page: historyCurrentPage,
            pageSize: historyPageSize,
            search: debouncedHistorySearch || undefined,
          }),
    [listId, loading, historyCurrentPage, historyPageSize, debouncedHistorySearch]
  )

  const handleTasksMessage = useCallback((data: ListTasksPaginatedResponse) => {
    setTasks(data.tasks)
    setTasksTotal(data.total)
    setTasksTotalPages(data.total_pages)
  }, [])
  const handleTasksError = useCallback(() => {
    api
      .getListTasksPaginated(listId, {
        page: tasksCurrentPage,
        pageSize: tasksPageSize,
        search: debouncedTasksSearch || undefined,
      })
      .then((data) => {
        setTasks(data.tasks)
        setTasksTotal(data.total)
        setTasksTotalPages(data.total_pages)
      })
      .catch(console.error)
  }, [listId, tasksCurrentPage, tasksPageSize, debouncedTasksSearch])

  const handleHistoryMessage = useCallback((data: ListHistoryPaginatedResponse) => {
    setHistory(data.entries)
    setHistoryTotal(data.total)
    setHistoryTotalPages(data.total_pages)
  }, [])
  const handleHistoryError = useCallback(() => {
    api
      .getListHistoryPaginated(listId, {
        page: historyCurrentPage,
        pageSize: historyPageSize,
        search: debouncedHistorySearch || undefined,
      })
      .then((data) => {
        setHistory(data.entries)
        setHistoryTotal(data.total)
        setHistoryTotalPages(data.total_pages)
      })
      .catch(console.error)
  }, [listId, historyCurrentPage, historyPageSize, debouncedHistorySearch])

  useEventSource(tasksStreamUrl, handleTasksMessage, handleTasksError)
  useEventSource(historyStreamUrl, handleHistoryMessage, handleHistoryError)

  // SSE stream URL for videos (with pagination and filter params)
  const videosStreamUrl = useMemo(() => {
    if (loading || !list) return null
    // For disabled lists (auto_download=false), pending filter should show nothing
    if (filter === 'pending' && !list.auto_download) return null

    const downloaded = filter === 'downloaded' ? true : filter === 'pending' ? false : undefined
    const failed = filter === 'failed' ? true : undefined
    const blacklisted = filter === 'blacklisted' ? true : undefined

    return getListVideosStreamUrl(listId, {
      page: currentPage,
      pageSize,
      downloaded: filter === 'failed' || filter === 'blacklisted' ? undefined : downloaded,
      failed,
      blacklisted,
      search: debouncedSearch || undefined,
    })
  }, [listId, loading, list, filter, currentPage, pageSize, debouncedSearch])

  const handleVideosMessage = useCallback((data: VideosPaginatedResponse) => {
    setVideos(data.videos)
    setTotalPages(data.total_pages)
    setTotalVideos(data.total)
  }, [])

  const handleVideosError = useCallback(() => {
    // Fallback to regular fetch on SSE error
    if (!list) return
    if (filter === 'pending' && !list.auto_download) {
      setVideos([])
      setTotalPages(1)
      setTotalVideos(0)
      return
    }

    const downloaded = filter === 'downloaded' ? true : filter === 'pending' ? false : undefined
    const failed = filter === 'failed' ? true : undefined
    const blacklisted = filter === 'blacklisted' ? true : undefined

    api
      .getVideosPaginated(listId, {
        page: currentPage,
        pageSize,
        downloaded: filter === 'failed' || filter === 'blacklisted' ? undefined : downloaded,
        failed,
        blacklisted,
        search: debouncedSearch || undefined,
      })
      .then((response) => {
        setVideos(response.videos)
        setTotalPages(response.total_pages)
        setTotalVideos(response.total)
      })
      .catch(console.error)
  }, [listId, list, filter, currentPage, pageSize, debouncedSearch])

  useEventSource(videosStreamUrl, handleVideosMessage, handleVideosError)

  // Handle pending filter for non-auto-download lists
  useEffect(() => {
    if (filter === 'pending' && list && !list.auto_download) {
      setVideos([])
      setTotalPages(1)
      setTotalVideos(0)
    }
  }, [filter, list])

  const fetchData = useCallback(async () => {
    try {
      const [listData, profilesData, statsResponse] = await Promise.all([
        api.getList(listId),
        api.getProfiles(),
        api.getVideoListStats(listId),
      ])
      setList(listData)
      setProfiles(profilesData)
      setServerStats(statsResponse.stats)
    } catch (err) {
      console.error('Failed to fetch list:', err)
    } finally {
      setLoading(false)
    }
  }, [listId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  // Reset to page 1 when search changes
  useEffect(() => {
    if (debouncedSearch) {
      setCurrentPage(1)
    }
  }, [debouncedSearch])

  const handleSync = async () => {
    setSyncStatus('queued')
    try {
      await api.triggerListSync(listId)
    } catch (err) {
      console.error('Failed to sync:', err)
      setSyncStatus('idle')
    }
  }

  const handleDownloadPending = async () => {
    const pendingVideos = videos.filter((v) => !v.downloaded && !v.error_message)
    if (pendingVideos.length === 0) return

    setDownloadingPending(true)
    try {
      await Promise.all(pendingVideos.map((v) => api.triggerVideoDownload(v.id)))
    } catch (err) {
      console.error('Failed to queue downloads:', err)
    } finally {
      setDownloadingPending(false)
    }
  }

  const handleRetryFailed = async () => {
    const failedVideos = videos.filter((v) => !!v.error_message)
    if (failedVideos.length === 0) return

    setRetryingFailed(true)
    try {
      await Promise.all(failedVideos.map((v) => api.retryVideo(v.id)))
      setTimeout(fetchData, 1000)
    } catch (err) {
      console.error('Failed to retry videos:', err)
    } finally {
      setRetryingFailed(false)
    }
  }

  const handleSave = async (data: Partial<VideoList>) => {
    try {
      const updated = await api.updateList(listId, data)
      setList(updated)
      setEditing(false)
    } catch (err) {
      console.error('Failed to save:', err)
    }
  }

  const handleDownload = async (videoId: number) => {
    setDownloadingIds((prev) => new Set(prev).add(videoId))
    try {
      await api.triggerVideoDownload(videoId)
      setQueuedDownloadIds((prev) => new Set(prev).add(videoId))
    } catch (err) {
      console.error('Failed to queue download:', err)
    } finally {
      setDownloadingIds((prev) => {
        const next = new Set(prev)
        next.delete(videoId)
        return next
      })
    }
  }

  // Reset to page 1 when filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [filter])

  // Debounce tasks search and reset page
  useEffect(() => {
    const timer = setTimeout(() => {
      if (tasksSearch !== debouncedTasksSearch) {
        setDebouncedTasksSearch(tasksSearch)
        setTasksCurrentPage(1)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [tasksSearch, debouncedTasksSearch])

  // Debounce history search and reset page
  useEffect(() => {
    const timer = setTimeout(() => {
      if (historySearch !== debouncedHistorySearch) {
        setDebouncedHistorySearch(historySearch)
        setHistoryCurrentPage(1)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [historySearch, debouncedHistorySearch])

  // Use server stats - show loading placeholder until available
  const statsLoading = !serverStats
  const stats = serverStats || { total: 0, downloaded: 0, pending: 0, failed: 0, blacklisted: 0 }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  if (!list) {
    return (
      <div className="p-6">
        <p className="text-[var(--error)]">List not found</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Link
          href="/lists"
          className="self-start rounded-md p-2 transition-colors hover:bg-[var(--card)]"
        >
          <ArrowLeft size={20} />
        </Link>
        <div className="flex flex-1 items-center gap-3 sm:gap-4">
          {list.thumbnail && (
            <img
              src={list.thumbnail}
              alt={list.name}
              className="h-12 w-12 rounded-lg object-cover sm:h-16 sm:w-16"
              referrerPolicy="no-referrer"
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <ExtractorIcon extractor={list.extractor} size="lg" />
              <h1 className="truncate text-xl font-semibold sm:text-2xl">{list.name}</h1>
            </div>
            <a
              href={list.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--foreground)] sm:text-sm"
            >
              <span className="truncate">{list.url}</span>
              <ExternalLink size={12} className="shrink-0" />
            </a>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm transition-colors hover:bg-[var(--card-hover)] sm:py-1.5"
          >
            <Edit2 size={14} />
            <span className="hidden sm:inline">Edit</span>
          </button>
          <button
            onClick={handleSync}
            disabled={syncStatus !== 'idle'}
            className={clsx(
              'flex items-center gap-1.5 rounded-md px-3 py-2 text-sm transition-colors disabled:opacity-50 sm:py-1.5',
              syncStatus === 'queued'
                ? 'bg-[var(--warning)] text-black'
                : 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]'
            )}
          >
            {syncStatus === 'running' ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : syncStatus === 'queued' ? (
              <Clock size={14} />
            ) : (
              <RefreshCw size={14} />
            )}
            <span className="hidden sm:inline">
              {syncStatus === 'running'
                ? 'Syncing'
                : syncStatus === 'queued'
                  ? 'Sync Queued'
                  : 'Sync'}
            </span>
          </button>
          {stats.pending > 0 && (
            <button
              onClick={handleDownloadPending}
              disabled={downloadingPending}
              className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm transition-colors hover:bg-[var(--card-hover)] disabled:opacity-50 sm:py-1.5"
            >
              {downloadingPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Download size={14} />
              )}
              <span className="hidden sm:inline">
                Download {list?.auto_download ? 'Pending' : 'All'}
              </span>
            </button>
          )}
          {stats.failed > 0 && (
            <button
              onClick={handleRetryFailed}
              disabled={retryingFailed}
              className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm transition-colors hover:bg-[var(--card-hover)] disabled:opacity-50 sm:py-1.5"
            >
              {retryingFailed ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              <span className="hidden sm:inline">Retry Failed</span>
            </button>
          )}
        </div>
      </div>

      {/* Edit Form */}
      {editing && (
        <ListForm
          list={list}
          profiles={profiles}
          onSave={handleSave}
          onCancel={() => setEditing(false)}
        />
      )}

      {/* Description and Tags */}
      {(list.description || (list.tags && list.tags.length > 0)) && (
        <div className="space-y-4 rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          {list.description && (
            <div>
              <h3 className="mb-2 text-sm font-medium">Description</h3>
              <div className="relative">
                <div
                  className={clsx(
                    'prose prose-sm prose-invert max-w-none overflow-hidden text-sm whitespace-pre-line text-[var(--muted)] transition-all [&_a]:text-[var(--accent)] [&_a]:underline',
                    !descriptionExpanded && 'max-h-[3em]'
                  )}
                  dangerouslySetInnerHTML={{ __html: linkifyText(list.description) }}
                />
                {list.description.split('\n').length > 3 || list.description.length > 300 ? (
                  <button
                    onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                    className="mt-2 flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
                  >
                    {descriptionExpanded ? (
                      <>
                        <ChevronUp size={14} />
                        Show less
                      </>
                    ) : (
                      <>
                        <ChevronDown size={14} />
                        Show more
                      </>
                    )}
                  </button>
                ) : null}
              </div>
            </div>
          )}
          {list.tags && list.tags.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-medium">Tags</h3>
              <div className="flex flex-wrap gap-1.5">
                {list.tags.map((tag, i) => (
                  <span
                    key={i}
                    className="rounded bg-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5">
        <button
          onClick={() => setFilter('all')}
          className={clsx(
            'rounded-lg border p-3 text-left transition-colors',
            filter === 'all'
              ? 'border-[var(--accent)] bg-[var(--accent)]/10'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold">
            {statsLoading ? (
              <span className="inline-block h-7 w-12 animate-pulse rounded bg-[var(--border)]" />
            ) : (
              stats.total
            )}
          </p>
          <p className="text-xs text-[var(--muted)]">Total found</p>
        </button>
        <button
          onClick={() => setFilter('downloaded')}
          className={clsx(
            'rounded-lg border p-3 text-left transition-colors',
            filter === 'downloaded'
              ? 'border-[var(--success)] bg-[var(--success)]/10'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold text-[var(--success)]">
            {statsLoading ? (
              <span className="inline-block h-7 w-12 animate-pulse rounded bg-[var(--border)]" />
            ) : (
              stats.downloaded
            )}
          </p>
          <p className="text-xs text-[var(--muted)]">Downloaded</p>
        </button>
        <button
          onClick={() => setFilter('pending')}
          className={clsx(
            'rounded-lg border p-3 text-left transition-colors',
            filter === 'pending'
              ? 'border-[var(--warning)] bg-[var(--warning)]/10'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted)]'
          )}
        >
          <p
            className={clsx(
              'text-2xl font-semibold',
              list?.auto_download ? 'text-[var(--warning)]' : 'text-[var(--muted)]'
            )}
          >
            {statsLoading ? (
              <span className="inline-block h-7 w-12 animate-pulse rounded bg-[var(--border)]" />
            ) : list?.auto_download ? (
              stats.pending
            ) : (
              0
            )}
          </p>
          <p className="text-xs text-[var(--muted)]">
            {list?.auto_download ? 'Pending' : 'Not queued (manual)'}
          </p>
        </button>
        <button
          onClick={() => setFilter('blacklisted')}
          className={clsx(
            'rounded-lg border p-3 text-left transition-colors',
            filter === 'blacklisted'
              ? 'border-[var(--muted)] bg-[var(--muted)]/10'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold text-[var(--muted)]">
            {statsLoading ? (
              <span className="inline-block h-7 w-12 animate-pulse rounded bg-[var(--border)]" />
            ) : (
              stats.blacklisted
            )}
          </p>
          <p className="text-xs text-[var(--muted)]">Blacklisted</p>
        </button>
        <button
          onClick={() => setFilter('failed')}
          className={clsx(
            'rounded-lg border p-3 text-left transition-colors',
            filter === 'failed'
              ? 'border-[var(--error)] bg-[var(--error)]/10'
              : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold text-[var(--error)]">
            {statsLoading ? (
              <span className="inline-block h-7 w-12 animate-pulse rounded bg-[var(--border)]" />
            ) : (
              stats.failed
            )}
          </p>
          <p className="text-xs text-[var(--muted)]">Failed</p>
        </button>
      </div>

      {/* Videos */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4">
          <h2 className="font-medium">
            Videos (
            {debouncedSearch ? (
              // When searching, show the count from the paginated response
              (totalVideos ?? (
                <span className="inline-block h-4 w-8 animate-pulse rounded bg-[var(--border)] align-middle" />
              ))
            ) : statsLoading ? (
              <span className="inline-block h-4 w-8 animate-pulse rounded bg-[var(--border)] align-middle" />
            ) : filter === 'all' ? (
              stats.total
            ) : filter === 'downloaded' ? (
              stats.downloaded
            ) : filter === 'pending' ? (
              list?.auto_download ? (
                stats.pending
              ) : (
                0
              )
            ) : filter === 'blacklisted' ? (
              stats.blacklisted
            ) : filter === 'failed' ? (
              stats.failed
            ) : (
              stats.total
            )}
            )
          </h2>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="relative w-full sm:w-auto">
              <Search
                size={14}
                className="absolute top-1/2 left-3 -translate-y-1/2 text-[var(--muted)]"
              />
              <input
                type="text"
                placeholder="Search videos..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] py-1.5 pr-3 pl-8 text-sm focus:border-[var(--accent)] focus:outline-none sm:w-64"
              />
            </div>
            <Select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setCurrentPage(1)
              }}
              fullWidth={false}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size} rows
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {videos.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">No videos found</p>
          ) : (
            videos.map((video: Video) => (
              <VideoRow
                key={video.video_id}
                video={video}
                downloading={downloadingIds.has(video.id)}
                downloadQueued={queuedDownloadIds.has(video.id)}
                downloadRunning={runningDownloadIds.has(video.id)}
                onDownload={() => handleDownload(video.id)}
                autoDownload={list?.auto_download ?? true}
              />
            ))
          )}
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
      </div>

      {/* Tasks */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4">
          <h2 className="font-medium">Tasks ({tasksTotal})</h2>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="relative w-full sm:w-auto">
              <Search
                size={14}
                className="absolute top-1/2 left-3 -translate-y-1/2 text-[var(--muted)]"
              />
              <input
                type="text"
                placeholder="Search tasks..."
                value={tasksSearch}
                onChange={(e) => setTasksSearch(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] py-1.5 pr-3 pl-8 text-sm focus:border-[var(--accent)] focus:outline-none sm:w-64"
              />
            </div>
            <Select
              value={tasksPageSize}
              onChange={(e) => {
                setTasksPageSize(Number(e.target.value))
                setTasksCurrentPage(1)
              }}
              fullWidth={false}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size} rows
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {tasks.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">No tasks found</p>
          ) : (
            tasks.map((task) => <TaskRow key={task.id} task={task} />)
          )}
        </div>
        <Pagination
          currentPage={tasksCurrentPage}
          totalPages={tasksTotalPages}
          onPageChange={setTasksCurrentPage}
        />
      </div>

      {/* History */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4">
          <h2 className="font-medium">History ({historyTotal})</h2>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="relative w-full sm:w-auto">
              <Search
                size={14}
                className="absolute top-1/2 left-3 -translate-y-1/2 text-[var(--muted)]"
              />
              <input
                type="text"
                placeholder="Search history..."
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] py-1.5 pr-3 pl-8 text-sm focus:border-[var(--accent)] focus:outline-none sm:w-64"
              />
            </div>
            <Select
              value={historyPageSize}
              onChange={(e) => {
                setHistoryPageSize(Number(e.target.value))
                setHistoryCurrentPage(1)
              }}
              fullWidth={false}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size} rows
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {history.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">No history entries</p>
          ) : (
            history.map((entry) => <HistoryRow key={entry.id} entry={entry} />)
          )}
        </div>
        <Pagination
          currentPage={historyCurrentPage}
          totalPages={historyTotalPages}
          onPageChange={setHistoryCurrentPage}
        />
      </div>
    </div>
  )
}

function VideoRow({
  video,
  downloading,
  downloadQueued,
  downloadRunning,
  onDownload,
  autoDownload,
}: {
  video: Video
  downloading: boolean
  downloadQueued: boolean
  downloadRunning: boolean
  onDownload: () => void
  autoDownload: boolean
}) {
  const hasLabels = video.downloaded && video.labels && Object.keys(video.labels).length > 0
  const progress = useProgress(video.id)

  const renderStatusIcon = () => {
    const wrapperClass = 'rounded-md bg-[var(--card-hover)] p-2'

    if (video.downloaded) {
      return (
        <span className={wrapperClass}>
          <CheckCircle size={18} className="text-[var(--success)]" />
        </span>
      )
    }
    if (video.blacklisted) {
      return (
        <span
          title={video.error_message || 'Blacklisted - excluded from auto-download'}
          className={wrapperClass}
        >
          <CircleSlash size={18} className="text-[var(--muted)]" />
        </span>
      )
    }
    if (video.error_message) {
      return (
        <span className={wrapperClass}>
          <XCircle size={18} className="text-[var(--error)]" />
        </span>
      )
    }
    if (downloadRunning) {
      return (
        <span title="Downloading..." className={wrapperClass}>
          <Loader2 size={18} className="animate-spin text-[var(--accent)]" />
        </span>
      )
    }
    if (downloadQueued) {
      return (
        <span title="Download queued" className={wrapperClass}>
          <Clock size={18} className="text-[var(--warning)]" />
        </span>
      )
    }
    if (autoDownload) {
      return (
        <span className={wrapperClass}>
          <Clock size={18} className="text-[var(--warning)]" />
        </span>
      )
    }
    return (
      <span title="Not pending - auto download is disabled for this list" className={wrapperClass}>
        <CircleSlash size={18} className="text-[var(--muted)] opacity-50" />
      </span>
    )
  }

  const renderDownloadButton = () => {
    if (video.downloaded || downloadRunning || downloadQueued) return null

    return (
      <button
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDownload()
        }}
        disabled={downloading}
        className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
        title="Download"
      >
        {downloading ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
      </button>
    )
  }

  const renderActions = () => (
    <div className="flex shrink-0 items-center gap-2">
      {renderStatusIcon()}
      {renderDownloadButton()}
    </div>
  )

  return (
    <div className="p-3 sm:p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
        <Link href={`/videos/${video.id}`} className="shrink-0">
          {video.thumbnail ? (
            <img
              src={video.thumbnail}
              alt=""
              className="aspect-video w-full rounded bg-[var(--border)] object-cover transition-opacity hover:opacity-80 sm:h-14 sm:w-24"
            />
          ) : (
            <div className="aspect-video w-full rounded bg-[var(--border)] sm:h-14 sm:w-24" />
          )}
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <Link
              href={`/videos/${video.id}`}
              className="line-clamp-2 flex-1 text-sm font-medium transition-colors hover:text-[var(--accent)]"
            >
              {video.title}
            </Link>
            {/* Mobile: status and download inline with title */}
            <div className="sm:hidden">{renderActions()}</div>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
            <span className="rounded bg-[var(--accent)]/20 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent)]">
              {video.media_type}
            </span>
            {video.blacklisted && (
              <span className="rounded bg-[var(--muted)]/20 px-1.5 py-0.5 text-[10px] font-medium text-[var(--muted)]">
                blacklisted
              </span>
            )}
            <span>{formatDuration(video.duration)}</span>
            {video.upload_date && (
              <span className="hidden sm:inline">
                {new Date(video.upload_date).toLocaleString(undefined, {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </span>
            )}
            {hasLabels && <VideoLabels labels={video.labels} compact />}
          </div>
          {progress &&
            progress.status !== 'completed' &&
            progress.status !== 'error' &&
            !video.error_message && (
              <div className="mt-2 max-w-sm">
                <DownloadProgress progress={progress} />
              </div>
            )}
          {video.error_message && !video.blacklisted && (
            <p className="mt-1 line-clamp-1 text-xs text-[var(--error)]">{video.error_message}</p>
          )}
          {video.blacklisted && video.error_message && (
            <p className="mt-1 line-clamp-1 text-xs text-[var(--muted)]">{video.error_message}</p>
          )}
        </div>
        {/* Desktop: status and download on right */}
        <div className="hidden sm:block">{renderActions()}</div>
      </div>
    </div>
  )
}

function TaskRow({ task }: { task: Task }) {
  return (
    <div className="flex items-center gap-3 p-4">
      <TaskStatusIcon status={task.status} size={16} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {task.task_type === 'sync' ? 'Sync' : 'Download'} •{' '}
          {task.entity_name || `#${task.entity_id}`}
        </p>
        <p className="text-xs text-[var(--muted)]">
          {new Date(task.created_at).toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
          })}
          {task.completed_at &&
            ` • Completed ${new Date(task.completed_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`}
        </p>
        {task.error && (
          <p className="mt-1 line-clamp-1 text-xs text-[var(--error)]">{task.error}</p>
        )}
      </div>
      <span
        className={clsx(
          'rounded px-2 py-1 text-xs',
          task.status === 'completed' && 'bg-[var(--success)]/20 text-[var(--success)]',
          task.status === 'failed' && 'bg-[var(--error)]/20 text-[var(--error)]',
          task.status === 'running' && 'bg-[var(--accent)]/20 text-[var(--accent)]',
          task.status === 'pending' && 'bg-[var(--warning)]/20 text-[var(--warning)]',
          task.status === 'paused' && 'bg-[var(--muted)]/20 text-[var(--muted)]',
          task.status === 'cancelled' && 'bg-[var(--border)] text-[var(--muted)]'
        )}
      >
        {task.status === 'pending' ? 'queued' : task.status}
      </span>
    </div>
  )
}

function HistoryRow({ entry }: { entry: HistoryEntry }) {
  const actionIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
    list_created: Plus,
    list_updated: Edit2,
    list_deleted: Trash2,
    list_synced: RefreshCw,
    video_discovered: Film,
    video_download_started: Download,
    video_download_completed: Download,
    video_download_failed: Download,
    video_retry: RefreshCw,
  }

  const entityIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
    list: ListVideo,
    video: Film,
  }

  const formatAction = (action: string) => {
    return action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }

  const getDetails = (details: Record<string, unknown> | string): Record<string, unknown> => {
    if (typeof details === 'string') {
      try {
        return JSON.parse(details)
      } catch {
        return {}
      }
    }
    return details || {}
  }

  const ActionIcon = actionIcons[entry.action] || RefreshCw
  const EntityIcon = entityIcons[entry.entity_type] || Film
  const details = getDetails(entry.details)
  const isError = entry.action.includes('failed')
  const isSuccess = entry.action.includes('completed') || entry.action.includes('created')

  return (
    <div className="flex items-start gap-3 p-4">
      <div
        className={clsx(
          'rounded-md p-2',
          isError && 'bg-[var(--error)]/10',
          isSuccess && 'bg-[var(--success)]/10',
          !isError && !isSuccess && 'bg-[var(--border)]'
        )}
      >
        <ActionIcon
          size={14}
          className={clsx(
            isError && 'text-[var(--error)]',
            isSuccess && 'text-[var(--success)]',
            !isError && !isSuccess && 'text-[var(--muted)]'
          )}
        />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{formatAction(entry.action)}</span>
          <span className="flex items-center gap-1 text-xs text-[var(--muted)]">
            <EntityIcon size={12} />
            {entry.entity_type}
            {entry.entity_id && ` #${entry.entity_id}`}
          </span>
        </div>
        {Object.keys(details).length > 0 && (
          <p className="mt-1 text-xs text-[var(--muted)]">
            {'name' in details && (
              <span className="pr-1 after:ml-1 after:content-['•']">{String(details.name)}</span>
            )}
            {'title' in details && <span>{String(details.title)}</span>}
          </p>
        )}
        <p className="mt-1 text-xs text-[var(--muted)]">
          {new Date(entry.created_at).toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
          })}
        </p>
      </div>
    </div>
  )
}
