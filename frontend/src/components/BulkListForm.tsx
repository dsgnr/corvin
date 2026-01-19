'use client'

import { useState } from 'react'
import { Profile, BulkListCreate } from '@/lib/api'
import { X, Check, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'

interface BulkListFormProps {
  profiles: Profile[]
  onSave: (
    data: BulkListCreate
  ) => Promise<{ created: number; errors: { url: string; error: string }[] }>
  onCancel: () => void
}

export function BulkListForm({ profiles, onSave, onCancel }: BulkListFormProps) {
  const [form, setForm] = useState({
    urls: '',
    list_type: 'channel',
    profile_id: profiles[0]?.id || 0,
    sync_frequency: 'daily',
    enabled: true,
    auto_download: true,
  })
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<{
    created: number
    errors: { url: string; error: string }[]
  } | null>(null)

  const urlCount = form.urls
    .split('\n')
    .map((u) => u.trim())
    .filter((u) => u.length > 0).length

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (urlCount === 0) return

    setSaving(true)
    setResult(null)

    const urls = form.urls
      .split('\n')
      .map((u) => u.trim())
      .filter((u) => u.length > 0)

    const res = await onSave({
      urls,
      list_type: form.list_type,
      profile_id: form.profile_id,
      sync_frequency: form.sync_frequency,
      enabled: form.enabled,
      auto_download: form.auto_download,
    })

    setResult(res)
    setSaving(false)

    if (res.errors.length === 0 && res.created > 0) {
      setTimeout(() => onCancel(), 1500)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <div>
        <label className="mb-1 block text-sm font-medium">URLs (one per line)</label>
        <p className="mb-2 text-xs text-[var(--muted)]">
          Paste YouTube channel or playlist URLs, one per line. Names will be auto-detected.
        </p>
        <textarea
          value={form.urls}
          onChange={(e) => setForm({ ...form, urls: e.target.value })}
          className="h-40 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 font-mono text-sm focus:border-[var(--accent)] focus:outline-none"
          placeholder={
            'https://youtube.com/@channel1\nhttps://youtube.com/@channel2\nhttps://youtube.com/playlist?list=...'
          }
          disabled={saving}
        />
        <p className="mt-1 text-xs text-[var(--muted)]">
          {urlCount} URL{urlCount !== 1 ? 's' : ''} detected
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium">Type</label>
          <p className="mb-2 text-xs text-[var(--muted)]">
            Whether these are channels or playlists
          </p>
          <Select
            value={form.list_type}
            onChange={(e) => setForm({ ...form, list_type: e.target.value })}
            disabled={saving}
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Profile</label>
          <p className="mb-2 text-xs text-[var(--muted)]">Download settings to use for all lists</p>
          <Select
            value={form.profile_id}
            onChange={(e) => setForm({ ...form, profile_id: Number(e.target.value) })}
            disabled={saving}
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
            disabled={saving}
          >
            <option value="hourly">Hourly</option>
            <option value="6h">Every 6 hours</option>
            <option value="12h">Every 12 hours</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </Select>
        </div>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <ToggleOption
          label="Enabled"
          description="When disabled, these lists will not be synced automatically"
          checked={form.enabled}
          onChange={() => setForm({ ...form, enabled: !form.enabled })}
          disabled={saving}
        />

        <ToggleOption
          label="Auto download"
          description="Automatically queue new videos for download"
          checked={form.auto_download}
          onChange={() => setForm({ ...form, auto_download: !form.auto_download })}
          disabled={saving}
        />
      </div>

      {result && (
        <div className="space-y-2 border-t border-[var(--border)] pt-4">
          {result.created > 0 && (
            <div className="flex items-center gap-2 text-sm text-[var(--success)]">
              <CheckCircle2 size={16} />
              <span>
                Queued {result.created} list{result.created !== 1 ? 's' : ''} for creation
              </span>
            </div>
          )}
          {result.errors.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-[var(--error)]">
                <AlertCircle size={16} />
                <span>
                  {result.errors.length} error{result.errors.length !== 1 ? 's' : ''}
                </span>
              </div>
              <ul className="ml-6 space-y-1 text-xs text-[var(--muted)]">
                {result.errors.map((err, i) => (
                  <li key={i}>
                    <span className="font-mono">
                      {err.url.length > 50 ? err.url.slice(0, 50) + '...' : err.url}
                    </span>
                    : {err.error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)] disabled:opacity-50"
        >
          <X size={18} />
        </button>
        <button
          type="submit"
          disabled={saving || urlCount === 0 || !form.profile_id}
          className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
