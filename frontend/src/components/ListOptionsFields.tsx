'use client'

import { useCallback } from 'react'
import { Profile } from '@/lib/api'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'
import { FormField, ValidatedInput } from '@/components/FormField'
import { validators } from '@/lib/validation'

export interface ListOptionsValues {
  list_type: string
  profile_id: number
  sync_frequency: string
  from_date: string
  blacklist_regex: string
  min_duration: number | null
  max_duration: number | null
  enabled: boolean
  auto_download: boolean
}

export interface ListOptionsErrors {
  blacklist_regex: string | null
  min_duration: string | null
  max_duration: string | null
}

export interface ListOptionsTouched {
  blacklist_regex: boolean
  min_duration: boolean
  max_duration: boolean
}

interface ListOptionsFieldsProps {
  values: ListOptionsValues
  profiles: Profile[]
  errors: ListOptionsErrors
  touched: ListOptionsTouched
  minDurationRaw: string
  maxDurationRaw: string
  disabled?: boolean
  onChange: (values: Partial<ListOptionsValues>) => void
  onErrorChange: (errors: Partial<ListOptionsErrors>) => void
  onTouchedChange: (touched: Partial<ListOptionsTouched>) => void
  onMinDurationRawChange: (value: string) => void
  onMaxDurationRawChange: (value: string) => void
}

// Validation helpers
export function validateRegex(value: string): string | null {
  if (!value) return null
  return validators.regex(value)
}

export function validateDuration(raw: string): string | null {
  if (raw === '') return null
  if (!/^\d+$/.test(raw)) return 'Must be a positive integer'
  const val = parseInt(raw, 10)
  if (val < 0) return 'Must be 0 or greater'
  return null
}

export function ListOptionsFields({
  values,
  profiles,
  errors,
  touched,
  minDurationRaw,
  maxDurationRaw,
  disabled = false,
  onChange,
  onErrorChange,
  onTouchedChange,
  onMinDurationRawChange,
  onMaxDurationRawChange,
}: ListOptionsFieldsProps) {
  const handleRegexChange = useCallback(
    (value: string) => {
      onChange({ blacklist_regex: value })
      onTouchedChange({ blacklist_regex: true })
      onErrorChange({ blacklist_regex: validateRegex(value) })
    },
    [onChange, onTouchedChange, onErrorChange]
  )

  const handleMinDurationChange = useCallback(
    (raw: string) => {
      onMinDurationRawChange(raw)
      onTouchedChange({ min_duration: true })
      if (raw === '') {
        onChange({ min_duration: null })
        onErrorChange({ min_duration: null })
      } else if (/^\d+$/.test(raw)) {
        onChange({ min_duration: parseInt(raw, 10) })
        onErrorChange({ min_duration: null })
      } else {
        onErrorChange({ min_duration: 'Must be a positive integer' })
      }
    },
    [onChange, onErrorChange, onTouchedChange, onMinDurationRawChange]
  )

  const handleMaxDurationChange = useCallback(
    (raw: string) => {
      onMaxDurationRawChange(raw)
      onTouchedChange({ max_duration: true })
      if (raw === '') {
        onChange({ max_duration: null })
        onErrorChange({ max_duration: null })
      } else if (/^\d+$/.test(raw)) {
        onChange({ max_duration: parseInt(raw, 10) })
        onErrorChange({ max_duration: null })
      } else {
        onErrorChange({ max_duration: 'Must be a positive integer' })
      }
    },
    [onChange, onErrorChange, onTouchedChange, onMaxDurationRawChange]
  )

  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField label="Type" description="Whether this is a channel or playlist">
          <Select
            value={values.list_type}
            onChange={(e) => onChange({ list_type: e.target.value })}
            disabled={disabled}
          >
            <option value="channel">Channel</option>
            <option value="playlist">Playlist</option>
          </Select>
        </FormField>

        <FormField label="Profile" description="Download settings to use" required>
          <Select
            value={values.profile_id}
            onChange={(e) => onChange({ profile_id: Number(e.target.value) })}
            disabled={disabled}
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
            value={values.sync_frequency}
            onChange={(e) => onChange({ sync_frequency: e.target.value })}
            disabled={disabled}
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
              values.from_date
                ? `${values.from_date.slice(0, 4)}-${values.from_date.slice(4, 6)}-${values.from_date.slice(6, 8)}`
                : ''
            }
            onChange={(e) => onChange({ from_date: e.target.value.replace(/-/g, '') })}
            className="input"
            disabled={disabled}
          />
        </FormField>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <FormField
          label="Blacklist Pattern"
          description="Videos with titles matching this pattern will be synced but not auto-downloaded. Uses regex with case-insensitive matching."
          error={touched.blacklist_regex ? errors.blacklist_regex : null}
        >
          <ValidatedInput
            type="text"
            value={values.blacklist_regex}
            onChange={(e) => handleRegexChange(e.target.value)}
            onBlur={() => onTouchedChange({ blacklist_regex: true })}
            className="font-mono text-sm"
            placeholder="e.g. live|sponsor|#shorts"
            disabled={disabled}
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
            description="Videos shorter than this will be blacklisted (in seconds)"
            error={touched.min_duration ? errors.min_duration : null}
          >
            <input
              type="text"
              inputMode="numeric"
              value={minDurationRaw}
              onChange={(e) => handleMinDurationChange(e.target.value)}
              onBlur={() => onTouchedChange({ min_duration: true })}
              placeholder="e.g. 60 for 1 minute"
              className="input"
              disabled={disabled}
            />
          </FormField>

          <FormField
            label="Max Duration"
            description="Videos longer than this will be blacklisted (in seconds)"
            error={touched.max_duration ? errors.max_duration : null}
          >
            <input
              type="text"
              inputMode="numeric"
              value={maxDurationRaw}
              onChange={(e) => handleMaxDurationChange(e.target.value)}
              onBlur={() => onTouchedChange({ max_duration: true })}
              placeholder="e.g. 3600 for 1 hour"
              className="input"
              disabled={disabled}
            />
          </FormField>
        </div>

        <ToggleOption
          label="Enabled"
          description="When disabled, this list will not be synced automatically"
          checked={values.enabled}
          onChange={() => onChange({ enabled: !values.enabled })}
          disabled={disabled}
        />

        <ToggleOption
          label="Auto download"
          description="Automatically queue new videos for download"
          checked={values.auto_download}
          onChange={() => onChange({ auto_download: !values.auto_download })}
          disabled={disabled}
        />
      </div>
    </>
  )
}
