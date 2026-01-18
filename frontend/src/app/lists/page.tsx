'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  api,
  VideoList,
  Profile,
  TasksPaginatedResponse,
  getListsStreamUrl,
  getTasksStreamUrl,
} from '@/lib/api'
import { useEventSource } from '@/lib/useEventSource'
import { Plus, RefreshCw, Trash2, Edit2, ExternalLink, Loader2, Search } from 'lucide-react'
import { clsx } from 'clsx'
import Link from 'next/link'
import { ListForm } from '@/components/ListForm'
import { Pagination } from '@/components/Pagination'
import { Select } from '@/components/Select'
import { ExtractorIcon } from '@/components/ExtractorIcon'
import { PAGE_SIZE_OPTIONS, DEFAULT_PAGE_SIZE } from '@/lib/utils'

export default function ListsPage() {
  const [lists, setLists] = useState<VideoList[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const [syncingIds, setSyncingIds] = useState<Set<number>>(new Set())
  const [queuedIds, setQueuedIds] = useState<Set<number>>(new Set())
  const [syncingAll, setSyncingAll] = useState(false)
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [currentPage, setCurrentPage] = useState(1)

  const handleListsMessage = useCallback((data: VideoList[]) => {
    setLists(data)
    setLoading(false)
  }, [])

  const handleListsError = useCallback(() => {
    api
      .getLists()
      .then((data) => {
        setLists(data)
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to fetch lists:', err)
        setLoading(false)
      })
  }, [])

  const handleTasksMessage = useCallback((data: TasksPaginatedResponse) => {
    const tasks = data.tasks
    const runningIds = new Set(tasks.filter((t) => t.status === 'running').map((t) => t.entity_id))
    const pendingIds = new Set(tasks.filter((t) => t.status === 'pending').map((t) => t.entity_id))
    setSyncingIds(runningIds)
    setQueuedIds(pendingIds)
  }, [])

  useEventSource(getListsStreamUrl(), handleListsMessage, handleListsError)
  // Fetch only active (pending/running) sync tasks
  useEventSource(
    getTasksStreamUrl({ type: 'sync', status: 'active', pageSize: 100 }),
    handleTasksMessage
  )

  // Fetch profiles and poll for changes (they may be added via API)
  useEffect(() => {
    const fetchProfiles = () => {
      api.getProfiles().then(setProfiles).catch(console.error)
    }

    fetchProfiles()

    // Poll for profile changes every 5 seconds if no profiles exist
    const interval = setInterval(() => {
      if (profiles.length === 0) {
        fetchProfiles()
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [profiles.length])

  const handleSync = async (listId: number) => {
    setQueuedIds((prev) => new Set(prev).add(listId))
    try {
      await api.triggerListSync(listId)
    } catch (err) {
      console.error('Failed to sync:', err)
      setQueuedIds((prev) => {
        const next = new Set(prev)
        next.delete(listId)
        return next
      })
    }
  }

  const handleSyncAll = async () => {
    setSyncingAll(true)
    try {
      await api.triggerAllSyncs()
    } catch (err) {
      console.error('Failed to sync all:', err)
    } finally {
      setSyncingAll(false)
    }
  }

  const handleDelete = async (list: VideoList) => {
    if (!confirm(`Delete "${list.name}"? This will also delete all associated videos.`)) return
    try {
      await api.deleteList(list.id)
      // SSE will update the list with deleting=true, no need to manually update
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete list'
      alert(message)
      console.error('Failed to delete:', err)
    }
  }

  const handleSave = async (data: Partial<VideoList>, id?: number) => {
    try {
      if (id) {
        const updated = await api.updateList(id, data)
        setLists(lists.map((l) => (l.id === updated.id ? updated : l)))
      } else {
        const created = await api.createList(data)
        setLists([...lists, created])
      }
      setEditingId(null)
    } catch (err) {
      console.error('Failed to save:', err)
    }
  }

  const filteredLists = lists
    .filter((list) => {
      if (!search) return true
      const searchLower = search.toLowerCase()
      return list.name?.toLowerCase().includes(searchLower)
    })
    .sort((a, b) => (a.name || '').localeCompare(b.name || ''))

  const totalPages = Math.ceil(filteredLists.length / pageSize)
  const paginatedLists = filteredLists.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  // Reset to page 1 when search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [search])

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
        <h1 className="text-2xl font-semibold">Lists</h1>
        {profiles.length > 0 && (
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search
                size={14}
                className="absolute top-1/2 left-3 -translate-y-1/2 text-[var(--muted)]"
              />
              <input
                type="text"
                placeholder="Search lists..."
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
            {lists.length > 0 && (
              <button
                onClick={handleSyncAll}
                disabled={syncingAll}
                className="flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--foreground)] transition-colors hover:bg-[var(--card-hover)] disabled:opacity-50"
              >
                <RefreshCw size={14} className={syncingAll ? 'animate-spin' : ''} />
                Sync All
              </button>
            )}
            {editingId !== 'new' && (
              <button
                onClick={() => setEditingId('new')}
                className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm text-white transition-colors hover:bg-[var(--accent-hover)]"
              >
                <Plus size={14} />
                Add List
              </button>
            )}
          </div>
        )}
      </div>

      {profiles.length === 0 ? (
        <div className="rounded-md border border-[var(--warning)]/30 bg-[var(--warning)]/10 p-4">
          <p className="text-sm text-[var(--warning)]">
            You need to create a profile before adding lists.{' '}
            <Link href="/profiles" className="underline">
              Create one now
            </Link>
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {editingId === 'new' && (
            <ListForm
              profiles={profiles}
              onSave={(data) => handleSave(data)}
              onCancel={() => setEditingId(null)}
            />
          )}

          {filteredLists.length === 0 && editingId !== 'new' ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-8 text-center">
              <p className="text-[var(--muted)]">
                {search ? 'No lists match your search.' : 'No lists yet. Add one to get started.'}
              </p>
            </div>
          ) : (
            <>
              <div className="grid gap-4">
                {paginatedLists.map((list) =>
                  editingId === list.id ? (
                    <ListForm
                      key={list.id}
                      list={list}
                      profiles={profiles}
                      onSave={(data) => handleSave(data, list.id)}
                      onCancel={() => setEditingId(null)}
                    />
                  ) : (
                    <ListCard
                      key={list.id}
                      list={list}
                      profiles={profiles}
                      syncing={syncingIds.has(list.id)}
                      queued={queuedIds.has(list.id)}
                      onSync={() => handleSync(list.id)}
                      onEdit={() => setEditingId(list.id)}
                      onDelete={() => handleDelete(list)}
                    />
                  )
                )}
              </div>
              {totalPages > 1 && (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
                  <Pagination
                    currentPage={currentPage}
                    totalPages={totalPages}
                    onPageChange={setCurrentPage}
                  />
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ListCard({
  list,
  profiles,
  syncing,
  queued,
  onSync,
  onEdit,
  onDelete,
}: {
  list: VideoList
  profiles: Profile[]
  syncing: boolean
  queued: boolean
  onSync: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const profile = profiles.find((p) => p.id === list.profile_id)
  const isDeleting = list.deleting
  const isSyncing = syncing
  const _isBusy = isDeleting || isSyncing || queued
  void _isBusy // Suppress unused variable warning

  return (
    <div
      className={clsx(
        'rounded-lg border bg-[var(--card)] p-4',
        isDeleting && 'border-[var(--error)]/50 opacity-60',
        isSyncing && !isDeleting && 'border-[var(--accent)]/50',
        !isDeleting && !isSyncing && 'border-[var(--border)]'
      )}
    >
      <div className="flex gap-4">
        {list.thumbnail && (
          <Link
            href={`/lists/${list.id}`}
            className={clsx('flex-shrink-0', isDeleting && 'pointer-events-none')}
          >
            <img
              src={list.thumbnail}
              alt={list.name}
              className="h-20 w-20 rounded-lg object-cover"
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          </Link>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <ExtractorIcon extractor={list.extractor} size="md" />
                <Link
                  href={`/lists/${list.id}`}
                  className={clsx(
                    'font-medium transition-colors hover:text-[var(--accent)]',
                    isDeleting && 'pointer-events-none'
                  )}
                >
                  {list.name}
                </Link>
                {isDeleting ? (
                  <span className="flex items-center gap-1 rounded bg-[var(--error)]/20 px-2 py-0.5 text-xs text-[var(--error)]">
                    <Loader2 size={10} className="animate-spin" />
                    Deleting...
                  </span>
                ) : syncing ? (
                  <span className="flex items-center gap-1 rounded bg-[var(--accent)]/20 px-2 py-0.5 text-xs text-[var(--accent)]">
                    <Loader2 size={10} className="animate-spin" />
                    Syncing...
                  </span>
                ) : queued ? (
                  <span className="flex items-center gap-1 rounded bg-[var(--warning)]/20 px-2 py-0.5 text-xs text-[var(--warning)]">
                    Sync Queued
                  </span>
                ) : (
                  <>
                    <span
                      className={clsx(
                        'rounded px-2 py-0.5 text-xs',
                        list.enabled
                          ? 'bg-[var(--success)]/20 text-[var(--success)]'
                          : 'bg-[var(--muted)]/20 text-[var(--muted)]'
                      )}
                    >
                      {list.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                    {!list.auto_download && (
                      <span className="rounded bg-[var(--warning)]/20 px-2 py-0.5 text-xs text-[var(--warning)]">
                        Manual DL
                      </span>
                    )}
                    <span className="rounded bg-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted)]">
                      {list.list_type}
                    </span>
                  </>
                )}
              </div>
              <a
                href={list.url}
                target="_blank"
                rel="noopener noreferrer"
                className={clsx(
                  'mt-1 inline-flex items-center gap-1 text-sm text-[var(--muted)] hover:text-[var(--foreground)]',
                  isDeleting && 'pointer-events-none'
                )}
              >
                {list.url.length > 60 ? list.url.slice(0, 60) + '...' : list.url}
                <ExternalLink size={12} />
              </a>
              <div className="mt-2 flex items-center text-xs text-[var(--muted)]">
                <span className="mr-2 after:ml-2 after:content-['•']">
                  Profile: {profile?.name || 'Unknown'}
                </span>
                <span className="capitalize">Sync: {list.sync_frequency}</span>
                {list.last_synced && (
                  <span className="capitalize before:mr-2 before:ml-2 before:content-['•']">
                    Last synced:{' '}
                    {new Date(list.last_synced).toLocaleString(undefined, {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </span>
                )}
              </div>
            </div>
            {!isDeleting && (
              <div className="ml-4 flex items-center gap-2">
                <button
                  onClick={onSync}
                  disabled={syncing || queued}
                  className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)] disabled:opacity-50"
                  title="Sync now"
                >
                  <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                </button>
                <button
                  onClick={onEdit}
                  disabled={isSyncing}
                  className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)] disabled:opacity-50"
                  title="Edit"
                >
                  <Edit2 size={16} />
                </button>
                <button
                  onClick={onDelete}
                  disabled={isSyncing}
                  className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--error)] disabled:opacity-50"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
