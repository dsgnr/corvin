'use client'

import { useEffect, useState } from 'react'
import { api, HistoryEntry, getHistoryStreamUrl } from '@/lib/api'
import { Loader2, ListVideo, FolderCog, Film, RefreshCw, Download, Trash2, Plus, Edit2, Search } from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'
import { Select } from '@/components/Select'

const PAGE_SIZE_OPTIONS = [20, 50, 100]

const actionIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  profile_created: Plus,
  profile_updated: Edit2,
  profile_deleted: Trash2,
  list_created: Plus,
  list_updated: Edit2,
  list_deleted: Trash2,
  list_synced: RefreshCw,
  video_discovered: Film,
  video_download_started: Download,
  video_download_completed: Download,
  video_download_failed: Download,
  video_retry: RefreshCw,
}

const entityIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  profile: FolderCog,
  list: ListVideo,
  video: Film,
}

export default function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(20)
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    const eventSource = new EventSource(getHistoryStreamUrl({ limit: 200 }))

    eventSource.onmessage = (event) => {
      const data: HistoryEntry[] = JSON.parse(event.data)
      setEntries(data)
      setLoading(false)
    }

    eventSource.onerror = () => {
      // Fallback to regular fetch on SSE error
      api.getHistory({ limit: 200 }).then(data => {
        setEntries(data)
        setLoading(false)
      }).catch(err => {
        console.error('Failed to fetch history:', err)
        setLoading(false)
      })
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [])

  const filteredEntries = entries.filter(e => {
    if (filter !== 'all' && e.entity_type !== filter) return false
    if (search) {
      const searchLower = search.toLowerCase()
      const details = typeof e.details === 'string' ? e.details : JSON.stringify(e.details)
      return (
        e.action.toLowerCase().includes(searchLower) ||
        e.entity_type.toLowerCase().includes(searchLower) ||
        details.toLowerCase().includes(searchLower)
      )
    }
    return true
  })

  const totalPages = Math.ceil(filteredEntries.length / pageSize)
  const paginatedEntries = filteredEntries.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  // Reset to page 1 when filter or search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [filter, search])

  const formatAction = (action: string) => {
    return action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }

  const getDetails = (details: Record<string, unknown> | string): Record<string, unknown> => {
    if (typeof details === 'string') {
      try {
        return JSON.parse(details)
      } catch {
        return {}
      }
    }
    return details || {}
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
        <h1 className="text-2xl font-semibold">History</h1>
      </div>

      {/* Filter */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-2">
          {['all', 'profile', 'list', 'video'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                'px-3 py-1.5 text-sm rounded-md transition-colors',
                filter === f
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--card)] text-[var(--prose-color)] hover:text-[var(--foreground)] border border-[var(--border)]'
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
              placeholder="Search history..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)] w-64"
            />
          </div>
          <Select
            value={pageSize}
            onChange={e => {
              setPageSize(Number(e.target.value))
              setCurrentPage(1)
            }}
            fullWidth={false}
          >
            {PAGE_SIZE_OPTIONS.map(size => (
              <option key={size} value={size}>{size} rows</option>
            ))}
          </Select>
        </div>
      </div>

      {/* Entries */}
      <div className="bg-[var(--card)] rounded-lg border border-[var(--border)]">
        <div className="divide-y divide-[var(--border)]">
          {paginatedEntries.length === 0 ? (
            <p className="p-4 text-[var(--muted)] text-sm">No history entries</p>
          ) : (
            paginatedEntries.map(entry => {
              const ActionIcon = actionIcons[entry.action] || RefreshCw
              const EntityIcon = entityIcons[entry.entity_type] || Film
              const details = getDetails(entry.details)
              const isError = entry.action.includes('failed')
              const isSuccess = entry.action.includes('completed') || entry.action.includes('created')

              return (
                <div key={entry.id} className="p-4 flex items-start gap-3">
                  <div className={clsx(
                    'p-2 rounded-md',
                    isError && 'bg-[var(--error)]/10',
                    isSuccess && 'bg-[var(--success)]/10',
                    !isError && !isSuccess && 'bg-[var(--border)]'
                  )}>
                    <ActionIcon size={16} className={clsx(
                      isError && 'text-[var(--error)]',
                      isSuccess && 'text-[var(--success)]',
                      !isError && !isSuccess && 'text-[var(--muted)]'
                    )} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{formatAction(entry.action)}</span>
                      <span className="flex items-center gap-1 text-xs text-[var(--muted)]">
                        <EntityIcon size={12} />
                        {entry.entity_type}
                        {entry.entity_id && ` #${entry.entity_id}`}
                      </span>
                    </div>
                    {Object.keys(details).length > 0 && (
                      <p className="text-xs text-[var(--muted)] mt-1">
                        {'name' in details && <span className="pr-1 after:content-['•'] after:ml-1">{String(details.name)}</span>}
                        {'title' in details && <span>{String(details.title)}</span>}
                        {'url' in details && <span className="truncate block">{String(details.url)}</span>}
                      </p>
                    )}
                    <p className="text-xs text-[var(--muted)] mt-1">
                      {new Date(entry.created_at).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'})}
                    </p>
                  </div>
                </div>
              )
            })
          )}
        </div>
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
      </div>
    </div>
  )
}
