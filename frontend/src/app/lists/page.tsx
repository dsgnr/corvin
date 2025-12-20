'use client'

import { useEffect, useState } from 'react'
import { api, VideoList, Profile } from '@/lib/api'
import { Plus, RefreshCw, Trash2, Edit2, ExternalLink, Loader2, X, Check } from 'lucide-react'
import { clsx } from 'clsx'
import Link from 'next/link'

export default function ListsPage() {
  const [lists, setLists] = useState<VideoList[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const [syncingIds, setSyncingIds] = useState<Set<number>>(new Set())

  const checkSyncStatus = async () => {
    try {
      const tasks = await api.getTasks({ type: 'sync', status: 'running' })
      const runningIds = new Set(tasks.map(t => t.entity_id))
      setSyncingIds(runningIds)
      return runningIds
    } catch {
      return new Set<number>()
    }
  }

  const fetchData = async () => {
    try {
      const [listsData, profilesData] = await Promise.all([
        api.getLists(),
        api.getProfiles(),
      ])
      setLists(listsData)
      setProfiles(profilesData)
      await checkSyncStatus()
    } catch (err) {
      console.error('Failed to fetch lists:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // Poll for sync status while any list is syncing
  useEffect(() => {
    if (syncingIds.size === 0) return
    const interval = setInterval(async () => {
      const stillRunning = await checkSyncStatus()
      if (stillRunning.size === 0) {
        // Only refetch lists data, not profiles (they don't change during sync)
        const listsData = await api.getLists()
        setLists(prev => {
          // Only update if data actually changed to prevent unnecessary re-renders
          if (JSON.stringify(prev) === JSON.stringify(listsData)) return prev
          return listsData
        })
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [syncingIds.size])

  const handleSync = async (listId: number) => {
    setSyncingIds(prev => new Set(prev).add(listId))
    try {
      await api.triggerListSync(listId)
    } catch (err) {
      console.error('Failed to sync:', err)
      setSyncingIds(prev => {
        const next = new Set(prev)
        next.delete(listId)
        return next
      })
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

      {profiles.length === 0 && (
        <div className="bg-[var(--warning)]/10 border border-[var(--warning)]/30 rounded-md p-4">
          <p className="text-sm text-[var(--warning)]">
            You need to create a profile before adding lists.{' '}
            <Link href="/profiles" className="underline">Create one now</Link>
          </p>
        </div>
      )}

      <div className="grid gap-4">
        {editingId === 'new' && (
          <ListForm
            profiles={profiles}
            onSave={(data) => handleSave(data)}
            onCancel={() => setEditingId(null)}
          />
        )}

        {lists.length === 0 && editingId !== 'new' ? (
          <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-8 text-center">
            <p className="text-[var(--muted)]">No lists yet. Add one to get started.</p>
          </div>
        ) : (
          lists.map(list => (
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
                onSync={() => handleSync(list.id)}
                onEdit={() => setEditingId(list.id)}
                onDelete={() => handleDelete(list)}
              />
            )
          ))
        )}
      </div>
    </div>
  )
}

function ListCard({ list, profiles, syncing, onSync, onEdit, onDelete }: {
  list: VideoList
  profiles: Profile[]
  syncing: boolean
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
              <div className="flex items-center gap-4 mt-2 text-xs text-[var(--muted)]">
                <span>Profile: {profile?.name || 'Unknown'}</span>
                <span>Sync: {list.sync_frequency}</span>
                {list.last_synced && (
                  <span>Last synced: {new Date(list.last_synced).toLocaleDateString()}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 ml-4">
              <button
                onClick={onSync}
                disabled={syncing}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors disabled:opacity-50"
                title="Sync now"
              >
                <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                {syncing && <span className="text-xs">Syncing</span>}
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

function ListForm({ list, profiles, onSave, onCancel }: {
  list?: VideoList
  profiles: Profile[]
  onSave: (data: Partial<VideoList>) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState({
    name: list?.name || '',
    url: list?.url || '',
    list_type: list?.list_type || 'channel',
    profile_id: list?.profile_id || profiles[0]?.id || 0,
    sync_frequency: list?.sync_frequency || 'daily',
    from_date: list?.from_date || '',
    enabled: list?.enabled ?? true,
  })
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    await onSave(form)
    setSaving(false)
  }

  return (
    <form onSubmit={handleSubmit} className="bg-[var(--card)] rounded-lg border border-[var(--accent)] p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
            required
          />
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">URL</label>
          <input
            type="url"
            value={form.url}
            onChange={e => setForm({ ...form, url: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
            placeholder="https://youtube.com/..."
            required
            disabled={!!list}
          />
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Type</label>
          <select
            value={form.list_type}
            onChange={e => setForm({ ...form, list_type: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Profile</label>
          <select
            value={form.profile_id}
            onChange={e => setForm({ ...form, profile_id: Number(e.target.value) })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          >
            {profiles.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Sync Frequency</label>
          <select
            value={form.sync_frequency}
            onChange={e => setForm({ ...form, sync_frequency: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">From Date</label>
          <input
            type="date"
            value={form.from_date ? `${form.from_date.slice(0,4)}-${form.from_date.slice(4,6)}-${form.from_date.slice(6,8)}` : ''}
            onChange={e => setForm({ ...form, from_date: e.target.value.replace(/-/g, '') })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          />
        </div>
      </div>
      <div className="flex items-center justify-between pt-2">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={e => setForm({ ...form, enabled: e.target.checked })}
            className="rounded border-[var(--border)]"
          />
          <span className="text-sm">Enabled</span>
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
          >
            <X size={18} />
          </button>
          <button
            type="submit"
            disabled={saving || !form.name || !form.url || !form.profile_id}
            className="p-2 rounded-md bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white transition-colors disabled:opacity-50"
          >
            <Check size={18} />
          </button>
        </div>
      </div>
    </form>
  )
}
