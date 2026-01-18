'use client'

import { VideoLabels as VideoLabelsType } from '@/lib/api'
import { formatFileSize } from '@/lib/utils'
import { clsx } from 'clsx'

interface VideoLabelsProps {
  labels: VideoLabelsType
  /** Use smaller text for compact displays (e.g. list rows) */
  compact?: boolean
}

/**
 * Displays video metadata labels (format, resolution, HDR, audio codec, etc.)
 * as styled badges. Used in video detail pages and video list rows.
 */
export function VideoLabels({ labels, compact = false }: VideoLabelsProps) {
  if (!labels || Object.keys(labels).length === 0) return null

  const textSize = compact ? 'text-[10px]' : 'text-sm'
  const padding = compact ? 'px-1.5 py-0.5' : 'px-2 py-1'

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {labels.format && (
        <span className={clsx(padding, textSize, 'bg-[var(--muted)]/10 text-[var(--prose-color)] rounded font-medium')}>
          {labels.format.toUpperCase()}
        </span>
      )}
      {labels.resolution && (
        <span className={clsx(padding, textSize, 'bg-[var(--accent)]/10 text-[var(--accent)] rounded font-medium')}>
          {labels.resolution}
        </span>
      )}
      {labels.dynamic_range && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded font-medium',
            labels.dynamic_range.toLowerCase().includes('hdr')
              ? 'bg-purple-500/10 text-purple-400'
              : 'bg-[var(--muted)]/10 text-[var(--muted)]'
          )}
        >
          {labels.dynamic_range}
        </span>
      )}
      {labels.acodec && (
        <span className={clsx(padding, textSize, 'bg-[var(--muted)]/10 text-[var(--prose-color)] rounded')}>
          {labels.acodec.toUpperCase()}
        </span>
      )}
      {labels.audio_channels && (
        <span className={clsx(padding, textSize, 'bg-[var(--muted)]/10 text-[var(--prose-color)] rounded')}>
          {formatAudioChannels(labels.audio_channels)}
        </span>
      )}
      {labels.filesize_approx && (
        <span className={clsx(padding, textSize, 'bg-[var(--muted)]/10 text-[var(--prose-color)] rounded')}>
          {formatFileSize(labels.filesize_approx)}
        </span>
      )}
    </div>
  )
}

function formatAudioChannels(channels: number): string {
  if (channels === 2) return 'Stereo'
  if (channels === 6) return '5.1'
  return `${channels}ch`
}
