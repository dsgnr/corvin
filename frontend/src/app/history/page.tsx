'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { api, HistoryEntry, HistoryPaginatedResponse, getHistoryStreamUrl } from '@/lib/api'
import { useEventSource } from '@/lib/useEventSource'
import {
  Loader2,
  ListVideo,
  FolderCog,
  Film,
  RefreshCw,
  Download,
  Trash2,
  Plus,
  Edit2,
  Search,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Pagination } from '@/components/Pagination'
import { Select } from '@/components/Select'
import Link from 'next/link'
import { PAGE_SIZE_OPTIONS, DEFAULT_PAGE_SIZE } from '@/lib/utils'

const actionIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  profile_created: Plus,
  profile_updated: Edit2,
  profile_deleted: Trash2,
  list_created: Plus,
  list_updated: Edit2,
  list_deleted: Trash2,
  list_sync_started: RefreshCw,
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
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)

  // Debounce search input and reset page
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== debouncedSearch) {
        setDebouncedSearch(search)
        setCurrentPage(1)
        setLoading(true)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [search, debouncedSearch])

  // Set loading when page changes
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page)
    setLoading(true)
  }, [])

  // Build SSE stream URL with current filters
  const streamUrl = useMemo(() => {
    const params: {
      entity_type?: string
      search?: string
      page: number
      page_size: number
    } = {
      page: currentPage,
      page_size: pageSize,
    }
    if (filter !== 'all') {
      params.entity_type = filter
    }
    if (debouncedSearch) {
      params.search = debouncedSearch
    }
    return getHistoryStreamUrl(params)
  }, [filter, debouncedSearch, currentPage, pageSize])

  // Handle SSE message with paginated response
  const handleMessage = useCallback((data: HistoryPaginatedResponse) => {
    setEntries(data.entries)
    setTotal(data.total)
    setTotalPages(data.total_pages)
    setLoading(false)
  }, [])

  // Fallback to REST API on SSE error
  const handleError = useCallback(() => {
    const params: {
      page: number
      pageSize: number
      entity_type?: string
      search?: string
    } = {
      page: currentPage,
      pageSize: pageSize,
    }
    if (filter !== 'all') {
      params.entity_type = filter
    }
    if (debouncedSearch) {
      params.search = debouncedSearch
    }
    api
      .getHistoryPaginated(params)
      .then((data) => {
        setEntries(data.entries)
        setTotal(data.total)
        setTotalPages(data.total_pages)
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to fetch history:', err)
        setLoading(false)
      })
  }, [currentPage, pageSize, filter, debouncedSearch])

  useEventSource(streamUrl, handleMessage, handleError)

  // Handle filter change with page reset
  const handleFilterChange = useCallback((newFilter: string) => {
    setFilter(newFilter)
    setCurrentPage(1)
    setLoading(true)
  }, [])

  const formatAction = (action: string) => {
    return action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
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

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">History</h1>
      </div>

      {/* Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-2">
          {['all', 'profile', 'list', 'video'].map((f) => (
            <button
              key={f}
              onClick={() => handleFilterChange(f)}
              className={clsx(
                'rounded-md px-3 py-1.5 text-sm transition-colors',
                filter === f
                  ? 'bg-[var(--accent)] text-white'
                  : 'border border-[var(--border)] bg-[var(--card)] text-[var(--prose-color)] hover:text-[var(--foreground)]'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search
              size={14}
              className="absolute top-1/2 left-3 -translate-y-1/2 text-[var(--muted)]"
            />
            <input
              type="text"
              placeholder="Search history..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-64 rounded-md border border-[var(--border)] bg-[var(--background)] py-1.5 pr-3 pl-8 text-sm focus:border-[var(--accent)] focus:outline-none"
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

      {/* Entries */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
        <div className="flex items-center justify-between border-b border-[var(--border)] p-4">
          <h2 className="font-medium">
            Entries ({loading ? <Loader2 size={14} className="inline-block animate-spin" /> : total}
            )
          </h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {loading ? (
            <div className="flex items-center justify-center p-4">
              <Loader2 className="animate-spin text-[var(--muted)]" size={24} />
            </div>
          ) : entries.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">No history entries</p>
          ) : (
            entries.map((entry) => {
              const ActionIcon = actionIcons[entry.action] || RefreshCw
              const EntityIcon = entityIcons[entry.entity_type] || Film
              const details = getDetails(entry.details)
              const isError = entry.action.includes('failed')
              const isSuccess =
                entry.action.includes('completed') || entry.action.includes('created')

              // Determine link targets based on entity type and details
              const listId =
                entry.entity_type === 'list'
                  ? entry.entity_id
                  : (details.list_id as number | undefined)
              const videoId =
                entry.entity_type === 'video' && entry.entity_id ? entry.entity_id : undefined
              const profileId =
                entry.entity_type === 'profile' && entry.entity_id ? entry.entity_id : undefined

              return (
                <div key={entry.id} className="flex items-start gap-3 p-4">
                  <div
                    className={clsx(
                      'rounded-md p-2',
                      isError && 'bg-[var(--error)]/10',
                      isSuccess && 'bg-[var(--success)]/10',
                      !isError && !isSuccess && 'bg-[var(--border)]'
                    )}
                  >
                    <ActionIcon
                      size={16}
                      className={clsx(
                        isError && 'text-[var(--error)]',
                        isSuccess && 'text-[var(--success)]',
                        !isError && !isSuccess && 'text-[var(--muted)]'
                      )}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{formatAction(entry.action)}</span>
                      <span className="flex items-center gap-1 text-xs text-[var(--muted)]">
                        <EntityIcon size={12} />
                        {entry.entity_type}
                        {entry.entity_id && ` #${entry.entity_id}`}
                      </span>
                    </div>
                    {Object.keys(details).length > 0 && (
                      <p className="mt-1 text-xs text-[var(--muted)]">
                        {'name' in details && profileId && (
                          <Link
                            href={`/profiles?edit=${profileId}`}
                            className="transition-colors hover:text-[var(--accent)]"
                          >
                            {String(details.name)}
                          </Link>
                        )}
                        {'name' in details && listId && !profileId && (
                          <Link
                            href={`/lists/${listId}`}
                            className="transition-colors hover:text-[var(--accent)]"
                          >
                            {String(details.name)}
                          </Link>
                        )}
                        {'name' in details && !listId && !profileId && (
                          <span>{String(details.name)}</span>
                        )}
                        {'name' in details && 'title' in details && <span className="mx-1">•</span>}
                        {'title' in details && videoId && (
                          <Link
                            href={`/videos/${videoId}`}
                            className="transition-colors hover:text-[var(--accent)]"
                          >
                            {String(details.title)}
                          </Link>
                        )}
                        {'title' in details && !videoId && listId && (
                          <Link
                            href={`/lists/${listId}`}
                            className="transition-colors hover:text-[var(--accent)]"
                          >
                            {String(details.title)}
                          </Link>
                        )}
                        {'title' in details && !videoId && !listId && (
                          <span>{String(details.title)}</span>
                        )}
                        {'url' in details && (
                          <span className="block truncate">{String(details.url)}</span>
                        )}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {new Date(entry.created_at).toLocaleString(undefined, {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      })}
                    </p>
                  </div>
                </div>
              )
            })
          )}
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={handlePageChange}
        />
      </div>
    </div>
  )
}
