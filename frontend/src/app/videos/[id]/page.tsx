'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api, Video, Task, getTasksStreamUrl } from '@/lib/api'
import { useProgress } from '@/lib/ProgressContext'
import { useEventSource } from '@/lib/useEventSource'
import { DownloadProgress } from '@/components/DownloadProgress'
import { VideoLabels } from '@/components/VideoLabels'
import { ExtractorIcon } from '@/components/ExtractorIcon'
import { TaskStatusIcon } from '@/components/TaskStatusIcon'
import { formatDuration } from '@/lib/utils'
import { linkifyText } from '@/lib/text'
import {
  ArrowLeft,
  Download,
  ExternalLink,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RotateCcw,
  CircleSlash,
  Calendar,
  Timer,
  Hash,
  FolderOpen,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { clsx } from 'clsx'

export default function VideoDetailPage() {
  const params = useParams()
  const videoId = Number(params.id)
  const [video, setVideo] = useState<Video | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [togglingBlacklist, setTogglingBlacklist] = useState(false)
  const [downloadQueued, setDownloadQueued] = useState(false)
  const [downloadRunning, setDownloadRunning] = useState(false)
  const [descriptionExpanded, setDescriptionExpanded] = useState(false)

  // Tasks state
  const [tasks, setTasks] = useState<Task[]>([])
  const [tasksTotal, setTasksTotal] = useState(0)
  const [tasksPage, setTasksPage] = useState(1)
  const [tasksTotalPages, setTasksTotalPages] = useState(1)
  const tasksPageSize = 5

  // Track if we initiated a download locally to prevent SSE from clearing state prematurely
  const localDownloadInitiated = useRef(false)

  // Derive list from video
  const list = video?.list ?? null

  // Real-time download progress
  const progress = useProgress(videoId)

  // Derive download state from progress - single source of truth for active downloads
  const isActiveDownload =
    progress && progress.status !== 'completed' && progress.status !== 'error'

  // Clear local flag once progress is active
  useEffect(() => {
    if (isActiveDownload) {
      localDownloadInitiated.current = false
    }
  }, [isActiveDownload])

  // SSE stream for download task status (for queued state before progress starts)
  const handleTasksMessage = useCallback(
    (data: { tasks: Task[] }) => {
      const tasks = data.tasks || []
      const isQueued = tasks.some((t) => t.status === 'pending' && t.entity_id === videoId)
      const isRunning = tasks.some((t) => t.status === 'running' && t.entity_id === videoId)

      // Don't let SSE clear our local state if we just initiated a download
      if (!isQueued && !isRunning && localDownloadInitiated.current) {
        return
      }

      setDownloadQueued(isQueued)
      setDownloadRunning(isRunning)
    },
    [videoId]
  )

  useEventSource(getTasksStreamUrl({ type: 'download' }), handleTasksMessage)

  useEffect(() => {
    const fetchVideo = async () => {
      try {
        const data = await api.getVideo(videoId)
        setVideo(data)
      } catch (err) {
        console.error('Failed to fetch video:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchVideo()
  }, [videoId])

  // Fetch tasks for this video
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const data = await api.getVideoTasksPaginated(videoId, {
          page: tasksPage,
          pageSize: tasksPageSize,
        })
        setTasks(data.tasks)
        setTasksTotal(data.total)
        setTasksTotalPages(data.total_pages)
      } catch (err) {
        console.error('Failed to fetch tasks:', err)
      }
    }

    fetchTasks()
  }, [videoId, tasksPage])

  // Refresh video data and tasks when download completes or fails
  useEffect(() => {
    if (progress?.status === 'completed' || progress?.status === 'error') {
      const refetchData = async () => {
        try {
          const [videoData, tasksData] = await Promise.all([
            api.getVideo(videoId),
            api.getVideoTasksPaginated(videoId, { page: tasksPage, pageSize: tasksPageSize }),
          ])
          setVideo(videoData)
          setTasks(tasksData.tasks)
          setTasksTotal(tasksData.total)
          setTasksTotalPages(tasksData.total_pages)
          // Clear task states since download finished
          setDownloadQueued(false)
          setDownloadRunning(false)
        } catch (err) {
          console.error('Failed to fetch data:', err)
        }
      }
      setTimeout(refetchData, 1000)
    }
  }, [progress?.status, videoId, tasksPage])

  const handleDownload = async () => {
    if (!video) return
    setDownloading(true)
    try {
      await api.triggerVideoDownload(video.id)
      localDownloadInitiated.current = true
      setDownloadQueued(true)
    } catch (err) {
      console.error('Failed to trigger download:', err)
    } finally {
      setDownloading(false)
    }
  }

  const handleRetry = async () => {
    if (!video) return
    setRetrying(true)
    try {
      await api.retryVideo(video.id)
      // Optimistically update state - clear error and mark as queued
      localDownloadInitiated.current = true
      setVideo({ ...video, error_message: null })
      setDownloadQueued(true)
    } catch (err) {
      console.error('Failed to retry:', err)
    } finally {
      setRetrying(false)
    }
  }

  const handleToggleBlacklist = async () => {
    if (!video) return
    setTogglingBlacklist(true)
    try {
      const data = await api.toggleVideoBlacklist(video.id)
      setVideo(data)
    } catch (err) {
      console.error('Failed to toggle blacklist:', err)
    } finally {
      setTogglingBlacklist(false)
    }
  }

  // Determine status - prefer progress state for active downloads
  const getStatus = () => {
    if (video?.downloaded) return 'downloaded'
    if (video?.blacklisted) return 'blacklisted'
    if (video?.error_message) return 'failed'
    // Use progress state as primary source during downloads
    if (isActiveDownload) {
      if (progress?.status === 'downloading' || progress?.status === 'processing')
        return 'downloading'
      return 'queued'
    }
    if (downloadRunning) return 'downloading'
    if (downloadQueued) return 'queued'
    if (list?.auto_download) return 'pending'
    return 'manual'
  }

  const status = getStatus()

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  if (!video) {
    return (
      <div className="p-6">
        <p className="text-[var(--error)]">Video not found</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Channel Header */}
      <div className="flex items-center gap-3 sm:gap-4">
        <Link
          href={`/lists/${video.list_id}`}
          className="rounded-md p-2 transition-colors hover:bg-[var(--card)]"
        >
          <ArrowLeft size={20} />
        </Link>
        <div className="flex flex-1 items-center gap-3 sm:gap-4">
          {list?.thumbnail && (
            <Link href={`/lists/${video.list_id}`} className="hidden sm:block">
              <img
                src={list.thumbnail}
                alt={list.name}
                className="h-12 w-12 rounded-lg object-cover transition-opacity hover:opacity-80"
                referrerPolicy="no-referrer"
              />
            </Link>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <ExtractorIcon extractor={list?.extractor} size="md" />
              <Link
                href={`/lists/${video.list_id}`}
                className="truncate font-medium transition-colors hover:text-[var(--accent)]"
              >
                {list?.name || 'Loading...'}
              </Link>
            </div>
            {list?.url && (
              <a
                href={list.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hidden items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--foreground)] sm:flex"
              >
                {list.url.length > 50 ? list.url.slice(0, 50) + '...' : list.url}
                <ExternalLink size={10} />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Left Column - Thumbnail & Actions */}
        <div className="space-y-4 lg:col-span-2">
          {/* Thumbnail with status overlay */}
          <div className="group relative">
            {video.thumbnail ? (
              <img
                src={video.thumbnail}
                alt={video.title}
                className="aspect-video w-full rounded-lg bg-[var(--card)] object-cover"
              />
            ) : (
              <div className="flex aspect-video w-full items-center justify-center rounded-lg bg-[var(--card)]">
                <span className="text-[var(--muted)]">No thumbnail</span>
              </div>
            )}
            {/* Duration badge */}
            {video.duration && (
              <div className="absolute right-2 bottom-2 rounded bg-black/80 px-1.5 py-0.5 text-xs text-white">
                {formatDuration(video.duration)}
              </div>
            )}
            {/* Status overlay */}
            <div
              className={clsx(
                'absolute top-2 left-2 flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium shadow-lg',
                status === 'downloaded' && 'bg-[var(--success)] text-white',
                status === 'blacklisted' && 'bg-[var(--muted)] text-white',
                status === 'failed' && 'bg-[var(--error)] text-white',
                status === 'downloading' && 'bg-[var(--accent)] text-white',
                status === 'queued' && 'bg-[var(--warning)] text-black',
                status === 'pending' && 'bg-[var(--warning)] text-black',
                status === 'manual' && 'border border-[var(--border)] bg-black/80 text-white'
              )}
            >
              {status === 'downloaded' && (
                <>
                  <CheckCircle size={12} /> Downloaded
                </>
              )}
              {status === 'blacklisted' && (
                <>
                  <CircleSlash size={12} /> Blacklisted
                </>
              )}
              {status === 'failed' && (
                <>
                  <XCircle size={12} /> Failed
                </>
              )}
              {status === 'downloading' && (
                <>
                  <Loader2 size={12} className="animate-spin" /> Downloading
                </>
              )}
              {status === 'queued' && (
                <>
                  <Clock size={12} /> Queued
                </>
              )}
              {status === 'pending' && (
                <>
                  <Clock size={12} /> Pending
                </>
              )}
              {status === 'manual' && (
                <>
                  <CircleSlash size={12} /> Not queued
                </>
              )}
            </div>
          </div>

          {/* Download Progress */}
          {(isActiveDownload || downloadQueued) && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
              <DownloadProgress
                progress={
                  progress ||
                  ({
                    status: 'queued',
                    percent: 0,
                    video_id: videoId,
                    speed: null,
                    eta: null,
                    error: null,
                  } as const)
                }
              />
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2">
            {!video.downloaded && !video.error_message && !downloadRunning && !downloadQueued && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-2 text-sm text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50 sm:py-1.5"
              >
                {downloading ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Download size={14} />
                )}
                Download
              </button>
            )}
            {downloadQueued && !downloadRunning && !video.downloaded && (
              <div className="flex items-center gap-1.5 rounded-md bg-[var(--warning)] px-3 py-2 text-sm text-black sm:py-1.5">
                <Clock size={14} />
                Queued
              </div>
            )}
            {downloadRunning && !video.downloaded && (
              <div className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-2 text-sm text-white sm:py-1.5">
                <Loader2 size={14} className="animate-spin" />
                Downloading
              </div>
            )}
            {video.error_message && !video.blacklisted && (
              <button
                onClick={handleRetry}
                disabled={retrying}
                className="flex items-center gap-1.5 rounded-md bg-[var(--warning)] px-3 py-2 text-sm text-black transition-colors hover:opacity-90 disabled:opacity-50 sm:py-1.5"
              >
                {retrying ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <RotateCcw size={14} />
                )}
                Retry
              </button>
            )}
            {!video.downloaded && (
              <button
                onClick={handleToggleBlacklist}
                disabled={togglingBlacklist}
                className={clsx(
                  'flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors disabled:opacity-50 sm:py-1.5',
                  video.blacklisted
                    ? 'border-[var(--muted)] bg-[var(--muted)]/10 text-[var(--muted)] hover:bg-[var(--muted)]/20'
                    : 'border-[var(--border)] bg-[var(--card)] hover:bg-[var(--card-hover)]'
                )}
                title={video.blacklisted ? 'Remove from blacklist' : 'Add to blacklist'}
              >
                {togglingBlacklist ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <CircleSlash size={14} />
                )}
                {video.blacklisted ? 'Unblacklist' : 'Blacklist'}
              </button>
            )}
            <a
              href={video.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm transition-colors hover:bg-[var(--card-hover)] sm:py-1.5"
            >
              <ExternalLink size={14} />
              YouTube
            </a>
          </div>

          {/* Error Message */}
          {video.error_message && !video.blacklisted && !isActiveDownload && !downloadQueued && (
            <div className="rounded-lg border border-[var(--error)]/30 bg-[var(--error)]/10 p-4">
              <div className="mb-2 flex items-center gap-2 font-medium text-[var(--error)]">
                <XCircle size={16} />
                Download Failed
              </div>
              <p className="text-sm text-[var(--error)]">{video.error_message}</p>
            </div>
          )}

          {/* Blacklist Reason */}
          {video.blacklisted && video.error_message && (
            <div className="rounded-lg border border-[var(--muted)]/30 bg-[var(--muted)]/10 p-4">
              <div className="mb-2 flex items-center gap-2 font-medium text-[var(--muted)]">
                <CircleSlash size={16} />
                Blacklisted
              </div>
              <p className="text-sm text-[var(--muted)]">{video.error_message}</p>
            </div>
          )}

          {/* Download Path */}
          {video.download_path && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm text-[var(--muted)]">
                <FolderOpen size={14} />
                Download Path
              </div>
              <p className="font-mono text-sm break-all text-[var(--foreground)]">
                {video.download_path}
              </p>
            </div>
          )}
        </div>

        {/* Right Column - Video Info */}
        <div className="space-y-4 lg:col-span-3">
          {/* Title & Meta */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
            <h1 className="mb-4 text-xl leading-tight font-semibold">{video.title}</h1>

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="rounded bg-[var(--accent)]/20 px-2 py-1 text-xs font-medium text-[var(--accent)] uppercase">
                {video.media_type}
              </span>
              {video.blacklisted && (
                <span className="rounded bg-[var(--muted)]/20 px-2 py-1 text-xs font-medium text-[var(--muted)]">
                  blacklisted
                </span>
              )}
              {video.duration && (
                <span className="flex items-center gap-1.5 rounded bg-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]">
                  <Timer size={12} />
                  {formatDuration(video.duration)}
                </span>
              )}
              {video.upload_date && (
                <span className="flex items-center gap-1.5 rounded bg-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]">
                  <Calendar size={12} />
                  {new Date(video.upload_date).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
              )}
              <span className="flex items-center gap-1.5 rounded bg-[var(--border)] px-2 py-1 font-mono text-xs text-[var(--muted)]">
                <Hash size={12} />
                {video.video_id}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 border-t border-[var(--border)] pt-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="mb-1 text-xs text-[var(--muted)]">Added</dt>
                <dd>
                  {new Date(video.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </dd>
              </div>
              <div>
                <dt className="mb-1 text-xs text-[var(--muted)]">Updated</dt>
                <dd>
                  {new Date(video.updated_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </dd>
              </div>
              {video.retry_count > 0 && (
                <div>
                  <dt className="mb-1 flex items-center gap-1 text-xs text-[var(--muted)]">
                    <RefreshCw size={10} /> Retries
                  </dt>
                  <dd>{video.retry_count}</dd>
                </div>
              )}
            </div>
          </div>

          {/* Media Info Labels */}
          {video.downloaded && video.labels && Object.keys(video.labels).length > 0 && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
              <h2 className="mb-4 font-medium">Media Info</h2>
              <VideoLabels labels={video.labels} />
            </div>
          )}

          {/* Description - Collapsible */}
          {video.description && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
              <h2 className="mb-3 font-medium">Description</h2>
              <div
                className={clsx(
                  'text-sm leading-relaxed break-words whitespace-pre-wrap text-[var(--muted)] [&_a]:text-[var(--accent)] [&_a]:underline [&_a]:hover:opacity-80',
                  !descriptionExpanded && 'line-clamp-3'
                )}
                dangerouslySetInnerHTML={{ __html: linkifyText(video.description) }}
              />
              {video.description.split('\n').length > 3 || video.description.length > 300 ? (
                <button
                  onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                  className="mt-2 flex items-center gap-1 text-sm text-[var(--accent)] hover:opacity-80"
                >
                  {descriptionExpanded ? (
                    <>
                      Show less <ChevronUp size={14} />
                    </>
                  ) : (
                    <>
                      Show more <ChevronDown size={14} />
                    </>
                  )}
                </button>
              ) : null}
            </div>
          )}

          {/* Tasks Table */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
            <div className="border-b border-[var(--border)] p-4">
              <h2 className="font-medium">Tasks ({tasksTotal})</h2>
            </div>
            <div className="divide-y divide-[var(--border)]">
              {tasks.length === 0 ? (
                <p className="p-4 text-sm text-[var(--muted)]">No tasks found</p>
              ) : (
                tasks.map((task) => (
                  <div key={task.id} className="flex items-center gap-3 p-4">
                    <TaskStatusIcon status={task.status} size={16} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">Download</p>
                      <p className="text-xs text-[var(--muted)]">
                        {new Date(task.created_at).toLocaleString(undefined, {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })}
                        {task.completed_at &&
                          ` • Completed ${new Date(task.completed_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`}
                      </p>
                      {task.error && (
                        <p className="mt-1 line-clamp-1 text-xs text-[var(--error)]">
                          {task.error}
                        </p>
                      )}
                    </div>
                    <span
                      className={clsx(
                        'rounded px-2 py-1 text-xs',
                        task.status === 'completed' &&
                          'bg-[var(--success)]/20 text-[var(--success)]',
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
                ))
              )}
            </div>
            {tasksTotalPages > 1 && (
              <div className="flex items-center justify-center gap-2 border-t border-[var(--border)] p-3">
                <button
                  onClick={() => setTasksPage((p) => Math.max(1, p - 1))}
                  disabled={tasksPage === 1}
                  className="rounded px-2 py-1 text-xs transition-colors hover:bg-[var(--card-hover)] disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-xs text-[var(--muted)]">
                  {tasksPage} / {tasksTotalPages}
                </span>
                <button
                  onClick={() => setTasksPage((p) => Math.min(tasksTotalPages, p + 1))}
                  disabled={tasksPage === tasksTotalPages}
                  className="rounded px-2 py-1 text-xs transition-colors hover:bg-[var(--card-hover)] disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
