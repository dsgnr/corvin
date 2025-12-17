'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api, VideoList, Video } from '@/lib/api'
import { ArrowLeft, Download, RefreshCw, CheckCircle, XCircle, Clock, Loader2, ExternalLink } from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'

const PAGE_SIZE = 20

export default function ListDetailPage() {
  const params = useParams()
  const listId = Number(params.id)
  const [list, setList] = useState<VideoList | null>(null)
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [downloadingPending, setDownloadingPending] = useState(false)
  const [retryingFailed, setRetryingFailed] = useState(false)
  const [downloadingIds, setDownloadingIds] = useState<Set<number>>(new Set())
  const [filter, setFilter] = useState<'all' | 'pending' | 'downloaded' | 'failed'>('all')
  const [currentPage, setCurrentPage] = useState(1)

  const checkSyncStatus = async () => {
    try {
      const tasks = await api.getTasks({ type: 'sync', status: 'running' })
      const isRunning = tasks.some(t => t.entity_id === listId)
      setSyncing(isRunning)
      return isRunning
    } catch {
      return false
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

  // Poll for sync status while syncing
  useEffect(() => {
    if (!syncing) return
    const interval = setInterval(async () => {
      const stillRunning = await checkSyncStatus()
      if (!stillRunning) {
        fetchData()
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [syncing, listId])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await api.triggerListSync(listId)
    } catch (err) {
      console.error('Failed to sync:', err)
      setSyncing(false)
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
            <h1 className="text-2xl font-semibold">{list.name}</h1>
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
          disabled={syncing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Syncing' : 'Sync'}
        </button>
        {stats.pending > 0 && (
          <button
            onClick={handleDownloadPending}
            disabled={downloadingPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] rounded-md transition-colors disabled:opacity-50"
          >
            {downloadingPending ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Download Queued
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
              <p className="text-sm text-[var(--muted)] whitespace-pre-line">{list.description}</p>
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
          <p className="text-xs text-[var(--muted)]">Total</p>
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
          <p className="text-2xl font-semibold text-[var(--warning)]">{stats.pending}</p>
          <p className="text-xs text-[var(--muted)]">Pending</p>
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
              />
            ))
          )}
        </div>
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
      </div>
    </div>
  )
}

function VideoRow({ video, downloading, onDownload }: {
  video: Video
  downloading: boolean
  onDownload: () => void
}) {
  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
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
          <span>{formatDuration(video.duration)}</span>
          {video.upload_date && (
            <span>{new Date(video.upload_date).toLocaleDateString()}</span>
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
        ) : (
          <Clock size={18} className="text-[var(--warning)]" />
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
