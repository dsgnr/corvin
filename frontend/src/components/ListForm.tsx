'use client'

import { useState, useCallback } from 'react'
import { VideoList, Profile } from '@/lib/api'
import { X, Check } from 'lucide-react'
import { FormField, ValidatedInput } from '@/components/FormField'
import { validators } from '@/lib/validation'
import {
  ListOptionsFields,
  ListOptionsValues,
  ListOptionsErrors,
  ListOptionsTouched,
  validateRegex,
  validateDuration,
} from '@/components/ListOptionsFields'

interface ListFormProps {
  list?: VideoList
  profiles: Profile[]
  onSave: (data: Partial<VideoList>) => Promise<void>
  onCancel: () => void
}

export function ListForm({ list, profiles, onSave, onCancel }: ListFormProps) {
  const [name, setName] = useState(list?.name || '')
  const [url, setUrl] = useState(list?.url || '')
  const [options, setOptions] = useState<ListOptionsValues>({
    list_type: list?.list_type || 'channel',
    profile_id: list?.profile_id || profiles[0]?.id || 0,
    sync_frequency: list?.sync_frequency || 'daily',
    from_date: list?.from_date || '',
    blacklist_regex: list?.blacklist_regex || '',
    min_duration: list?.min_duration ?? null,
    max_duration: list?.max_duration ?? null,
    enabled: list?.enabled ?? true,
    auto_download: list?.auto_download ?? true,
  })

  const [minDurationRaw, setMinDurationRaw] = useState(
    list?.min_duration != null ? String(list.min_duration) : ''
  )
  const [maxDurationRaw, setMaxDurationRaw] = useState(
    list?.max_duration != null ? String(list.max_duration) : ''
  )

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [nameError, setNameError] = useState<string | null>(null)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [optionErrors, setOptionErrors] = useState<ListOptionsErrors>({
    blacklist_regex: null,
    min_duration: null,
    max_duration: null,
  })

  const [nameTouched, setNameTouched] = useState(false)
  const [urlTouched, setUrlTouched] = useState(false)
  const [optionsTouched, setOptionsTouched] = useState<ListOptionsTouched>({
    blacklist_regex: false,
    min_duration: false,
    max_duration: false,
  })

  const isEditing = !!list

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

  const handleNameChange = (value: string) => {
    setName(value)
    if (nameTouched) {
      setNameError(validateName(value))
    }
  }

  const handleUrlChange = (value: string) => {
    setUrl(value)
    if (urlTouched) {
      setUrlError(validateUrl(value))
    }
  }

  const handleOptionsChange = useCallback((partial: Partial<ListOptionsValues>) => {
    setOptions((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleOptionErrorsChange = useCallback((partial: Partial<ListOptionsErrors>) => {
    setOptionErrors((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleOptionsTouchedChange = useCallback((partial: Partial<ListOptionsTouched>) => {
    setOptionsTouched((prev) => ({ ...prev, ...partial }))
  }, [])

  const validateAll = (): boolean => {
    const nameErr = validateName(name)
    const urlErr = !isEditing ? validateUrl(url) : null
    const regexErr = validateRegex(options.blacklist_regex)
    const minDurErr = validateDuration(minDurationRaw)
    const maxDurErr = validateDuration(maxDurationRaw)

    setNameError(nameErr)
    setUrlError(urlErr)
    setOptionErrors({
      blacklist_regex: regexErr,
      min_duration: minDurErr,
      max_duration: maxDurErr,
    })

    setNameTouched(true)
    setUrlTouched(true)
    setOptionsTouched({
      blacklist_regex: true,
      min_duration: true,
      max_duration: true,
    })

    return !nameErr && !urlErr && !regexErr && !minDurErr && !maxDurErr
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateAll()) return

    setSaving(true)
    setError(null)
    try {
      await onSave({
        name,
        url,
        ...options,
        blacklist_regex: options.blacklist_regex || null,
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
    name.length >= 2 &&
    (isEditing || url.length > 0) &&
    options.profile_id > 0 &&
    !nameError &&
    !urlError &&
    !optionErrors.blacklist_regex &&
    !optionErrors.min_duration &&
    !optionErrors.max_duration

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <FormField label="Name" required error={nameTouched ? nameError : null}>
        <ValidatedInput
          type="text"
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          onBlur={() => {
            setNameTouched(true)
            setNameError(validateName(name))
          }}
          placeholder="My Channel"
          autoFocus
        />
      </FormField>

      {!isEditing && (
        <FormField
          label="URL"
          description="YouTube channel or playlist URL to monitor"
          required
          error={urlTouched ? urlError : null}
        >
          <ValidatedInput
            type="text"
            value={url}
            onChange={(e) => handleUrlChange(e.target.value)}
            onBlur={() => {
              setUrlTouched(true)
              setUrlError(validateUrl(url))
            }}
            placeholder="https://youtube.com/@channel or https://youtube.com/playlist?list=..."
          />
        </FormField>
      )}

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
