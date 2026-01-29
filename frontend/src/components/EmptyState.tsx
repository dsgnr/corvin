'use client'

interface EmptyStateProps {
  message: string
  className?: string
}

export function EmptyState({ message, className = '' }: EmptyStateProps) {
  return <p className={`p-4 text-sm text-[var(--muted)] ${className}`}>{message}</p>
}
