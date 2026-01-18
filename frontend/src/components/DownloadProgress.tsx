'use client'

import { DownloadProgress as ProgressData } from '@/lib/api'

const STAGE_LABELS: Record<string, string> = {
  pending: 'Starting',
  downloading: 'Downloading',
  processing: 'Processing',
  completed: 'Done',
  error: 'Failed',
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
  const showStats = progress.status === 'downloading'

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3 text-[10px] text-[var(--muted)]">
        <span className={isProcessing ? 'text-[var(--warning)]' : 'text-[var(--accent)]'}>
          {STAGE_LABELS[progress.status] || progress.status}
        </span>
        {showStats && progress.speed && <span>{progress.speed}</span>}
        {showStats && progress.eta && progress.eta > 0 && <span>{formatEta(progress.eta)}</span>}
        <span className="ml-auto tabular-nums">{Math.round(percent)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
        <div
          className={`h-full transition-all duration-300 ${isProcessing ? 'animate-pulse bg-[var(--warning)]' : 'bg-[var(--accent)]'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
