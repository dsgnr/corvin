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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="flex gap-2">
          <button
            onClick={handleSyncAll}
            disabled={syncing}
            className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--foreground)] transition-colors hover:bg-[var(--card-hover)] disabled:opacity-50"
          >
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            Sync All
          </button>
          <button
            onClick={handleDownloadPending}
            disabled={downloading}
            className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            <Download size={14} className={downloading ? 'animate-bounce' : ''} />
            Download Pending
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
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
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="border-b border-[var(--border)] p-4">
          <h2 className="font-medium">Recent Tasks</h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {recentTasks.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">No recent tasks</p>
          ) : (
            recentTasks.map((task) => {
              const linkHref =
                task.task_type === 'sync' ? `/lists/${task.entity_id}` : `/videos/${task.entity_id}`
              return (
                <div key={task.id} className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <TaskStatusIcon status={task.status} />
                    <div>
                      <p className="text-sm font-medium">
                        {task.task_type === 'sync' ? 'Sync' : 'Download'} •{' '}
                        <Link
                          href={linkHref}
                          className="transition-colors hover:text-[var(--accent)]"
                        >
                          {task.entity_name || `#${task.entity_id}`}
                        </Link>
                      </p>
                      <p className="text-xs text-[var(--muted)]">
                        {new Date(task.created_at).toLocaleString(undefined, {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })}
                      </p>
                    </div>
                  </div>
                  <span
                    className={clsx(
                      'rounded px-2 py-1 text-xs',
                      task.status === 'cancelled' && 'bg-[var(--muted)]/20 text-[var(--muted)]',
                      task.status === 'completed' && 'bg-[var(--success)]/20 text-[var(--success)]',
                      task.status === 'failed' && 'bg-[var(--error)]/20 text-[var(--error)]',
                      task.status === 'running' && 'bg-[var(--accent)]/20 text-[var(--accent)]',
                      task.status === 'paused' && 'bg-[var(--warning)]/20 text-[var(--warning)]',
                      task.status === 'pending' && 'bg-[var(--warning)]/20 text-[var(--warning)]'
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
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-[var(--muted)]">{title}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">{subtitle}</p>
        </div>
        <Icon size={24} className="text-[var(--muted)]" />
      </div>
    </div>
  )
}
