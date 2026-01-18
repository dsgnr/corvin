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
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <div>
        <label className="mb-1 block text-sm font-medium">Name</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
          required
        />
      </div>

      {!isEditing && (
        <div>
          <label className="mb-1 block text-sm font-medium">URL</label>
          <p className="mb-2 text-xs text-[var(--muted)]">
            YouTube channel or playlist URL to monitor
          </p>
          <input
            type="text"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
            placeholder="https://youtube.com/..."
            required
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium">Type</label>
          <p className="mb-2 text-xs text-[var(--muted)]">Whether this is a channel or playlist</p>
          <Select
            value={form.list_type}
            onChange={(e) => setForm({ ...form, list_type: e.target.value })}
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Profile</label>
          <p className="mb-2 text-xs text-[var(--muted)]">Download settings to use for this list</p>
          <Select
            value={form.profile_id}
            onChange={(e) => setForm({ ...form, profile_id: Number(e.target.value) })}
          >
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Sync Frequency</label>
          <p className="mb-2 text-xs text-[var(--muted)]">How often to check for new videos</p>
          <Select
            value={form.sync_frequency}
            onChange={(e) => setForm({ ...form, sync_frequency: e.target.value })}
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
          <label className="mb-1 block text-sm font-medium">From Date</label>
          <p className="mb-2 text-xs text-[var(--muted)]">
            Only sync videos uploaded after this date
          </p>
          <input
            type="date"
            value={
              form.from_date
                ? `${form.from_date.slice(0, 4)}-${form.from_date.slice(4, 6)}-${form.from_date.slice(6, 8)}`
                : ''
            }
            onChange={(e) => setForm({ ...form, from_date: e.target.value.replace(/-/g, '') })}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
          />
        </div>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
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
          className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]"
        >
          <X size={18} />
        </button>
        <button
          type="submit"
          disabled={saving || !form.name || (!isEditing && !form.url) || !form.profile_id}
          className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
