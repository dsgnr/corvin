'use client'

import { Film } from 'lucide-react'
import { ReactNode } from 'react'

interface VideoThumbnailProps {
  src?: string | null
  alt?: string
  className?: string
  /** Show duration overlay */
  duration?: string
  /** Size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Custom overlay content (e.g., status badge) */
  overlay?: ReactNode
  /** Enable hover opacity effect */
  hoverEffect?: boolean
}

export function VideoThumbnail({
  src,
  alt = '',
  className = '',
  duration,
  size = 'md',
  overlay,
  hoverEffect = false,
}: VideoThumbnailProps) {
  const sizeStyles = {
    sm: 'aspect-video w-full sm:h-14 sm:w-24',
    md: 'aspect-video w-full',
    lg: 'aspect-video w-full',
  }

  const iconSizes = {
    sm: 16,
    md: 24,
    lg: 32,
  }

  const hoverClass = hoverEffect ? 'transition-opacity hover:opacity-80' : ''

  if (!src) {
    return (
      <div
        className={`flex items-center justify-center rounded bg-[var(--border)] ${sizeStyles[size]} ${className}`}
      >
        <Film size={iconSizes[size]} className="text-[var(--muted)]" />
      </div>
    )
  }

  return (
    <div className="relative">
      <img
        src={src}
        alt={alt}
        className={`rounded bg-[var(--border)] object-cover ${sizeStyles[size]} ${hoverClass} ${className}`}
      />
      {duration && (
        <div className="absolute right-2 bottom-2 rounded bg-black/80 px-1.5 py-0.5 text-xs text-white">
          {duration}
        </div>
      )}
      {overlay}
    </div>
  )
}
