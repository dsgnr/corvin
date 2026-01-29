'use client'

import { useState, useMemo } from 'react'
import { Profile, BulkListCreate } from '@/lib/api'
import { X, Check, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'
import { FormField, ValidatedTextarea } from '@/components/FormField'
import { validators } from '@/lib/validation'

interface BulkListFormProps {
  profiles: Profile[]
  onSave: (
    data: BulkListCreate
  ) => Promise<{ created: number; errors: { url: string; error: string }[] }>
  onCancel: () => void
}

interface UrlValidation {
  url: string
  valid: boolean
  error: string | null
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
  const [touched, setTouched] = useState(false)
  const [result, setResult] = useState<{
    created: number
    errors: { url: string; error: string }[]
  } | null>(null)

  // Parse and validate URLs
  const urlValidations = useMemo((): UrlValidation[] => {
    const lines = form.urls
      .split('\n')
      .map((u) => u.trim())
      .filter((u) => u.length > 0)

    return lines.map((url) => {
      const urlError = validators.url(url, 'URL')
      if (urlError) {
        return { url, valid: false, error: urlError }
      }
      return { url, valid: true, error: null }
    })
  }, [form.urls])

  const validUrls = urlValidations.filter((v) => v.valid)
  const invalidUrls = urlValidations.filter((v) => !v.valid)
  const urlCount = urlValidations.length

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)

    if (validUrls.length === 0) return

    setSaving(true)
    setResult(null)

    const urls = validUrls.map((v) => v.url)

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

  const hasUrlError = touched && urlCount > 0 && invalidUrls.length > 0
  const allUrlsValid = urlCount > 0 && invalidUrls.length === 0

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <FormField
        label="URLs (one per line)"
        description="Paste YouTube channel or playlist URLs, one per line. Names will be auto-detected."
        required
        error={touched && urlCount === 0 ? 'At least one URL is required' : null}
      >
        <ValidatedTextarea
          value={form.urls}
          onChange={(e) => setForm({ ...form, urls: e.target.value })}
          onBlur={() => setTouched(true)}
          className="h-40 font-mono text-sm"
          placeholder={
            'https://youtube.com/@channel1\nhttps://youtube.com/@channel2\nhttps://youtube.com/playlist?list=...'
          }
          disabled={saving}
        />

        {/* URL validation summary */}
        <div className="mt-2 space-y-1">
          {urlCount > 0 && (
            <p
              className={`flex items-center gap-1 text-xs ${allUrlsValid ? 'text-[var(--success)]' : 'text-[var(--muted)]'}`}
            >
              {allUrlsValid ? <CheckCircle2 size={12} /> : null}
              {validUrls.length} valid URL{validUrls.length !== 1 ? 's' : ''}
            </p>
          )}
          {hasUrlError && (
            <div className="space-y-1">
              <p className="flex items-center gap-1 text-xs text-[var(--error)]">
                <AlertCircle size={12} />
                {invalidUrls.length} invalid URL{invalidUrls.length !== 1 ? 's' : ''}
              </p>
              <ul className="ml-4 space-y-0.5 text-xs text-[var(--muted)]">
                {invalidUrls.slice(0, 3).map((v, i) => (
                  <li key={i} className="truncate">
                    <span className="font-mono">{v.url.slice(0, 40)}...</span>
                    <span className="text-[var(--error)]"> - {v.error}</span>
                  </li>
                ))}
                {invalidUrls.length > 3 && (
                  <li className="text-[var(--muted)]">
                    ...and {invalidUrls.length - 3} more invalid URL
                    {invalidUrls.length - 3 !== 1 ? 's' : ''}
                  </li>
                )}
              </ul>
            </div>
          )}
          {urlCount === 0 && touched && (
            <p className="text-xs text-[var(--muted)]">Paste URLs above to get started</p>
          )}
        </div>
      </FormField>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Type" description="Whether these are channels or playlists">
          <Select
            value={form.list_type}
            onChange={(e) => setForm({ ...form, list_type: e.target.value })}
            disabled={saving}
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </Select>
        </FormField>

        <FormField label="Profile" description="Download settings to use for all lists" required>
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
        </FormField>

        <FormField label="Sync Frequency" description="How often to check for new videos">
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
        </FormField>
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
          disabled={saving || validUrls.length === 0 || !form.profile_id}
          className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
