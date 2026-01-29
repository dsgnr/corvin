'use client'

import { DownloadProgress as ProgressData } from '@/lib/api'

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  pending: 'Starting',
  downloading: 'Downloading',
  processing: 'Processing',
  completed: 'Done',
  error: 'Failed',
  retrying: 'Retrying',
}

function formatEta(seconds: number | null): string {
  if (!seconds || seconds < 0) return ''
  const secs = Math.round(seconds)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
}

export function DownloadProgress({ progress }: { progress: ProgressData }) {
  const percent = Math.min(100, Math.max(0, progress.percent || 0))
  const isProcessing = progress.status === 'processing'
  const isError = progress.status === 'error'
  const isRetrying = progress.status === 'retrying'
  const showStats = progress.status === 'downloading'

  const getStatusLabel = () => {
    const attempt = progress.attempt
    const maxAttempts = progress.max_attempts
    const isRetryAttempt = attempt && maxAttempts && attempt > 1

    if (isRetrying && isRetryAttempt) {
      return `Retrying (attempt ${attempt}/${maxAttempts})`
    }
    // Show attempt info only if we're on attempt 2+
    if ((progress.status === 'pending' || progress.status === 'downloading') && isRetryAttempt) {
      const base = STAGE_LABELS[progress.status] || progress.status
      return `${base} (attempt ${attempt}/${maxAttempts})`
    }
    return STAGE_LABELS[progress.status] || progress.status
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3 text-[10px] text-[var(--muted)]">
        <span
          className={
            isError
              ? 'text-[var(--error)]'
              : isProcessing || isRetrying
                ? 'text-[var(--warning)]'
                : 'text-[var(--accent)]'
          }
        >
          {getStatusLabel()}
        </span>
        {showStats && progress.speed && <span>{progress.speed}</span>}
        {showStats && progress.eta && progress.eta > 0 && <span>{formatEta(progress.eta)}</span>}
        <span className="ml-auto tabular-nums">{Math.round(percent)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
        <div
          className={`h-full transition-all duration-300 ${isError ? 'bg-[var(--error)]' : isProcessing || isRetrying ? 'animate-pulse bg-[var(--warning)]' : 'bg-[var(--accent)]'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
