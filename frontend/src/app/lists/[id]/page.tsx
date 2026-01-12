'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api, VideoList, Video, Profile, ActiveTasks } from '@/lib/api'
import { useProgress } from '@/lib/ProgressContext'
import { useVideoListStream } from '@/lib/useVideoListStream'
import { formatDuration, formatFileSize } from '@/lib/utils'
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
} from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'
import { DownloadProgress } from '@/components/DownloadProgress'
import { ListForm } from '@/components/ListForm'

const PAGE_SIZE = 20

// Convert URLs in text to clickable links and escape HTML
function linkifyText(text: string): string {
  // First escape HTML to prevent XSS
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

  // Then convert URLs to links
  const urlRegex = /(https?:\/\/[^\s<]+)/g
  return escaped.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
}

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
  const [filter, setFilter] = useState<'all' | 'pending' | 'downloaded' | 'failed'>('all')
  const [search, setSearch] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  // Handle combined SSE stream updates (videos + tasks)
  const handleStreamUpdate = useCallback((videos: Video[], tasks: ActiveTasks) => {
    setVideos(videos)

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
  }, [listId])

  // Use SSE stream for real-time video and task updates
  useVideoListStream(listId, !loading, handleStreamUpdate)

  const fetchData = async () => {
    try {
      const [listData, profilesData] = await Promise.all([
        api.getList(listId),
        api.getProfiles(),
      ])
      setList(listData)
      setProfiles(profilesData)
    } catch (err) {
      console.error('Failed to fetch list:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [listId])

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
    const pendingVideos = videos.filter(v => !v.downloaded && !v.error_message)
    if (pendingVideos.length === 0) return

    setDownloadingPending(true)
    try {
      await Promise.all(pendingVideos.map(v => api.triggerVideoDownload(v.id)))
    } catch (err) {
      console.error('Failed to queue downloads:', err)
    } finally {
      setDownloadingPending(false)
    }
  }

  const handleRetryFailed = async () => {
    const failedVideos = videos.filter(v => !!v.error_message)
    if (failedVideos.length === 0) return

    setRetryingFailed(true)
    try {
      await Promise.all(failedVideos.map(v => api.retryVideo(v.id)))
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
    setDownloadingIds(prev => new Set(prev).add(videoId))
    try {
      await api.triggerVideoDownload(videoId)
      setQueuedDownloadIds(prev => new Set(prev).add(videoId))
    } catch (err) {
      console.error('Failed to queue download:', err)
    } finally {
      setDownloadingIds(prev => {
        const next = new Set(prev)
        next.delete(videoId)
        return next
      })
    }
  }

  const filteredVideos = videos
    .filter(v => {
      // Status filter
      if (filter === 'pending' && (v.downloaded || v.error_message)) return false
      if (filter === 'downloaded' && !v.downloaded) return false
      if (filter === 'failed' && !v.error_message) return false
      // Search filter
      if (search) {
        const searchLower = search.toLowerCase()
        return v.title?.toLowerCase().includes(searchLower)
      }
      return true
    })
    .sort((a, b) => {
      const dateA = a.upload_date ? new Date(a.upload_date).getTime() : 0
      const dateB = b.upload_date ? new Date(b.upload_date).getTime() : 0
      return dateB - dateA
    })

  const totalPages = Math.ceil(filteredVideos.length / PAGE_SIZE)
  const paginatedVideos = filteredVideos.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  // Reset to page 1 when filter or search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [filter, search])

  const stats = {
    total: videos.length,
    downloaded: videos.filter(v => v.downloaded).length,
    pending: videos.filter(v => !v.downloaded && !v.error_message).length,
    failed: videos.filter(v => !!v.error_message).length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
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
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/lists" className="p-2 rounded-md hover:bg-[var(--card)] transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1 flex items-center gap-4">
          {list.thumbnail && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={list.thumbnail}
              alt={list.name}
              className="w-16 h-16 rounded-lg object-cover"
              referrerPolicy="no-referrer"
            />
          )}
          <div>
            <div className="flex items-center gap-2">
              {list.extractor?.toLowerCase().includes('youtube') && (
                <svg viewBox="0 0 24 24" className="w-6 h-6 flex-shrink-0" fill="#FF0000">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
              )}
              <h1 className="text-2xl font-semibold">{list.name}</h1>
            </div>
            <a
              href={list.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] flex items-center gap-1"
            >
              {list.url}
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
        <button
          onClick={() => setEditing(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] rounded-md transition-colors"
        >
          <Edit2 size={14} />
          Edit
        </button>
        <button
          onClick={handleSync}
          disabled={syncStatus !== 'idle'}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-colors disabled:opacity-50',
            syncStatus === 'queued'
              ? 'bg-[var(--warning)] text-black'
              : 'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white'
          )}
        >
          {syncStatus === 'running' ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : syncStatus === 'queued' ? (
            <Clock size={14} />
          ) : (
            <RefreshCw size={14} />
          )}
          {syncStatus === 'running' ? 'Syncing' : syncStatus === 'queued' ? 'Sync Queued' : 'Sync'}
        </button>
        {stats.pending > 0 && (
          <button
            onClick={handleDownloadPending}
            disabled={downloadingPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] rounded-md transition-colors disabled:opacity-50"
          >
            {downloadingPending ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Download {list?.auto_download ? 'Pending' : 'All'}
          </button>
        )}
        {stats.failed > 0 && (
          <button
            onClick={handleRetryFailed}
            disabled={retryingFailed}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] rounded-md transition-colors disabled:opacity-50"
          >
            {retryingFailed ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Retry Failed
          </button>
        )}
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
        <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4 space-y-4">
          {list.description && (
            <div>
              <h3 className="text-sm font-medium mb-2">Description</h3>
              <div
                className="text-sm text-[var(--muted)] whitespace-pre-line prose prose-sm prose-invert max-w-none [&_a]:text-[var(--accent)] [&_a]:underline"
                dangerouslySetInnerHTML={{ __html: linkifyText(list.description) }}
              />
            </div>
          )}
          {list.tags && list.tags.length > 0 && (
            <div>
              <h3 className="text-sm font-medium mb-2">Tags</h3>
              <div className="flex flex-wrap gap-1.5">
                {list.tags.map((tag, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded bg-[var(--border)] text-[var(--muted)]">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <button
          onClick={() => setFilter('all')}
          className={clsx(
            'p-3 rounded-lg border transition-colors text-left',
            filter === 'all' ? 'bg-[var(--accent)]/10 border-[var(--accent)]' : 'bg-[var(--card)] border-[var(--border)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold">{stats.total}</p>
          <p className="text-xs text-[var(--muted)]">Total found</p>
        </button>
        <button
          onClick={() => setFilter('downloaded')}
          className={clsx(
            'p-3 rounded-lg border transition-colors text-left',
            filter === 'downloaded' ? 'bg-[var(--success)]/10 border-[var(--success)]' : 'bg-[var(--card)] border-[var(--border)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold text-[var(--success)]">{stats.downloaded}</p>
          <p className="text-xs text-[var(--muted)]">Downloaded</p>
        </button>
        <button
          onClick={() => setFilter('pending')}
          className={clsx(
            'p-3 rounded-lg border transition-colors text-left',
            filter === 'pending' ? 'bg-[var(--warning)]/10 border-[var(--warning)]' : 'bg-[var(--card)] border-[var(--border)] hover:border-[var(--muted)]'
          )}
        >
          <p className={clsx(
            'text-2xl font-semibold',
            list?.auto_download ? 'text-[var(--warning)]' : 'text-[var(--muted)]'
          )}>
            {list?.auto_download ? stats.pending : 0}
          </p>
          <p className="text-xs text-[var(--muted)]">
            {list?.auto_download ? 'Pending' : 'Not queued (manual)'}
          </p>
        </button>
        <button
          onClick={() => setFilter('failed')}
          className={clsx(
            'p-3 rounded-lg border transition-colors text-left',
            filter === 'failed' ? 'bg-[var(--error)]/10 border-[var(--error)]' : 'bg-[var(--card)] border-[var(--border)] hover:border-[var(--muted)]'
          )}
        >
          <p className="text-2xl font-semibold text-[var(--error)]">{stats.failed}</p>
          <p className="text-xs text-[var(--muted)]">Failed</p>
        </button>
      </div>

      {/* Videos */}
      <div className="bg-[var(--card)] rounded-lg border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between gap-4">
          <h2 className="font-medium">Videos ({filteredVideos.length})</h2>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search videos..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)] w-64"
            />
          </div>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {paginatedVideos.length === 0 ? (
            <p className="p-4 text-[var(--muted)] text-sm">No videos found</p>
          ) : (
            paginatedVideos.map(video => (
              <VideoRow
                key={video.id}
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
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
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
    if (video.downloaded) {
      return <CheckCircle size={18} className="text-[var(--success)]" />
    }
    if (video.error_message) {
      return <XCircle size={18} className="text-[var(--error)]" />
    }
    if (downloadRunning) {
      return (
        <span title="Downloading...">
          <Loader2 size={18} className="text-[var(--accent)] animate-spin" />
        </span>
      )
    }
    if (downloadQueued) {
      return (
        <span title="Download queued">
          <Clock size={18} className="text-[var(--warning)]" />
        </span>
      )
    }
    if (autoDownload) {
      return <Clock size={18} className="text-[var(--warning)]" />
    }
    return (
      <span title="Not pending - auto download is disabled for this list">
        <CircleSlash size={18} className="text-[var(--muted)] opacity-50" />
      </span>
    )
  }

  return (
    <div className="p-4 flex items-center gap-4">
      <Link href={`/videos/${video.id}`} className="shrink-0">
        {video.thumbnail ? (
          <img
            src={video.thumbnail}
            alt=""
            className="w-24 h-14 object-cover rounded bg-[var(--border)] hover:opacity-80 transition-opacity"
          />
        ) : (
          <div className="w-24 h-14 rounded bg-[var(--border)]" />
        )}
      </Link>
      <div className="flex-1 min-w-0">
        <Link
          href={`/videos/${video.id}`}
          className="font-medium text-sm hover:text-[var(--accent)] transition-colors line-clamp-1"
        >
          {video.title}
        </Link>
        <div className="flex items-center gap-3 mt-1 text-xs text-[var(--muted)]">
          <span className="px-1.5 py-0.5 bg-[var(--accent)]/20 text-[var(--accent)] rounded text-[10px] font-medium">
            {video.media_type}
          </span>
          <span>{formatDuration(video.duration)}</span>
          {video.upload_date && (
            <span>{new Date(video.upload_date).toLocaleDateString()}</span>
          )}
          {hasLabels && (
            <div className="flex items-center gap-1.5">
              {video.labels.format && (
                <span className="px-1.5 py-0.5 bg-[var(--muted)]/10 text-[var(--prose-color)] rounded text-[10px] font-medium">
                  {video.labels.format.toUpperCase()}
                </span>
              )}
              {video.labels.resolution && (
                <span className="px-1.5 py-0.5 bg-[var(--accent)]/10 text-[var(--accent)] rounded text-[10px] font-medium">
                  {video.labels.resolution}
                </span>
              )}
              {video.labels.dynamic_range && (
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  video.labels.dynamic_range.toLowerCase().includes('hdr')
                    ? 'bg-purple-500/10 text-purple-400'
                    : 'bg-[var(--muted)]/10 text-[var(--muted)]'
                }`}>
                  {video.labels.dynamic_range}
                </span>
              )}
              {video.labels.acodec && (
                <span className="px-1.5 py-0.5 bg-[var(--muted)]/10 text-[var(--prose-color)] rounded text-[10px]">
                  {video.labels.acodec.toUpperCase()}
                </span>
              )}
              {video.labels.audio_channels && (
                <span className="px-1.5 py-0.5 bg-[var(--muted)]/10 text-[var(--prose-color)] rounded text-[10px]">
                  {video.labels.audio_channels === 2 ? 'Stereo' : video.labels.audio_channels === 6 ? '5.1' : `${video.labels.audio_channels}ch`}
                </span>
              )}
              {video.labels.filesize_approx && (
                <span className="px-1.5 py-0.5 bg-[var(--muted)]/10 text-[var(--prose-color)] rounded text-[10px]">
                  {formatFileSize(video.labels.filesize_approx)}
                </span>
              )}
            </div>
          )}
        </div>
        {/* Show progress bar when we have progress data */}
        {progress && progress.status !== 'completed' && (
          <div className="mt-2 max-w-sm">
            <DownloadProgress progress={progress} />
          </div>
        )}
        {video.error_message && (
          <p className="text-xs text-[var(--error)] mt-1 line-clamp-1">{video.error_message}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        {renderStatusIcon()}
        {!video.downloaded && !downloadRunning && !downloadQueued && (
          <button
            onClick={(e) => { e.preventDefault(); onDownload() }}
            disabled={downloading}
            className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors disabled:opacity-50"
            title="Download"
          >
            {downloading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Download size={16} />
            )}
          </button>
        )}
      </div>
    </div>
  )
}
