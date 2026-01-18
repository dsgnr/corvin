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

  const handleTaskAction = async (taskId: number, action: 'retry' | 'pause' | 'resume' | 'cancel') => {
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

  // Handle filter change with page reset
  const handleFilterChange = useCallback((newFilter: string) => {
    setFilter(newFilter)
    setCurrentPage(1)
    setLoading(true)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <div className="flex gap-2">
          {hasPendingTasks && (
            <button
              onClick={handlePauseAll}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] text-[var(--foreground)] border border-[var(--border)] rounded-md transition-colors"
            >
              <Pause size={14} />
              Pause Queued
            </button>
          )}
          <button
            onClick={handleResumeAll}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors"
          >
            <Play size={14} />
            Resume Paused
          </button>
          <button
            onClick={handleCancelAll}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--error)] hover:opacity-90 text-white rounded-md transition-colors"
          >
            <Ban size={14} />
            Cancel Queued
          </button>
          <button
            onClick={handleRetryFailed}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] text-[var(--foreground)] border border-[var(--border)] rounded-md transition-colors"
          >
            <RotateCcw size={14} />
            Retry Failed
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
          onPause={handlePauseDownload}
          onResume={handleResumeDownload}
        />
      </div>

      {/* Filter */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-2 flex-wrap">
          {['all', 'sync', 'download', 'queued', 'paused', 'running', 'completed', 'failed', 'cancelled'].map((f) => (
            <button
              key={f}
              onClick={() => handleFilterChange(f)}
              className={clsx(
                'px-3 py-1.5 text-sm rounded-md transition-colors',
                filter === f
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--card)] text-[var(--muted)] hover:text-[var(--foreground)] border border-[var(--border)]'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)] w-64"
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
      <div className="bg-[var(--card)] rounded-lg border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-medium">Tasks ({total})</h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {tasks.length === 0 ? (
            <p className="p-4 text-[var(--muted)] text-sm">No tasks found</p>
          ) : (
            tasks.map((task) => (
              <TaskRow key={task.id} task={task} onAction={handleTaskAction} />
            ))
          )}
        </div>
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
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
  onPause,
  onResume,
}: {
  label: string
  value: number
  running: number
  icon: React.ComponentType<{ size?: number; className?: string }>
  paused: boolean
  onPause: () => void
  onResume: () => void
}) {
  return (
    <div
      className={clsx(
        'bg-[var(--card)] rounded-lg border p-4',
        paused ? 'border-[var(--warning)]' : 'border-[var(--border)]'
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon size={18} className={paused ? 'text-[var(--muted)]' : 'text-[var(--accent)]'} />
          <p className="text-sm font-medium">{label}</p>
          {paused && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--warning)]/20 text-[var(--warning)]">
              Paused
            </span>
          )}
        </div>
        {paused ? (
          <button
            onClick={onResume}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-[var(--accent)] text-white hover:opacity-90 transition-colors"
          >
            <Play size={12} />
            Resume
          </button>
        ) : (
          <button
            onClick={onPause}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded-md border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] hover:bg-[var(--card-hover)] transition-colors"
          >
            <Pause size={12} />
            Pause
          </button>
        )}
      </div>
      <div className="flex items-center gap-6">
        <div>
          <p className="text-xs text-[var(--muted)]">Queued</p>
          <p className="text-2xl font-semibold text-[var(--warning)]">{value}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--muted)]">Running</p>
          <p className="text-2xl font-semibold text-[var(--accent)]">{running}</p>
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
  const linkHref = task.task_type === 'sync' ? `/lists/${task.entity_id}` : `/videos/${task.entity_id}`

  return (
    <div className="p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div onClick={() => setExpanded(!expanded)} className="cursor-pointer">
            <TaskStatusIcon status={task.status} />
          </div>
          <div>
            <p className="text-sm font-medium">
              <span className="cursor-default" onClick={() => setExpanded(!expanded)}>
                {task.task_type === 'sync' ? 'Sync' : 'Download'} •
              </span>{' '}
              <Link
                href={linkHref}
                className="hover:text-[var(--accent)] transition-colors"
              >
                {task.entity_name || `#${task.entity_id}`}
              </Link>
            </p>
            <p className="text-xs text-[var(--muted)]">
              Started{' '}
              {new Date(task.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
              {task.completed_at &&
                ` • Completed ${new Date(task.completed_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'text-xs px-2 py-1 rounded cursor-default',
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
                className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                title="Pause"
              >
                <Pause size={14} />
              </button>
              <button
                onClick={() => onAction(task.id, 'cancel')}
                className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--error)] transition-colors"
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
                className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--accent)] transition-colors"
                title="Resume"
              >
                <Play size={14} />
              </button>
              <button
                onClick={() => onAction(task.id, 'cancel')}
                className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--error)] transition-colors"
                title="Cancel"
              >
                <Square size={14} />
              </button>
            </>
          )}
          {(task.status === 'failed' || task.status === 'completed' || task.status === 'cancelled') && (
            <button
              onClick={() => onAction(task.id, 'retry')}
              className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              title="Retry"
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      </div>
      {expanded && task.error && (
        <div className="mt-3 p-3 bg-[var(--error)]/10 rounded text-sm text-[var(--error)]">{task.error}</div>
      )}
      {expanded && task.logs && task.logs.length > 0 && (
        <div className="mt-3 space-y-1 text-xs font-mono bg-[var(--background)] rounded p-3 max-h-40 overflow-y-auto">
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
