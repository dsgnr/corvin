'use client'

interface BlacklistedBadgeProps {
  compact?: boolean
}

export function BlacklistedBadge({ compact = false }: BlacklistedBadgeProps) {
  const sizeStyles = compact ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs'

  return (
    <span className={`rounded bg-[var(--muted)]/20 font-medium text-[var(--muted)] ${sizeStyles}`}>
      blacklisted
    </span>
  )
}
