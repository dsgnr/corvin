'use client'

interface MediaTypeBadgeProps {
  type: string | null
  compact?: boolean
}

const getMediaTypeStyles = (type: string | null): string => {
  switch (type) {
    case 'video':
      return 'bg-blue-500/20 text-blue-400'
    case 'short':
      return 'bg-pink-500/20 text-pink-400'
    case 'livestream':
      return 'bg-orange-500/20 text-orange-400'
    case 'audio':
      return 'bg-purple-500/20 text-purple-400'
    default:
      return 'bg-[var(--accent)]/20 text-[var(--accent)]'
  }
}

export function MediaTypeBadge({ type, compact = false }: MediaTypeBadgeProps) {
  if (!type) return null

  const baseStyles = getMediaTypeStyles(type)
  const sizeStyles = compact ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs uppercase'

  return <span className={`rounded font-medium ${baseStyles} ${sizeStyles}`}>{type}</span>
}
