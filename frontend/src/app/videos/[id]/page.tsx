'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api, Video, Task, getTasksStreamUrl } from '@/lib/api'
import { useProgress } from '@/lib/ProgressContext'
import { useEventSource } from '@/lib/useEventSource'
import { DownloadProgress } from '@/components/DownloadProgress'
import { VideoLabels } from '@/components/VideoLabels'
import { ExtractorIcon } from '@/components/ExtractorIcon'
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
} from 'lucide-react'
import { clsx } from 'clsx'

export default function VideoDetailPage() {
  const params = useParams()
  const videoId = Number(params.id)
  const [video, setVideo] = useState<Video | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [downloadQueued, setDownloadQueued] = useState(false)
  const [downloadRunning, setDownloadRunning] = useState(false)

  // Derive list from video
  const list = video?.list ?? null

  // Real-time download progress
  const progress = useProgress(videoId)

  // SSE stream for download task status
  const handleTasksMessage = useCallback(
    (tasks: Task[]) => {
      const isQueued = tasks.some(t => t.status === 'pending' && t.entity_id === videoId)
      const isRunning = tasks.some(t => t.status === 'running' && t.entity_id === videoId)
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

  // Refresh video data when download completes
  useEffect(() => {
    if (progress?.status === 'completed') {
      const refetchVideo = async () => {
        try {
          const data = await api.getVideo(videoId)
          setVideo(data)
          // Clear task states since download is complete
          setDownloadQueued(false)
          setDownloadRunning(false)
        } catch (err) {
          console.error('Failed to fetch video:', err)
        }
      }
      setTimeout(refetchVideo, 1000)
    }
  }, [progress?.status, videoId])

  const handleDownload = async () => {
    if (!video) return
    setDownloading(true)
    try {
      await api.triggerVideoDownload(video.id)
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
      const data = await api.getVideo(videoId)
      setVideo(data)
    } catch (err) {
      console.error('Failed to retry:', err)
    } finally {
      setRetrying(false)
    }
  }

  // Determine status
  const getStatus = () => {
    if (video?.downloaded) return 'downloaded'
    if (video?.error_message) return 'failed'
    if (downloadRunning) return 'downloading'
    if (downloadQueued) return 'queued'
    if (list?.auto_download) return 'pending'
    return 'manual'
  }

  const status = getStatus()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
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
    <div className="p-6 space-y-6">
      {/* Channel Header */}
      <div className="flex items-center gap-4">
        <Link
          href={`/lists/${video.list_id}`}
          className="p-2 rounded-md hover:bg-[var(--card)] transition-colors"
        >
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1 flex items-center gap-4">
          {list?.thumbnail && (
            <Link href={`/lists/${video.list_id}`}>
              <img
                src={list.thumbnail}
                alt={list.name}
                className="w-12 h-12 rounded-lg object-cover hover:opacity-80 transition-opacity"
                referrerPolicy="no-referrer"
              />
            </Link>
          )}
          <div>
            <div className="flex items-center gap-2">
              <ExtractorIcon extractor={list?.extractor} size="md" />
              <Link
                href={`/lists/${video.list_id}`}
                className="font-medium hover:text-[var(--accent)] transition-colors"
              >
                {list?.name || 'Loading...'}
              </Link>
            </div>
            {list?.url && (
              <a
                href={list.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[var(--muted)] hover:text-[var(--foreground)] flex items-center gap-1"
              >
                {list.url.length > 50 ? list.url.slice(0, 50) + '...' : list.url}
                <ExternalLink size={10} />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left Column - Thumbnail & Actions */}
        <div className="lg:col-span-2 space-y-4">
          {/* Thumbnail with status overlay */}
          <div className="relative group">
            {video.thumbnail ? (
              <img
                src={video.thumbnail}
                alt={video.title}
                className="w-full aspect-video object-cover rounded-lg bg-[var(--card)]"
              />
            ) : (
              <div className="w-full aspect-video bg-[var(--card)] rounded-lg flex items-center justify-center">
                <span className="text-[var(--muted)]">No thumbnail</span>
              </div>
            )}
            {/* Duration badge */}
            {video.duration && (
              <div className="absolute bottom-2 right-2 px-1.5 py-0.5 bg-black/80 text-white text-xs rounded">
                {formatDuration(video.duration)}
              </div>
            )}
            {/* Status overlay */}
            <div
              className={clsx(
                'absolute top-2 left-2 px-2 py-1 rounded text-xs font-medium flex items-center gap-1.5 shadow-lg',
                status === 'downloaded' && 'bg-[var(--success)] text-white',
                status === 'failed' && 'bg-[var(--error)] text-white',
                status === 'downloading' && 'bg-[var(--accent)] text-white',
                status === 'queued' && 'bg-[var(--warning)] text-black',
                status === 'pending' && 'bg-[var(--warning)] text-black',
                status === 'manual' && 'bg-black/80 text-white border border-[var(--border)]'
              )}
            >
              {status === 'downloaded' && (
                <>
                  <CheckCircle size={12} /> Downloaded
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
          {progress &&
            progress.status !== 'completed' &&
            progress.status !== 'error' &&
            !video.error_message && (
              <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-3">
                <DownloadProgress progress={progress} />
              </div>
            )}

          {/* Action Buttons */}
          <div className="flex gap-2">
            {!video.downloaded && !downloadRunning && !downloadQueued && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors disabled:opacity-50"
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
              <div className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--warning)] text-black rounded-md">
                <Clock size={14} />
                Queued
              </div>
            )}
            {downloadRunning && !video.downloaded && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] text-white rounded-md">
                <Loader2 size={14} className="animate-spin" />
                Downloading
              </div>
            )}
            {video.error_message && (
              <button
                onClick={handleRetry}
                disabled={retrying}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--warning)] hover:opacity-90 text-black rounded-md transition-colors disabled:opacity-50"
              >
                {retrying ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <RotateCcw size={14} />
                )}
                Retry
              </button>
            )}
            <a
              href={video.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] rounded-md transition-colors"
            >
              <ExternalLink size={14} />
              YouTube
            </a>
          </div>

          {/* Error Message */}
          {video.error_message && (
            <div className="bg-[var(--error)]/10 border border-[var(--error)]/30 rounded-lg p-4">
              <div className="flex items-center gap-2 text-[var(--error)] font-medium mb-2">
                <XCircle size={16} />
                Download Failed
              </div>
              <p className="text-sm text-[var(--error)]">{video.error_message}</p>
            </div>
          )}

          {/* Download Path */}
          {video.download_path && (
            <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
              <div className="flex items-center gap-2 text-[var(--muted)] text-sm mb-2">
                <FolderOpen size={14} />
                Download Path
              </div>
              <p className="text-sm font-mono text-[var(--foreground)] break-all">
                {video.download_path}
              </p>
            </div>
          )}
        </div>

        {/* Right Column - Video Info */}
        <div className="lg:col-span-3 space-y-4">
          {/* Title & Meta */}
          <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-5">
            <h1 className="text-xl font-semibold mb-4 leading-tight">{video.title}</h1>

            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span className="px-2 py-1 bg-[var(--accent)]/20 text-[var(--accent)] rounded text-xs font-medium uppercase">
                {video.media_type}
              </span>
              {video.duration && (
                <span className="flex items-center gap-1.5 px-2 py-1 bg-[var(--border)] rounded text-xs text-[var(--muted)]">
                  <Timer size={12} />
                  {formatDuration(video.duration)}
                </span>
              )}
              {video.upload_date && (
                <span className="flex items-center gap-1.5 px-2 py-1 bg-[var(--border)] rounded text-xs text-[var(--muted)]">
                  <Calendar size={12} />
                  {new Date(video.upload_date).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
              )}
              <span className="flex items-center gap-1.5 px-2 py-1 bg-[var(--border)] rounded text-xs text-[var(--muted)] font-mono">
                <Hash size={12} />
                {video.video_id}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm pt-4 border-t border-[var(--border)]">
              <div>
                <dt className="text-[var(--muted)] text-xs mb-1">Added</dt>
                <dd>
                  {new Date(video.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--muted)] text-xs mb-1">Updated</dt>
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
                  <dt className="text-[var(--muted)] text-xs mb-1 flex items-center gap-1">
                    <RefreshCw size={10} /> Retries
                  </dt>
                  <dd>{video.retry_count}</dd>
                </div>
              )}
            </div>
          </div>

          {/* Media Info Labels */}
          {video.downloaded && video.labels && Object.keys(video.labels).length > 0 && (
            <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-5">
              <h2 className="font-medium mb-4">Media Info</h2>
              <VideoLabels labels={video.labels} />
            </div>
          )}

          {/* Description */}
          {video.description && (
            <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-5">
              <h2 className="font-medium mb-3">Description</h2>
              <div
                className="text-sm text-[var(--muted)] whitespace-pre-wrap break-words leading-relaxed [&_a]:text-[var(--accent)] [&_a]:underline [&_a]:hover:opacity-80"
                dangerouslySetInnerHTML={{ __html: linkifyText(video.description) }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
