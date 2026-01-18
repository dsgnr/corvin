'use client'

import { useState } from 'react'
import { VideoList, Profile } from '@/lib/api'
import { X, Check } from 'lucide-react'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'

interface ListFormProps {
  list?: VideoList
  profiles: Profile[]
  onSave: (data: Partial<VideoList>) => void
  onCancel: () => void
}

export function ListForm({ list, profiles, onSave, onCancel }: ListFormProps) {
  const [form, setForm] = useState({
    name: list?.name || '',
    url: list?.url || '',
    list_type: list?.list_type || 'channel',
    profile_id: list?.profile_id || profiles[0]?.id || 0,
    sync_frequency: list?.sync_frequency || 'daily',
    from_date: list?.from_date || '',
    enabled: list?.enabled ?? true,
    auto_download: list?.auto_download ?? true,
  })
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    await onSave(form)
    setSaving(false)
  }

  const isEditing = !!list

  return (
    <form onSubmit={handleSubmit} className="bg-[var(--card)] rounded-lg border border-[var(--accent)] p-4 space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">Name</label>
        <input
          type="text"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          required
        />
      </div>

      {!isEditing && (
        <div>
          <label className="block text-sm font-medium mb-1">URL</label>
          <p className="text-xs text-[var(--muted)] mb-2">YouTube channel or playlist URL to monitor</p>
          <input
            type="text"
            value={form.url}
            onChange={e => setForm({ ...form, url: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
            placeholder="https://youtube.com/..."
            required
          />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Type</label>
          <p className="text-xs text-[var(--muted)] mb-2">Whether this is a channel or playlist</p>
          <Select
            value={form.list_type}
            onChange={e => setForm({ ...form, list_type: e.target.value })}
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </Select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Profile</label>
          <p className="text-xs text-[var(--muted)] mb-2">Download settings to use for this list</p>
          <Select
            value={form.profile_id}
            onChange={e => setForm({ ...form, profile_id: Number(e.target.value) })}
          >
            {profiles.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Sync Frequency</label>
          <p className="text-xs text-[var(--muted)] mb-2">How often to check for new videos</p>
          <Select
            value={form.sync_frequency}
            onChange={e => setForm({ ...form, sync_frequency: e.target.value })}
          >
            <option value="hourly">Hourly</option>
            <option value="6h">Every 6 hours</option>
            <option value="12h">Every 12 hours</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </Select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">From Date</label>
          <p className="text-xs text-[var(--muted)] mb-2">Only sync videos uploaded after this date</p>
          <input
            type="date"
            value={form.from_date ? `${form.from_date.slice(0,4)}-${form.from_date.slice(4,6)}-${form.from_date.slice(6,8)}` : ''}
            onChange={e => setForm({ ...form, from_date: e.target.value.replace(/-/g, '') })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          />
        </div>
      </div>

      <div className="space-y-4 pt-4 border-t border-[var(--border)]">
        <ToggleOption
          label="Enabled"
          description="When disabled, this list will not be synced automatically"
          checked={form.enabled}
          onChange={() => setForm({ ...form, enabled: !form.enabled })}
        />

        <ToggleOption
          label="Auto download"
          description="Automatically queue new videos for download. If disabled, videos must be manually selected."
          checked={form.auto_download}
          onChange={() => setForm({ ...form, auto_download: !form.auto_download })}
        />
      </div>

      <div className="flex items-center justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
        >
          <X size={18} />
        </button>
        <button
          type="submit"
          disabled={saving || !form.name || (!isEditing && !form.url) || !form.profile_id}
          className="p-2 rounded-md bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white transition-colors disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
