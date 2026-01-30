'use client'

import { useState, useMemo, useCallback } from 'react'
import { Profile, BulkListCreate } from '@/lib/api'
import { X, Check, AlertCircle, CheckCircle2 } from 'lucide-react'
import { FormField, ValidatedTextarea } from '@/components/FormField'
import { validators } from '@/lib/validation'
import {
  ListOptionsFields,
  ListOptionsValues,
  ListOptionsErrors,
  ListOptionsTouched,
  validateRegex,
  validateDuration,
} from '@/components/ListOptionsFields'

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
  const [urls, setUrls] = useState('')
  const [options, setOptions] = useState<ListOptionsValues>({
    list_type: 'channel',
    profile_id: profiles[0]?.id || 0,
    sync_frequency: 'daily',
    from_date: '',
    blacklist_regex: '',
    min_duration: null,
    max_duration: null,
    enabled: true,
    auto_download: true,
  })

  const [minDurationRaw, setMinDurationRaw] = useState('')
  const [maxDurationRaw, setMaxDurationRaw] = useState('')

  const [saving, setSaving] = useState(false)
  const [urlsTouched, setUrlsTouched] = useState(false)
  const [optionErrors, setOptionErrors] = useState<ListOptionsErrors>({
    blacklist_regex: null,
    min_duration: null,
    max_duration: null,
  })
  const [optionsTouched, setOptionsTouched] = useState<ListOptionsTouched>({
    blacklist_regex: false,
    min_duration: false,
    max_duration: false,
  })
  const [result, setResult] = useState<{
    created: number
    errors: { url: string; error: string }[]
  } | null>(null)

  const handleOptionsChange = useCallback((partial: Partial<ListOptionsValues>) => {
    setOptions((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleOptionErrorsChange = useCallback((partial: Partial<ListOptionsErrors>) => {
    setOptionErrors((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleOptionsTouchedChange = useCallback((partial: Partial<ListOptionsTouched>) => {
    setOptionsTouched((prev) => ({ ...prev, ...partial }))
  }, [])

  // Parse and validate URLs
  const urlValidations = useMemo((): UrlValidation[] => {
    const lines = urls
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
  }, [urls])

  const validUrls = urlValidations.filter((v) => v.valid)
  const invalidUrls = urlValidations.filter((v) => !v.valid)
  const urlCount = urlValidations.length

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setUrlsTouched(true)

    // Validate all fields
    const regexError = validateRegex(options.blacklist_regex)
    const minDurationError = validateDuration(minDurationRaw)
    const maxDurationError = validateDuration(maxDurationRaw)

    setOptionErrors({
      blacklist_regex: regexError,
      min_duration: minDurationError,
      max_duration: maxDurationError,
    })
    setOptionsTouched({
      blacklist_regex: true,
      min_duration: true,
      max_duration: true,
    })

    if (validUrls.length === 0 || regexError || minDurationError || maxDurationError) return

    setSaving(true)
    setResult(null)

    const res = await onSave({
      urls: validUrls.map((v) => v.url),
      list_type: options.list_type,
      profile_id: options.profile_id,
      sync_frequency: options.sync_frequency,
      enabled: options.enabled,
      auto_download: options.auto_download,
      from_date: options.from_date || null,
      blacklist_regex: options.blacklist_regex || null,
      min_duration: options.min_duration,
      max_duration: options.max_duration,
    })

    setResult(res)
    setSaving(false)

    if (res.errors.length === 0 && res.created > 0) {
      setTimeout(() => onCancel(), 1500)
    }
  }

  const hasUrlError = urlsTouched && urlCount > 0 && invalidUrls.length > 0
  const allUrlsValid = urlCount > 0 && invalidUrls.length === 0
  const hasFieldErrors = !!(
    optionErrors.blacklist_regex ||
    optionErrors.min_duration ||
    optionErrors.max_duration
  )

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <FormField
        label="URLs (one per line)"
        description="Paste YouTube channel or playlist URLs, one per line. Names will be auto-detected."
        required
        error={urlsTouched && urlCount === 0 ? 'At least one URL is required' : null}
      >
        <ValidatedTextarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          onBlur={() => setUrlsTouched(true)}
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
          {urlCount === 0 && urlsTouched && (
            <p className="text-xs text-[var(--muted)]">Paste URLs above to get started</p>
          )}
        </div>
      </FormField>

      <ListOptionsFields
        values={options}
        profiles={profiles}
        errors={optionErrors}
        touched={optionsTouched}
        minDurationRaw={minDurationRaw}
        maxDurationRaw={maxDurationRaw}
        disabled={saving}
        onChange={handleOptionsChange}
        onErrorChange={handleOptionErrorsChange}
        onTouchedChange={handleOptionsTouchedChange}
        onMinDurationRawChange={setMinDurationRaw}
        onMaxDurationRawChange={setMaxDurationRaw}
      />

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
          disabled={saving || validUrls.length === 0 || !options.profile_id || hasFieldErrors}
          className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
