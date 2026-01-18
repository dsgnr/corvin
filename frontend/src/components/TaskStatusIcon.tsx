'use client'

import { CheckCircle, XCircle, Clock, Loader2, Pause } from 'lucide-react'

interface TaskStatusIconProps {
  status: string
  size?: number
}

/**
 * Displays an appropriate icon for a task's current status.
 * Handles completed, failed, running, paused, cancelled, and pending states.
 */
export function TaskStatusIcon({ status, size = 18 }: TaskStatusIconProps) {
  switch (status) {
    case 'completed':
      return <CheckCircle size={size} className="text-[var(--success)]" />
    case 'failed':
      return <XCircle size={size} className="text-[var(--error)]" />
    case 'running':
      return <Loader2 size={size} className="text-[var(--accent)] animate-spin" />
    case 'paused':
      return <Pause size={size} className="text-[var(--muted)]" />
    case 'cancelled':
      return <XCircle size={size} className="text-[var(--muted)]" />
    default:
      return <Clock size={size} className="text-[var(--warning)]" />
  }
}
