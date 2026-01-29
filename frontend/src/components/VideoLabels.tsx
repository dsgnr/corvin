'use client'

import { VideoLabels as VideoLabelsType } from '@/lib/api'
import { formatFileSize } from '@/lib/utils'
import { clsx } from 'clsx'

interface VideoLabelsProps {
  labels: VideoLabelsType
  /** Actual file size in bytes (from downloaded video) */
  filesize?: number | null
  /** Use smaller text for compact displays (e.g. list rows) */
  compact?: boolean
}

/**
 * Displays video metadata labels (format, resolution, HDR, audio codec, etc.)
 * as styled badges. Used in video detail pages and video list rows.
 */
export function VideoLabels({ labels, filesize, compact = false }: VideoLabelsProps) {
  if (!labels || Object.keys(labels).length === 0) return null

  const textSize = compact ? 'text-[10px]' : 'text-xs'
  const padding = compact ? 'px-1.5 py-0.5' : 'px-2 py-0.5'

  // Use actual filesize if available, otherwise fall back to approximate
  const displayFilesize = filesize ?? labels.filesize_approx

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {labels.format && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded-full bg-zinc-700/50 font-medium text-zinc-300'
          )}
        >
          {labels.format.toUpperCase()}
        </span>
      )}
      {labels.resolution && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded-full bg-blue-500/20 font-medium text-blue-400'
          )}
        >
          {labels.resolution}
        </span>
      )}
      {labels.dynamic_range && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded-full font-medium',
            labels.dynamic_range.toLowerCase().includes('hdr')
              ? 'bg-amber-500/20 text-amber-400'
              : 'bg-zinc-700/50 text-zinc-400'
          )}
        >
          {labels.dynamic_range}
        </span>
      )}
      {labels.was_live && (
        <span
          className={clsx(padding, textSize, 'rounded-full bg-red-500/20 font-medium text-red-400')}
        >
          Was Live
        </span>
      )}
      {labels.acodec && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded-full bg-emerald-500/20 font-medium text-emerald-400'
          )}
        >
          {labels.acodec.toUpperCase()}
        </span>
      )}
      {labels.audio_channels && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded-full bg-violet-500/20 font-medium text-violet-400'
          )}
        >
          {formatAudioChannels(labels.audio_channels)}
        </span>
      )}
      {displayFilesize && (
        <span
          className={clsx(
            padding,
            textSize,
            'rounded-full bg-zinc-700/50 font-medium text-zinc-400'
          )}
        >
          {formatFileSize(displayFilesize)}
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
