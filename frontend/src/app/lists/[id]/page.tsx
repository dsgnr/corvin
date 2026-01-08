'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api, VideoList, Video } from '@/lib/api'
import { formatDuration, formatFileSize } from '@/lib/utils'
import { ArrowLeft, Download, RefreshCw, CheckCircle, XCircle, Clock, Loader2, ExternalLink, CircleSlash } from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'

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
  const [loading, setLoading] = useState(true)
  const [syncStatus, setSyncStatus] = useState<'idle' | 'queued' | 'running'>('idle')
  const [downloadingPending, setDownloadingPending] = useState(false)
  const [retryingFailed, setRetryingFailed] = useState(false)
  const [downloadingIds, setDownloadingIds] = useState<Set<number>>(new Set())
  const [filter, setFilter] = useState<'all' | 'pending' | 'downloaded' | 'failed'>('all')
  const [currentPage, setCurrentPage] = useState(1)

  const checkSyncStatus = async () => {
    try {
      const [runningTasks, pendingTasks] = await Promise.all([
        api.getTasks({ type: 'sync', status: 'running' }),
        api.getTasks({ type: 'sync', status: 'pending' }),
      ])
      const isRunning = runningTasks.some(t => t.entity_id === listId)
      const isQueued = pendingTasks.some(t => t.entity_id === listId)
      
      if (isRunning) {
        setSyncStatus('running')
        return 'running'
      } else if (isQueued) {
        setSyncStatus('queued')
        return 'queued'
      } else {
        setSyncStatus('idle')
        return 'idle'
      }
    } catch {
      return 'idle'
    }
  }

  const fetchData = async () => {
    try {
      const [listData, videosData] = await Promise.all([
        api.getList(listId),
        api.getVideos({ list_id: listId, limit: 500 }),
      ])
      setList(listData)
      setVideos(videosData)
      await checkSyncStatus()
    } catch (err) {
      console.error('Failed to fetch list:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [listId])

  // Poll for sync status while queued or running
  useEffect(() => {
    if (syncStatus === 'idle') return
    const interval = setInterval(async () => {
      const status = await checkSyncStatus()
      if (status === 'idle') {
        fetchData()
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [syncStatus, listId])

  // Refresh videos every second while running
  useEffect(() => {
    if (syncStatus !== 'running') return
    const interval = setInterval(async () => {
      try {
        const videosData = await api.getVideos({ list_id: listId, limit: 500 })
        setVideos(videosData)
      } catch (err) {
        console.error('Failed to refresh videos:', err)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [syncStatus, listId])

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

  const handleDownload = async (videoId: number) => {
    setDownloadingIds(prev => new Set(prev).add(videoId))
    try {
      await api.triggerVideoDownload(videoId)
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
      if (filter === 'pending') return !v.downloaded && !v.error_message
      if (filter === 'downloaded') return v.downloaded
      if (filter === 'failed') return !!v.error_message
      return true
    })
    .sort((a, b) => {
      const dateA = a.upload_date ? new Date(a.upload_date).getTime() : 0
      const dateB = b.upload_date ? new Date(b.upload_date).getTime() : 0
      return dateB - dateA
    })

  const totalPages = Math.ceil(filteredVideos.length / PAGE_SIZE)
  const paginatedVideos = filteredVideos.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  // Reset to page 1 when filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [filter])

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
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-medium">Videos ({filteredVideos.length})</h2>
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

function VideoRow({ video, downloading, onDownload, autoDownload }: {
  video: Video
  downloading: boolean
  onDownload: () => void
  autoDownload: boolean
}) {
  const hasLabels = video.downloaded && video.labels && Object.keys(video.labels).length > 0

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
        {video.error_message && (
          <p className="text-xs text-[var(--error)] mt-1 line-clamp-1">{video.error_message}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        {video.downloaded ? (
          <CheckCircle size={18} className="text-[var(--success)]" />
        ) : video.error_message ? (
          <XCircle size={18} className="text-[var(--error)]" />
        ) : autoDownload ? (
          <Clock size={18} className="text-[var(--warning)]" />
        ) : (
          <span title="Not pending - auto download is disabled for this list">
            <CircleSlash size={18} className="text-[var(--muted)] opacity-50" />
          </span>
        )}
        {!video.downloaded && (
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
