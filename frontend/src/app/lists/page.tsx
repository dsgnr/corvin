'use client'

import { useEffect, useState } from 'react'
import { api, VideoList, Profile, Task, getListsStreamUrl, getTasksStreamUrl } from '@/lib/api'
import { Plus, RefreshCw, Trash2, Edit2, ExternalLink, Loader2, Search } from 'lucide-react'
import { clsx } from 'clsx'
import Link from 'next/link'
import { ListForm } from '@/components/ListForm'
import { Pagination } from '@/components/Pagination'
import { Select } from '@/components/Select'

const PAGE_SIZE_OPTIONS = [10, 20, 50]

export default function ListsPage() {
  const [lists, setLists] = useState<VideoList[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const [syncingIds, setSyncingIds] = useState<Set<number>>(new Set())
  const [queuedIds, setQueuedIds] = useState<Set<number>>(new Set())
  const [syncingAll, setSyncingAll] = useState(false)
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(10)
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    // Set up SSE stream for lists
    const listsSource = new EventSource(getListsStreamUrl())

    listsSource.onmessage = (event) => {
      const data: VideoList[] = JSON.parse(event.data)
      setLists(data)
      setLoading(false)
    }

    listsSource.onerror = () => {
      // Fallback to regular fetch on SSE error
      api.getLists().then(data => {
        setLists(data)
        setLoading(false)
      }).catch(err => {
        console.error('Failed to fetch lists:', err)
        setLoading(false)
      })
      listsSource.close()
    }

    // Set up SSE stream for sync tasks
    const tasksSource = new EventSource(getTasksStreamUrl({ type: 'sync' }))

    tasksSource.onmessage = (event) => {
      const tasks: Task[] = JSON.parse(event.data)
      const runningIds = new Set(tasks.filter(t => t.status === 'running').map(t => t.entity_id))
      const pendingIds = new Set(tasks.filter(t => t.status === 'pending').map(t => t.entity_id))
      setSyncingIds(runningIds)
      setQueuedIds(pendingIds)
    }

    tasksSource.onerror = () => {
      tasksSource.close()
    }

    return () => {
      listsSource.close()
      tasksSource.close()
    }
  }, [])

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
    setQueuedIds(prev => new Set(prev).add(listId))
    try {
      await api.triggerListSync(listId)
    } catch (err) {
      console.error('Failed to sync:', err)
      setQueuedIds(prev => {
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
      setLists(lists.filter(l => l.id !== list.id))
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  const handleSave = async (data: Partial<VideoList>, id?: number) => {
    try {
      if (id) {
        const updated = await api.updateList(id, data)
        setLists(lists.map(l => l.id === updated.id ? updated : l))
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
    .filter(list => {
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
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Lists</h1>
        {profiles.length > 0 && (
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
              <input
                type="text"
                placeholder="Search lists..."
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
            {lists.length > 0 && (
              <button
                onClick={handleSyncAll}
                disabled={syncingAll}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--card)] hover:bg-[var(--card-hover)] text-[var(--foreground)] border border-[var(--border)] rounded-md transition-colors disabled:opacity-50"
              >
                <RefreshCw size={14} className={syncingAll ? 'animate-spin' : ''} />
                Sync All
              </button>
            )}
            {editingId !== 'new' && (
              <button
                onClick={() => setEditingId('new')}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors"
              >
                <Plus size={14} />
                Add List
              </button>
            )}
          </div>
        )}
      </div>

      {profiles.length === 0 ? (
        <div className="bg-[var(--warning)]/10 border border-[var(--warning)]/30 rounded-md p-4">
          <p className="text-sm text-[var(--warning)]">
            You need to create a profile before adding lists.{' '}
            <Link href="/profiles" className="underline">Create one now</Link>
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
            <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-8 text-center">
              <p className="text-[var(--muted)]">{search ? 'No lists match your search.' : 'No lists yet. Add one to get started.'}</p>
            </div>
          ) : (
            <>
              <div className="grid gap-4">
                {paginatedLists.map(list => (
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
                ))}
              </div>
              {totalPages > 1 && (
                <div className="bg-[var(--card)] rounded-lg border border-[var(--border)]">
                  <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ListCard({ list, profiles, syncing, queued, onSync, onEdit, onDelete }: {
  list: VideoList
  profiles: Profile[]
  syncing: boolean
  queued: boolean
  onSync: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const profile = profiles.find(p => p.id === list.profile_id)

  return (
    <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
      <div className="flex gap-4">
        {list.thumbnail && (
          <Link href={`/lists/${list.id}`} className="flex-shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={list.thumbnail}
              alt={list.name}
              className="w-20 h-20 rounded-lg object-cover"
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          </Link>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                {list.extractor?.toLowerCase().includes('youtube') && (
                  <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0" fill="#FF0000">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                  </svg>
                )}
                <Link href={`/lists/${list.id}`} className="font-medium hover:text-[var(--accent)] transition-colors">
                  {list.name}
                </Link>
                <span className={clsx(
                  'text-xs px-2 py-0.5 rounded',
                  list.enabled ? 'bg-[var(--success)]/20 text-[var(--success)]' : 'bg-[var(--muted)]/20 text-[var(--muted)]'
                )}>
                  {list.enabled ? 'Enabled' : 'Disabled'}
                </span>
                {!list.auto_download && (
                  <span className="text-xs px-2 py-0.5 rounded bg-[var(--warning)]/20 text-[var(--warning)]">
                    Manual DL
                  </span>
                )}
                <span className="text-xs px-2 py-0.5 rounded bg-[var(--border)] text-[var(--muted)]">
                  {list.list_type}
                </span>
              </div>
              <a
                href={list.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] inline-flex items-center gap-1 mt-1"
              >
                {list.url.length > 60 ? list.url.slice(0, 60) + '...' : list.url}
                <ExternalLink size={12} />
              </a>
              <div className="flex items-center mt-2 text-xs text-[var(--muted)]">
                <span className="after:content-['•'] after:ml-2 mr-2">Profile: {profile?.name || 'Unknown'}</span>
                <span className="capitalize">Sync: {list.sync_frequency}</span>
                {list.last_synced && (
                  <span className="before:content-['•'] before:ml-2 before:mr-2 capitalize">Last synced: {new Date(list.last_synced).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'})}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 ml-4">
              <button
                onClick={onSync}
                disabled={syncing || queued}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors disabled:opacity-50"
                title="Sync now"
              >
                <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                {syncing && <span className="text-xs">Syncing</span>}
                {queued && !syncing && <span className="text-xs">Queued</span>}
              </button>
              <button
                onClick={onEdit}
                className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                title="Edit"
              >
                <Edit2 size={16} />
              </button>
              <button
                onClick={onDelete}
                className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--error)] transition-colors"
                title="Delete"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
