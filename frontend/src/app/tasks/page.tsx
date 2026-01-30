'use client'

import { useState, useCallback, useMemo, useEffect } from 'react'
import {
  api,
  Task,
  TaskStats,
  TasksPaginatedResponse,
  getTaskStatsStreamUrl,
  getTasksStreamUrl,
} from '@/lib/api'
import { useEventSource } from '@/lib/useEventSource'
import {
  RefreshCw,
  Loader2,
  Play,
  RotateCcw,
  Pause,
  Square,
  Ban,
  Download,
  Search,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'
import { Select } from '@/components/Select'
import { TaskStatusIcon } from '@/components/TaskStatusIcon'
import { EmptyState } from '@/components/EmptyState'
import Link from 'next/link'
import { PAGE_SIZE_OPTIONS, DEFAULT_PAGE_SIZE } from '@/lib/utils'

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [currentPage, setCurrentPage] = useState(1)

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== debouncedSearch) {
        setDebouncedSearch(search)
        setCurrentPage(1)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [search, debouncedSearch])

  // Build stream URL with current filters
  const tasksStreamUrl = useMemo(() => {
    const params: {
      page: number
      pageSize: number
      type?: string
      status?: string
      search?: string
    } = {
      page: currentPage,
      pageSize: pageSize,
    }
    if (filter === 'sync' || filter === 'download') {
      params.type = filter
    } else if (filter !== 'all') {
      params.status = filter
    }
    if (debouncedSearch) {
      params.search = debouncedSearch
    }
    return getTasksStreamUrl(params)
  }, [currentPage, pageSize, filter, debouncedSearch])

  const handleTasksMessage = useCallback((data: TasksPaginatedResponse) => {
    setTasks(data.tasks)
    setTotal(data.total)
    setTotalPages(data.total_pages)
    setLoading(false)
  }, [])

  const handleTasksError = useCallback(() => {
    const params: {
      page: number
      pageSize: number
      type?: string
      status?: string
      search?: string
    } = {
      page: currentPage,
      pageSize: pageSize,
    }
    if (filter === 'sync' || filter === 'download') {
      params.type = filter
    } else if (filter !== 'all') {
      params.status = filter
    }
    if (debouncedSearch) {
      params.search = debouncedSearch
    }
    api
      .getTasksPaginated(params)
      .then((data) => {
        setTasks(data.tasks)
        setTotal(data.total)
        setTotalPages(data.total_pages)
        setLoading(false)
      })
      .catch(console.error)
  }, [currentPage, pageSize, filter, debouncedSearch])

  const handleStatsMessage = useCallback((data: TaskStats) => {
    setStats(data)
  }, [])

  const handleStatsError = useCallback(() => {
    api.getTaskStats().then(setStats).catch(console.error)
  }, [])

  useEventSource(tasksStreamUrl, handleTasksMessage, handleTasksError)
  useEventSource(getTaskStatsStreamUrl(), handleStatsMessage, handleStatsError)

  const handlePauseAll = async () => {
    try {
      await api.pauseAllTasks()
    } catch (err) {
      console.error('Failed to pause all tasks:', err)
    }
  }

  const handleResumeAll = async () => {
    try {
      await api.resumeAllTasks()
    } catch (err) {
      console.error('Failed to resume all tasks:', err)
    }
  }

  const handleCancelAll = async () => {
    try {
      await api.cancelAllTasks()
    } catch (err) {
      console.error('Failed to cancel all tasks:', err)
    }
  }

  const handlePauseSync = async () => {
    try {
      await api.pauseSyncTasks()
    } catch (err) {
      console.error('Failed to pause sync tasks:', err)
    }
  }

  const handleResumeSync = async () => {
    try {
      await api.resumeSyncTasks()
    } catch (err) {
      console.error('Failed to resume sync tasks:', err)
    }
  }

  const handlePauseDownload = async () => {
    try {
      await api.pauseDownloadTasks()
    } catch (err) {
      console.error('Failed to pause download tasks:', err)
    }
  }

  const handleResumeDownload = async () => {
    try {
      await api.resumeDownloadTasks()
    } catch (err) {
      console.error('Failed to resume download tasks:', err)
    }
  }

  const handleRetryFailed = async () => {
    try {
      await api.retryFailedTasks()
    } catch (err) {
      console.error('Failed to retry failed tasks:', err)
    }
  }

  const handleTaskAction = async (
    taskId: number,
    action: 'retry' | 'pause' | 'resume' | 'cancel'
  ) => {
    try {
      switch (action) {
        case 'retry':
          await api.retryTask(taskId)
          break
        case 'pause':
          await api.pauseTask(taskId)
          break
        case 'resume':
          await api.resumeTask(taskId)
          break
        case 'cancel':
          await api.cancelTask(taskId)
          break
      }
    } catch (err) {
      console.error(`Failed to ${action} task:`, err)
    }
  }

  // Check if we have tasks with certain statuses (from stats, not filtered list)
  const hasPendingTasks = (stats?.pending_sync ?? 0) + (stats?.pending_download ?? 0) > 0
  const syncPaused = stats?.worker?.sync_paused ?? false
  const downloadPaused = stats?.worker?.download_paused ?? false
  const schedulePaused = stats?.schedule_paused ?? false

  // Handle filter change with page reset
  const handleFilterChange = useCallback((newFilter: string) => {
    setFilter(newFilter)
    setCurrentPage(1)
    setLoading(true)
  }, [])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <div className="flex flex-wrap gap-2">
          {hasPendingTasks && (
            <button
              onClick={handlePauseAll}
              className="flex items-center justify-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--foreground)] transition-colors hover:bg-[var(--card-hover)] sm:py-1.5"
              title="Pause Queued"
            >
              <Pause size={18} className="sm:h-[14px] sm:w-[14px]" />
              <span className="hidden sm:inline">Pause Queued</span>
            </button>
          )}
          <button
            onClick={handleResumeAll}
            className="flex items-center justify-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-2 text-sm text-white transition-colors hover:bg-[var(--accent-hover)] sm:py-1.5"
            title="Resume Paused"
          >
            <Play size={18} className="sm:h-[14px] sm:w-[14px]" />
            <span className="hidden sm:inline">Resume Paused</span>
          </button>
          <button
            onClick={handleCancelAll}
            className="flex items-center justify-center gap-1.5 rounded-md bg-[var(--error)] px-3 py-2 text-sm text-white transition-colors hover:opacity-90 sm:py-1.5"
            title="Cancel Queued"
          >
            <Ban size={18} className="sm:h-[14px] sm:w-[14px]" />
            <span className="hidden sm:inline">Cancel Queued</span>
          </button>
          <button
            onClick={handleRetryFailed}
            className="flex items-center justify-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--foreground)] transition-colors hover:bg-[var(--card-hover)] sm:py-1.5"
            title="Retry Failed"
          >
            <RotateCcw size={18} className="sm:h-[14px] sm:w-[14px]" />
            <span className="hidden sm:inline">Retry Failed</span>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
        <StatCard
          label="Syncs"
          value={stats?.pending_sync ?? 0}
          running={stats?.running_sync ?? 0}
          icon={RefreshCw}
          paused={syncPaused}
          onPause={handlePauseSync}
          onResume={handleResumeSync}
        />
        <StatCard
          label="Downloads"
          value={stats?.pending_download ?? 0}
          running={stats?.running_download ?? 0}
          icon={Download}
          paused={downloadPaused}
          schedulePaused={schedulePaused}
          onPause={handlePauseDownload}
          onResume={handleResumeDownload}
        />
      </div>

      {/* Filter */}
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          {[
            'all',
            'sync',
            'download',
            'queued',
            'paused',
            'running',
            'completed',
            'failed',
            'cancelled',
          ].map((f) => (
            <button
              key={f}
              onClick={() => handleFilterChange(f)}
              className={clsx(
                'rounded-md px-3 py-2 text-sm transition-colors sm:py-1.5',
                filter === f
                  ? 'bg-[var(--accent)] text-white'
                  : 'border border-[var(--border)] bg-[var(--card)] text-[var(--muted)] hover:text-[var(--foreground)]'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="relative w-full sm:w-auto">
            <Search
              size={14}
              className="absolute top-1/2 left-3 -translate-y-1/2 text-[var(--muted)]"
            />
            <input
              type="text"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] py-1.5 pr-3 pl-8 text-sm focus:border-[var(--accent)] focus:outline-none sm:w-64"
            />
          </div>
          <Select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setCurrentPage(1)
            }}
            fullWidth={false}
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size} rows
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Tasks */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="border-b border-[var(--border)] p-4">
          <h2 className="font-medium">Tasks ({total})</h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {tasks.length === 0 ? (
            <EmptyState message="No tasks found" />
          ) : (
            tasks.map((task) => <TaskRow key={task.id} task={task} onAction={handleTaskAction} />)
          )}
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  running,
  icon: Icon,
  paused,
  schedulePaused,
  onPause,
  onResume,
}: {
  label: string
  value: number
  running: number
  icon: React.ComponentType<{ size?: number; className?: string }>
  paused: boolean
  schedulePaused?: boolean
  onPause: () => void
  onResume: () => void
}) {
  const effectivelyPaused = paused || schedulePaused

  return (
    <div
      className={clsx(
        'card-elevated rounded-xl',
        effectivelyPaused && 'border-[var(--warning)]/50'
      )}
    >
      <div className="flex items-center justify-between border-b border-[var(--border)] p-4">
        <div className="flex items-center gap-2">
          <div
            className={clsx(
              'rounded-lg p-2',
              effectivelyPaused ? 'bg-[var(--warning-muted)]' : 'bg-[var(--accent-muted)]'
            )}
          >
            <Icon
              size={18}
              className={effectivelyPaused ? 'text-[var(--warning)]' : 'text-[var(--accent)]'}
            />
          </div>
          <div>
            <p className="text-sm font-medium">{label}</p>
            {schedulePaused && !paused && (
              <span className="text-xs text-[var(--warning)]">Schedule paused</span>
            )}
            {paused && <span className="text-xs text-[var(--warning)]">Manually paused</span>}
          </div>
        </div>
        {paused ? (
          <button onClick={onResume} className="btn btn-primary py-1.5 text-xs">
            <Play size={12} />
            Resume
          </button>
        ) : schedulePaused ? null : (
          <button onClick={onPause} className="btn btn-secondary py-1.5 text-xs">
            <Pause size={12} />
            Pause
          </button>
        )}
      </div>
      <div className="flex items-center gap-6 p-4">
        <div className="flex-1">
          <p className="text-xs font-medium tracking-wide text-[var(--muted)] uppercase">Queued</p>
          <p className="mt-1 text-3xl font-bold text-[var(--warning)] tabular-nums">{value}</p>
        </div>
        <div className="flex-1">
          <p className="text-xs font-medium tracking-wide text-[var(--muted)] uppercase">Running</p>
          <p className="mt-1 text-3xl font-bold text-[var(--accent)] tabular-nums">{running}</p>
        </div>
      </div>
    </div>
  )
}

function TaskRow({
  task,
  onAction,
}: {
  task: Task
  onAction: (taskId: number, action: 'retry' | 'pause' | 'resume' | 'cancel') => void
}) {
  const [expanded, setExpanded] = useState(false)
  const linkHref =
    task.task_type === 'sync' ? `/lists/${task.entity_id}` : `/videos/${task.entity_id}`

  return (
    <div className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div onClick={() => setExpanded(!expanded)} className="shrink-0 cursor-pointer">
            <TaskStatusIcon status={task.status} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">
              <span className="cursor-default" onClick={() => setExpanded(!expanded)}>
                {task.task_type === 'sync' ? 'Sync' : 'Download'} •
              </span>{' '}
              <Link href={linkHref} className="transition-colors hover:text-[var(--accent)]">
                {task.entity_name || `#${task.entity_id}`}
              </Link>
            </p>
            <p className="truncate text-xs text-[var(--muted)]">
              Started{' '}
              {new Date(task.created_at).toLocaleString(undefined, {
                dateStyle: 'medium',
                timeStyle: 'short',
              })}
              {task.completed_at &&
                ` • Completed ${new Date(task.completed_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={clsx(
              'cursor-default rounded px-2 py-1 text-xs',
              task.status === 'completed' && 'bg-[var(--success)]/20 text-[var(--success)]',
              task.status === 'failed' && 'bg-[var(--error)]/20 text-[var(--error)]',
              task.status === 'running' && 'bg-[var(--accent)]/20 text-[var(--accent)]',
              task.status === 'pending' && 'bg-[var(--warning)]/20 text-[var(--warning)]',
              task.status === 'paused' && 'bg-[var(--muted)]/20 text-[var(--muted)]',
              task.status === 'cancelled' && 'bg-[var(--border)] text-[var(--muted)]'
            )}
          >
            {task.status === 'pending' ? 'queued' : task.status}
          </span>
          {task.status === 'pending' && (
            <>
              <button
                onClick={() => onAction(task.id, 'pause')}
                className="rounded-md p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]"
                title="Pause"
              >
                <Pause size={14} />
              </button>
              <button
                onClick={() => onAction(task.id, 'cancel')}
                className="rounded-md p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--error)]"
                title="Cancel"
              >
                <Square size={14} />
              </button>
            </>
          )}
          {task.status === 'paused' && (
            <>
              <button
                onClick={() => onAction(task.id, 'resume')}
                className="rounded-md p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--accent)]"
                title="Resume"
              >
                <Play size={14} />
              </button>
              <button
                onClick={() => onAction(task.id, 'cancel')}
                className="rounded-md p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--error)]"
                title="Cancel"
              >
                <Square size={14} />
              </button>
            </>
          )}
          {(task.status === 'failed' ||
            task.status === 'completed' ||
            task.status === 'cancelled') && (
            <button
              onClick={() => onAction(task.id, 'retry')}
              className="rounded-md p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]"
              title="Retry"
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      </div>
      {expanded && task.error && (
        <div className="mt-3 rounded bg-[var(--error)]/10 p-3 text-sm text-[var(--error)]">
          {task.error}
        </div>
      )}
      {expanded && task.logs && task.logs.length > 0 && (
        <div className="mt-3 max-h-40 space-y-1 overflow-y-auto rounded bg-[var(--background)] p-3 font-mono text-xs">
          {task.logs.map((log) => (
            <div
              key={log.id}
              className={clsx(
                log.level === 'error' && 'text-[var(--error)]',
                log.level === 'warning' && 'text-[var(--warning)]',
                log.level === 'info' && 'text-[var(--muted)]'
              )}
            >
              [{new Date(log.created_at).toLocaleTimeString()}] {log.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
