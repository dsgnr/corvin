'use client'

import { useEffect, useState } from 'react'
import { api, Task, TaskStats } from '@/lib/api'
import { Download, RefreshCw, Loader2, CheckCircle, XCircle, Clock, Play, RotateCcw } from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'

const PAGE_SIZE = 20

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [triggering, setTriggering] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)

  const fetchData = async () => {
    try {
      const [tasksData, statsData] = await Promise.all([
        api.getTasks({ limit: 100 }),
        api.getTaskStats(),
      ])
      setTasks(tasksData)
      setStats(statsData)
    } catch (err) {
      console.error('Failed to fetch tasks:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleDownloadPending = async () => {
    setTriggering(true)
    try {
      await api.triggerPendingDownloads()
      await fetchData()
    } catch (err) {
      console.error('Failed to trigger downloads:', err)
    } finally {
      setTriggering(false)
    }
  }

  const handleRetry = async (taskId: number) => {
    try {
      await api.retryTask(taskId)
      await fetchData()
    } catch (err) {
      console.error('Failed to retry task:', err)
    }
  }

  const filteredTasks = tasks
    .filter(t => {
      if (filter === 'all') return true
      if (filter === 'sync') return t.task_type === 'sync'
      if (filter === 'download') return t.task_type === 'download'
      if (filter === 'queued') return t.status === 'pending'
      return t.status === filter
    })
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const totalPages = Math.ceil(filteredTasks.length / PAGE_SIZE)
  const paginatedTasks = filteredTasks.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  // Reset to page 1 when filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [filter])

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
        <button
          onClick={handleDownloadPending}
          disabled={triggering}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--success)] hover:opacity-90 text-white rounded-md transition-colors disabled:opacity-50"
        >
          <Download size={14} className={triggering ? 'animate-bounce' : ''} />
          Download Queued
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Queued Syncs" value={stats?.pending_sync ?? 0} icon={RefreshCw} colour="warning" />
        <StatCard label="Running Syncs" value={stats?.running_sync ?? 0} icon={Play} colour="accent" />
        <StatCard label="Queued Downloads" value={stats?.pending_download ?? 0} icon={Clock} colour="warning" />
        <StatCard label="Running Downloads" value={stats?.running_download ?? 0} icon={Download} colour="accent" />
      </div>

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {['all', 'sync', 'download', 'queued', 'running', 'completed', 'failed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
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

      {/* Tasks */}
      <div className="bg-[var(--card)] rounded-lg border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-medium">Tasks ({filteredTasks.length})</h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {paginatedTasks.length === 0 ? (
            <p className="p-4 text-[var(--muted)] text-sm">No tasks found</p>
          ) : (
            paginatedTasks.map(task => (
              <TaskRow key={task.id} task={task} onRetry={() => handleRetry(task.id)} />
            ))
          )}
        </div>
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
      </div>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, colour }: {
  label: string
  value: number
  icon: React.ComponentType<{ size?: number; className?: string }>
  colour: 'accent' | 'success' | 'warning' | 'error'
}) {
  const colourClass = {
    accent: 'text-[var(--accent)]',
    success: 'text-[var(--success)]',
    warning: 'text-[var(--warning)]',
    error: 'text-[var(--error)]',
  }[colour]

  return (
    <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-[var(--muted)]">{label}</p>
          <p className={clsx('text-2xl font-semibold mt-1', colourClass)}>{value}</p>
        </div>
        <Icon size={20} className={colourClass} />
      </div>
    </div>
  )
}

function TaskRow({ task, onRetry }: { task: Task; onRetry: () => void }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <TaskStatusIcon status={task.status} />
          <div>
            <p className="text-sm font-medium">
              {task.task_type === 'sync' ? 'Sync' : 'Download'} • {task.entity_name || `#${task.entity_id}`}
            </p>
            <p className="text-xs text-[var(--muted)]">
              {new Date(task.created_at).toLocaleString()}
              {task.completed_at && ` • Completed ${new Date(task.completed_at).toLocaleString()}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={clsx(
            'text-xs px-2 py-1 rounded',
            task.status === 'completed' && 'bg-[var(--success)]/20 text-[var(--success)]',
            task.status === 'failed' && 'bg-[var(--error)]/20 text-[var(--error)]',
            task.status === 'running' && 'bg-[var(--accent)]/20 text-[var(--accent)]',
            task.status === 'pending' && 'bg-[var(--warning)]/20 text-[var(--warning)]'
          )}>
            {task.status === 'pending' ? 'queued' : task.status}
          </span>
          {(task.status === 'failed' || task.status === 'completed') && (
            <button
              onClick={onRetry}
              className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              title="Retry"
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      </div>
      {expanded && task.error && (
        <div className="mt-3 p-3 bg-[var(--error)]/10 rounded text-sm text-[var(--error)]">
          {task.error}
        </div>
      )}
      {expanded && task.logs && task.logs.length > 0 && (
        <div className="mt-3 space-y-1 text-xs font-mono bg-[var(--background)] rounded p-3 max-h-40 overflow-y-auto">
          {task.logs.map(log => (
            <div key={log.id} className={clsx(
              log.level === 'error' && 'text-[var(--error)]',
              log.level === 'warning' && 'text-[var(--warning)]',
              log.level === 'info' && 'text-[var(--muted)]'
            )}>
              [{new Date(log.created_at).toLocaleTimeString()}] {log.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TaskStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle size={18} className="text-[var(--success)]" />
    case 'failed':
      return <XCircle size={18} className="text-[var(--error)]" />
    case 'running':
      return <Loader2 size={18} className="text-[var(--accent)] animate-spin" />
    default:
      return <Clock size={18} className="text-[var(--warning)]" />
  }
}
