'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, TaskStats, Task, VideoList, getTaskStatsStreamUrl } from '@/lib/api'
import { useEventSource } from '@/lib/useEventSource'
import { RefreshCw, Play, Download, ListVideo, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import Link from 'next/link'
import { TaskStatusIcon } from '@/components/TaskStatusIcon'

export default function Dashboard() {
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [recentTasks, setRecentTasks] = useState<Task[]>([])
  const [lists, setLists] = useState<VideoList[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const fetchData = async () => {
    try {
      const [tasksData, listsData] = await Promise.all([
        api.getTasksPaginated({ page: 1, pageSize: 10 }),
        api.getLists(),
      ])
      setRecentTasks(tasksData.tasks)
      setLists(listsData)
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleStatsMessage = useCallback((data: TaskStats) => {
    setStats(data)
  }, [])

  const handleStatsError = useCallback(() => {
    api.getTaskStats().then(setStats).catch(console.error)
  }, [])

  useEventSource(getTaskStatsStreamUrl(), handleStatsMessage, handleStatsError)

  const handleSyncAll = async () => {
    setSyncing(true)
    try {
      await api.triggerAllSyncs()
      await fetchData()
    } catch (err) {
      console.error('Failed to trigger sync:', err)
    } finally {
      setSyncing(false)
    }
  }

  const handleDownloadPending = async () => {
    setDownloading(true)
    try {
      await api.triggerPendingDownloads()
      await fetchData()
    } catch (err) {
      console.error('Failed to trigger downloads:', err)
    } finally {
      setDownloading(false)
    }
  }

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
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleSyncAll}
            disabled={syncing}
            className="btn btn-secondary"
            title="Sync All"
          >
            <RefreshCw
              size={18}
              className={clsx('sm:h-[14px] sm:w-[14px]', syncing && 'animate-spin')}
            />
            <span className="hidden sm:inline">Sync All</span>
          </button>
          <button
            onClick={handleDownloadPending}
            disabled={downloading}
            className="btn btn-primary"
            title="Download Pending"
          >
            <Download
              size={18}
              className={clsx('sm:h-[14px] sm:w-[14px]', downloading && 'animate-bounce')}
            />
            <span className="hidden sm:inline">Download Pending</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard
          title="Lists"
          value={lists.length}
          subtitle={`${lists.filter((l) => l.enabled).length} enabled`}
          icon={ListVideo}
        />
        <StatCard
          title="Queued Syncs"
          value={stats?.pending_sync ?? 0}
          subtitle={`${stats?.running_sync ?? 0} running`}
          icon={RefreshCw}
        />
        <StatCard
          title="Queued Downloads"
          value={stats?.pending_download ?? 0}
          subtitle={`${stats?.running_download ?? 0} running`}
          icon={Download}
        />
        <StatCard
          title="Active Tasks"
          value={(stats?.running_sync ?? 0) + (stats?.running_download ?? 0)}
          subtitle="Currently processing"
          icon={Play}
        />
      </div>

      {/* Recent Tasks */}
      <div className="card-elevated overflow-hidden rounded-xl">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <h2 className="font-semibold">Recent Tasks</h2>
        </div>
        <div className="divide-y divide-[var(--border-subtle)]">
          {recentTasks.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-[var(--muted)]">No recent tasks</p>
          ) : (
            recentTasks.map((task) => {
              const linkHref =
                task.task_type === 'sync' ? `/lists/${task.entity_id}` : `/videos/${task.entity_id}`
              return (
                <div
                  key={task.id}
                  className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-[var(--card-hover)] sm:px-5"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="shrink-0">
                      <TaskStatusIcon status={task.status} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {task.task_type === 'sync' ? 'Sync' : 'Download'} •{' '}
                        <Link
                          href={linkHref}
                          className="transition-colors hover:text-[var(--accent)]"
                        >
                          {task.entity_name || `#${task.entity_id}`}
                        </Link>
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        {new Date(task.created_at).toLocaleString(undefined, {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })}
                      </p>
                    </div>
                  </div>
                  <span
                    className={clsx(
                      'badge shrink-0',
                      task.status === 'cancelled' && 'bg-[var(--muted)]/10 text-[var(--muted)]',
                      task.status === 'completed' &&
                        'bg-[var(--success-muted)] text-[var(--success)]',
                      task.status === 'failed' && 'bg-[var(--error-muted)] text-[var(--error)]',
                      task.status === 'running' && 'bg-[var(--accent-muted)] text-[var(--accent)]',
                      task.status === 'paused' && 'bg-[var(--warning-muted)] text-[var(--warning)]',
                      task.status === 'pending' && 'bg-[var(--warning-muted)] text-[var(--warning)]'
                    )}
                  >
                    {task.status === 'pending' ? 'queued' : task.status}
                  </span>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: {
  title: string
  value: number
  subtitle: string
  icon: React.ComponentType<{ size?: number; className?: string }>
}) {
  return (
    <div className="card-elevated card-interactive rounded-xl p-3 sm:p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium tracking-wide text-[var(--muted)] uppercase">
            {title}
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums sm:mt-2 sm:text-3xl">{value}</p>
          <p className="mt-1 truncate text-xs text-[var(--muted-foreground)]">{subtitle}</p>
        </div>
        <div className="shrink-0 rounded-lg bg-[var(--accent-muted)] p-1.5 sm:p-2">
          <Icon size={16} className="text-[var(--accent)] sm:h-5 sm:w-5" />
        </div>
      </div>
    </div>
  )
}
