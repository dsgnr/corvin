'use client'

import { useState, useCallback } from 'react'
import { VideoList, Profile } from '@/lib/api'
import { X, Check } from 'lucide-react'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'
import { FormField, ValidatedInput } from '@/components/FormField'
import { validators } from '@/lib/validation'

interface ListFormProps {
  list?: VideoList
  profiles: Profile[]
  onSave: (data: Partial<VideoList>) => Promise<void>
  onCancel: () => void
}

interface FormErrors {
  name: string | null
  url: string | null
  blacklist_regex: string | null
  min_duration: string | null
  max_duration: string | null
}

interface TouchedFields {
  name: boolean
  url: boolean
  blacklist_regex: boolean
  min_duration: boolean
  max_duration: boolean
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
    blacklist_regex: list?.blacklist_regex || '',
    min_duration: list?.min_duration ?? null,
    max_duration: list?.max_duration ?? null,
  })
  // Track raw string values for duration fields to preserve invalid input
  const [minDurationRaw, setMinDurationRaw] = useState(
    list?.min_duration != null ? String(list.min_duration) : ''
  )
  const [maxDurationRaw, setMaxDurationRaw] = useState(
    list?.max_duration != null ? String(list.max_duration) : ''
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errors, setErrors] = useState<FormErrors>({
    name: null,
    url: null,
    blacklist_regex: null,
    min_duration: null,
    max_duration: null,
  })
  const [touched, setTouched] = useState<TouchedFields>({
    name: false,
    url: false,
    blacklist_regex: false,
    min_duration: false,
    max_duration: false,
  })

  const isEditing = !!list

  // Validation functions
  const validateName = useCallback((value: string): string | null => {
    const required = validators.required(value, 'Name')
    if (required) return required
    const minLen = validators.minLength(value, 2, 'Name')
    if (minLen) return minLen
    const maxLen = validators.maxLength(value, 100, 'Name')
    if (maxLen) return maxLen
    return null
  }, [])

  const validateUrl = useCallback((value: string): string | null => {
    const required = validators.required(value, 'URL')
    if (required) return required
    return validators.url(value, 'URL')
  }, [])

  const validateRegex = useCallback((value: string): string | null => {
    if (!value) return null // Skip validation for empty/blank regex
    return validators.regex(value)
  }, [])

  const validateDuration = useCallback((raw: string): string | null => {
    if (raw === '') return null // Optional field
    if (!/^\d+$/.test(raw)) return 'Must be a positive integer'
    const val = parseInt(raw, 10)
    if (val < 0) return 'Must be 0 or greater'
    return null
  }, [])

  // Handle field changes with validation
  const handleNameChange = (value: string) => {
    setForm((prev) => ({ ...prev, name: value }))
    if (touched.name) {
      setErrors((prev) => ({ ...prev, name: validateName(value) }))
    }
  }

  const handleUrlChange = (value: string) => {
    setForm((prev) => ({ ...prev, url: value }))
    if (touched.url) {
      setErrors((prev) => ({ ...prev, url: validateUrl(value) }))
    }
  }

  const handleRegexChange = (value: string) => {
    setForm((prev) => ({ ...prev, blacklist_regex: value }))
    setTouched((prev) => ({ ...prev, blacklist_regex: true }))
    setErrors((prev) => ({ ...prev, blacklist_regex: validateRegex(value) }))
  }

  // Handle blur events
  const handleBlur = (field: keyof TouchedFields) => {
    setTouched((prev) => ({ ...prev, [field]: true }))
    if (field === 'name') {
      setErrors((prev) => ({ ...prev, name: validateName(form.name) }))
    } else if (field === 'url') {
      setErrors((prev) => ({ ...prev, url: validateUrl(form.url) }))
    } else if (field === 'blacklist_regex') {
      setErrors((prev) => ({ ...prev, blacklist_regex: validateRegex(form.blacklist_regex) }))
    } else if (field === 'min_duration') {
      setErrors((prev) => ({ ...prev, min_duration: validateDuration(minDurationRaw) }))
    } else if (field === 'max_duration') {
      setErrors((prev) => ({ ...prev, max_duration: validateDuration(maxDurationRaw) }))
    }
  }

  // Validate all fields
  const validateAll = (): boolean => {
    const nameError = validateName(form.name)
    const urlError = !isEditing ? validateUrl(form.url) : null
    const regexError = validateRegex(form.blacklist_regex)
    const minDurationError = validateDuration(minDurationRaw)
    const maxDurationError = validateDuration(maxDurationRaw)

    setErrors({
      name: nameError,
      url: urlError,
      blacklist_regex: regexError,
      min_duration: minDurationError,
      max_duration: maxDurationError,
    })
    setTouched({
      name: true,
      url: true,
      blacklist_regex: true,
      min_duration: true,
      max_duration: true,
    })

    return !nameError && !urlError && !regexError && !minDurationError && !maxDurationError
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateAll()) return

    setSaving(true)
    setError(null)
    try {
      await onSave({
        ...form,
        blacklist_regex: form.blacklist_regex || null,
        min_duration: form.min_duration,
        max_duration: form.max_duration,
      })
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'detail' in err
            ? String((err as { detail: string }).detail)
            : 'Failed to save list'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  const isFormValid =
    form.name.length >= 2 &&
    (isEditing || form.url.length > 0) &&
    form.profile_id > 0 &&
    !errors.name &&
    !errors.url &&
    !errors.blacklist_regex &&
    !errors.min_duration &&
    !errors.max_duration

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <FormField label="Name" required error={touched.name ? errors.name : null}>
        <ValidatedInput
          type="text"
          value={form.name}
          onChange={(e) => handleNameChange(e.target.value)}
          onBlur={() => handleBlur('name')}
          placeholder="My Channel"
          autoFocus
        />
      </FormField>

      {!isEditing && (
        <FormField
          label="URL"
          description="YouTube channel or playlist URL to monitor"
          required
          error={touched.url ? errors.url : null}
        >
          <ValidatedInput
            type="text"
            value={form.url}
            onChange={(e) => handleUrlChange(e.target.value)}
            onBlur={() => handleBlur('url')}
            placeholder="https://youtube.com/@channel or https://youtube.com/playlist?list=..."
          />
        </FormField>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Type" description="Whether this is a channel or playlist">
          <Select
            value={form.list_type}
            onChange={(e) => setForm({ ...form, list_type: e.target.value })}
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </Select>
        </FormField>

        <FormField label="Profile" description="Download settings to use for this list" required>
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
        </FormField>

        <FormField label="Sync Frequency" description="How often to check for new videos">
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
        </FormField>

        <FormField label="From Date" description="Only sync videos uploaded after this date">
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
        </FormField>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <FormField
          label="Blacklist Pattern"
          description="Videos with titles matching this pattern will be synced but not auto-downloaded. Uses regex with case-insensitive matching."
          error={errors.blacklist_regex}
        >
          <ValidatedInput
            type="text"
            value={form.blacklist_regex}
            onChange={(e) => handleRegexChange(e.target.value)}
            onBlur={() => handleBlur('blacklist_regex')}
            className="font-mono text-sm"
            placeholder="e.g. live|sponsor|#shorts"
          />
          <div className="mt-2 space-y-1 text-xs text-[var(--muted)]">
            <p>
              <code className="rounded bg-[var(--border)] px-1">word</code> matches titles
              containing &quot;word&quot; anywhere
            </p>
            <p>
              <code className="rounded bg-[var(--border)] px-1">live|stream</code> matches
              &quot;live&quot; OR &quot;stream&quot;
            </p>
            <p>
              <code className="rounded bg-[var(--border)] px-1">^live</code> matches titles starting
              with &quot;live&quot;
            </p>
          </div>
        </FormField>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormField
            label="Min Duration"
            description="Videos shorter than this will be blacklisted from auto-download (in seconds)"
            error={errors.min_duration}
          >
            <input
              type="text"
              inputMode="numeric"
              value={minDurationRaw}
              onChange={(e) => {
                const raw = e.target.value
                setMinDurationRaw(raw)
                setTouched((prev) => ({ ...prev, min_duration: true }))
                if (raw === '') {
                  setForm({ ...form, min_duration: null })
                  setErrors((prev) => ({ ...prev, min_duration: null }))
                } else if (/^\d+$/.test(raw)) {
                  setForm({ ...form, min_duration: parseInt(raw, 10) })
                  setErrors((prev) => ({ ...prev, min_duration: null }))
                } else {
                  setErrors((prev) => ({ ...prev, min_duration: 'Must be a positive integer' }))
                }
              }}
              onBlur={() => handleBlur('min_duration')}
              placeholder="e.g. 60 for 1 minute"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
            />
          </FormField>

          <FormField
            label="Max Duration"
            description="Videos longer than this will be blacklisted from auto-download (in seconds)"
            error={errors.max_duration}
          >
            <input
              type="text"
              inputMode="numeric"
              value={maxDurationRaw}
              onChange={(e) => {
                const raw = e.target.value
                setMaxDurationRaw(raw)
                setTouched((prev) => ({ ...prev, max_duration: true }))
                if (raw === '') {
                  setForm({ ...form, max_duration: null })
                  setErrors((prev) => ({ ...prev, max_duration: null }))
                } else if (/^\d+$/.test(raw)) {
                  setForm({ ...form, max_duration: parseInt(raw, 10) })
                  setErrors((prev) => ({ ...prev, max_duration: null }))
                } else {
                  setErrors((prev) => ({ ...prev, max_duration: 'Must be a positive integer' }))
                }
              }}
              onBlur={() => handleBlur('max_duration')}
              placeholder="e.g. 3600 for 1 hour"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
            />
          </FormField>
        </div>

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
        {error && <p className="mr-auto text-sm text-[var(--error)]">{error}</p>}
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]"
        >
          <X size={18} />
        </button>
        <button
          type="submit"
          disabled={saving || !isFormValid}
          className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
