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
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
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
      <div className="h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ${isProcessing ? 'bg-[var(--warning)] animate-pulse' : 'bg-[var(--accent)]'}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
