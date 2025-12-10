'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api, Video } from '@/lib/api'
import { ArrowLeft, Download, ExternalLink, CheckCircle, XCircle, Clock, Loader2, RotateCcw } from 'lucide-react'

export default function VideoDetailPage() {
  const params = useParams()
  const videoId = Number(params.id)
  const [video, setVideo] = useState<Video | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [retrying, setRetrying] = useState(false)

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

  useEffect(() => {
    fetchVideo()
  }, [videoId])

  const handleDownload = async () => {
    if (!video) return
    setDownloading(true)
    try {
      await api.triggerVideoDownload(video.id)
      setTimeout(fetchVideo, 2000)
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
      await fetchVideo()
    } catch (err) {
      console.error('Failed to retry:', err)
    } finally {
      setRetrying(false)
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'Unknown'
    const hrs = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

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
      <div className="flex items-center gap-4">
        <Link href={`/lists/${video.list_id}`} className="p-2 rounded-md hover:bg-[var(--card)] transition-colors">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-semibold flex-1 line-clamp-1">{video.title}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Thumbnail & Actions */}
        <div className="space-y-4">
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

          <div className="flex gap-2">
            {!video.downloaded && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors disabled:opacity-50"
              >
                {downloading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Download size={16} />
                )}
                Download
              </button>
            )}
            {video.error_message && (
              <button
                onClick={handleRetry}
                disabled={retrying}
                className="flex items-center justify-center gap-2 px-4 py-2 bg-[var(--warning)] hover:opacity-90 text-white rounded-md transition-colors disabled:opacity-50"
              >
                {retrying ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <RotateCcw size={16} />
                )}
                Retry
              </button>
            )}
            <a
              href={video.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-4 py-2 bg-[var(--card)] hover:bg-[var(--card-hover)] border border-[var(--border)] rounded-md transition-colors"
            >
              <ExternalLink size={16} />
              YouTube
            </a>
          </div>
        </div>

        {/* Metadata */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
            <h2 className="font-medium mb-4">Details</h2>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-[var(--muted)]">Download Status</dt>
                <dd className="flex items-center gap-2 mt-1">
                  {video.downloaded ? (
                    <>
                      <CheckCircle size={16} className="text-[var(--success)]" />
                      <span className="text-[var(--success)]">Downloaded</span>
                    </>
                  ) : video.error_message ? (
                    <>
                      <XCircle size={16} className="text-[var(--error)]" />
                      <span className="text-[var(--error)]">Failed</span>
                    </>
                  ) : (
                    <>
                      <Clock size={16} className="text-[var(--warning)]" />
                      <span className="text-[var(--warning)]">Pending</span>
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Duration</dt>
                <dd className="mt-1">{formatDuration(video.duration)}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Upload Date</dt>
                <dd className="mt-1">
                  {video.upload_date ? new Date(video.upload_date).toLocaleDateString() : 'Unknown'}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Video ID</dt>
                <dd className="mt-1 font-mono text-xs">{video.video_id}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Retry Count</dt>
                <dd className="mt-1">{video.retry_count}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Added</dt>
                <dd className="mt-1">{new Date(video.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          </div>

          {video.download_path && (
            <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
              <h2 className="font-medium mb-2">Download Path</h2>
              <p className="text-sm font-mono text-[var(--muted)] break-all">{video.download_path}</p>
            </div>
          )}

          {video.error_message && (
            <div className="bg-[var(--error)]/10 border border-[var(--error)]/30 rounded-lg p-4">
              <h2 className="font-medium text-[var(--error)] mb-2">Error</h2>
              <p className="text-sm text-[var(--error)]">{video.error_message}</p>
            </div>
          )}

          {video.description && (
            <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
              <h2 className="font-medium mb-2">Description</h2>
              <p className="text-sm text-[var(--muted)] whitespace-pre-wrap">
                {video.description}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
