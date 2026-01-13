'use client'

import { useEffect, useState } from 'react'
import { api, TaskStats, Task, VideoList } from '@/lib/api'
import { RefreshCw, Play, Download, ListVideo, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

export default function Dashboard() {
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [recentTasks, setRecentTasks] = useState<Task[]>([])
  const [lists, setLists] = useState<VideoList[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const fetchData = async () => {
    try {
      const [statsData, tasksData, listsData] = await Promise.all([
        api.getTaskStats(),
        api.getTasks({ limit: 5 }),
        api.getLists(),
      ])
      setStats(statsData)
      setRecentTasks(tasksData)
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
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="flex gap-2">
          <button
            onClick={handleSyncAll}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            Sync All
          </button>
          <button
            onClick={handleDownloadPending}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--success)] hover:opacity-90 text-success rounded-md transition-colors disabled:opacity-50"
          >
            <Download size={14} className={downloading ? 'animate-bounce' : ''} />
            Download Pending
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Lists"
          value={lists.length}
          subtitle={`${lists.filter(l => l.enabled).length} enabled`}
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
      <div className="bg-[var(--card)] rounded-lg border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-medium">Recent Tasks</h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {recentTasks.length === 0 ? (
            <p className="p-4 text-[var(--muted)] text-sm">No recent tasks</p>
          ) : (
            recentTasks.map(task => (
              <div key={task.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <TaskStatusIcon status={task.status} />
                  <div>
                    <p className="text-sm font-medium">
                      {task.task_type === 'sync' ? 'Sync' : 'Download'} • {task.entity_name}
                    </p>
                    <p className="text-xs text-[var(--muted)]">
                      {new Date(task.created_at).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'})}
                    </p>
                  </div>
                </div>
                <span className={clsx(
                  'text-xs px-2 py-1 rounded',
                  task.status === 'completed' && 'bg-[var(--success)]/20 text-[var(--success)]',
                  task.status === 'failed' && 'bg-[var(--error)]/20 text-[var(--error)]',
                  task.status === 'running' && 'bg-[var(--accent)]/20 text-[var(--accent)]',
                  task.status === 'pending' && 'bg-[var(--warning)]/20 text-[var(--warning)]'
                )}>
                  {task.status === 'pending' ? 'queued' : task.status}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ title, value, subtitle, icon: Icon }: {
  title: string
  value: number
  subtitle: string
  icon: React.ComponentType<{ size?: number; className?: string }>
}) {
  return (
    <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-[var(--muted)]">{title}</p>
          <p className="text-2xl font-semibold mt-1">{value}</p>
          <p className="text-xs text-[var(--muted)] mt-1">{subtitle}</p>
        </div>
        <Icon size={24} className="text-[var(--muted)]" />
      </div>
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
