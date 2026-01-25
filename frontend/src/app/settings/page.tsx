'use client'

import { useEffect, useState, useCallback } from 'react'
import { Clock, ExternalLink, Plus, Trash2, AlertCircle } from 'lucide-react'
import { api, DownloadSchedule, ScheduleStatus } from '@/lib/api'
import { FormField, ValidatedInput } from '@/components/FormField'
import { validators } from '@/lib/validation'

const DAYS_OF_WEEK = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
]

interface ScheduleFormData {
  name: string
  enabled: boolean
  days_of_week: string[]
  start_time: string
  end_time: string
}

interface ScheduleFormErrors {
  name: string | null
  days_of_week: string | null
  start_time: string | null
  end_time: string | null
}

interface ScheduleTouchedFields {
  name: boolean
  days_of_week: boolean
  start_time: boolean
  end_time: boolean
}

const defaultScheduleForm: ScheduleFormData = {
  name: '',
  enabled: true,
  days_of_week: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
  start_time: '00:00',
  end_time: '23:59',
}

const defaultErrors: ScheduleFormErrors = {
  name: null,
  days_of_week: null,
  start_time: null,
  end_time: null,
}

const defaultTouched: ScheduleTouchedFields = {
  name: false,
  days_of_week: false,
  start_time: false,
  end_time: false,
}

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState(
    typeof window !== 'undefined' ? localStorage.getItem('corvin_api_url') || '' : ''
  )
  const [saved, setSaved] = useState(false)

  // Schedule state
  const [schedules, setSchedules] = useState<DownloadSchedule[]>([])
  const [scheduleStatus, setScheduleStatus] = useState<ScheduleStatus | null>(null)
  const [showScheduleForm, setShowScheduleForm] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<DownloadSchedule | null>(null)
  const [scheduleForm, setScheduleForm] = useState<ScheduleFormData>(defaultScheduleForm)
  const [scheduleError, setScheduleError] = useState<string | null>(null)
  const [scheduleSaving, setScheduleSaving] = useState(false)
  const [errors, setErrors] = useState<ScheduleFormErrors>(defaultErrors)
  const [touched, setTouched] = useState<ScheduleTouchedFields>(defaultTouched)

  useEffect(() => {
    loadSchedules()
  }, [])

  const loadSchedules = async () => {
    try {
      const [schedulesData, statusData] = await Promise.all([
        api.getSchedules(),
        api.getScheduleStatus(),
      ])
      setSchedules(schedulesData)
      setScheduleStatus(statusData)
    } catch {
      // Ignore errors on initial load
    }
  }

  const handleSave = () => {
    if (apiUrl) {
      localStorage.setItem('corvin_api_url', apiUrl)
    } else {
      localStorage.removeItem('corvin_api_url')
    }
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  // Validation functions
  const validateName = useCallback((value: string): string | null => {
    const required = validators.required(value, 'Schedule name')
    if (required) return required
    const minLen = validators.minLength(value, 2, 'Schedule name')
    if (minLen) return minLen
    return null
  }, [])

  const validateDays = useCallback((days: string[]): string | null => {
    return validators.nonEmptyArray(days, 'day')
  }, [])

  const validateTime = useCallback((value: string, fieldName: string): string | null => {
    const required = validators.required(value, fieldName)
    if (required) return required
    return validators.time(value, fieldName)
  }, [])

  const handleFieldChange = (field: keyof ScheduleFormErrors, value: string | string[]) => {
    setScheduleForm((prev) => ({ ...prev, [field]: value }))
    if (touched[field]) {
      let error: string | null = null
      if (field === 'name') error = validateName(value as string)
      else if (field === 'days_of_week') error = validateDays(value as string[])
      else if (field === 'start_time') error = validateTime(value as string, 'Start time')
      else if (field === 'end_time') error = validateTime(value as string, 'End time')
      setErrors((prev) => ({ ...prev, [field]: error }))
    }
  }

  const handleBlur = (field: keyof ScheduleTouchedFields) => {
    setTouched((prev) => ({ ...prev, [field]: true }))
    let error: string | null = null
    if (field === 'name') error = validateName(scheduleForm.name)
    else if (field === 'days_of_week') error = validateDays(scheduleForm.days_of_week)
    else if (field === 'start_time') error = validateTime(scheduleForm.start_time, 'Start time')
    else if (field === 'end_time') error = validateTime(scheduleForm.end_time, 'End time')
    setErrors((prev) => ({ ...prev, [field]: error }))
  }

  const validateAll = (): boolean => {
    const nameError = validateName(scheduleForm.name)
    const daysError = validateDays(scheduleForm.days_of_week)
    const startError = validateTime(scheduleForm.start_time, 'Start time')
    const endError = validateTime(scheduleForm.end_time, 'End time')

    setErrors({
      name: nameError,
      days_of_week: daysError,
      start_time: startError,
      end_time: endError,
    })
    setTouched({
      name: true,
      days_of_week: true,
      start_time: true,
      end_time: true,
    })

    return !nameError && !daysError && !startError && !endError
  }

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateAll()) return

    setScheduleError(null)
    setScheduleSaving(true)

    try {
      if (editingSchedule) {
        await api.updateSchedule(editingSchedule.id, scheduleForm)
      } else {
        await api.createSchedule(scheduleForm)
      }
      await loadSchedules()
      setShowScheduleForm(false)
      setEditingSchedule(null)
      setScheduleForm(defaultScheduleForm)
      setErrors(defaultErrors)
      setTouched(defaultTouched)
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : 'Failed to save schedule')
    } finally {
      setScheduleSaving(false)
    }
  }

  const handleEditSchedule = (schedule: DownloadSchedule) => {
    setEditingSchedule(schedule)
    setScheduleForm({
      name: schedule.name,
      enabled: schedule.enabled,
      days_of_week: schedule.days_of_week,
      start_time: schedule.start_time,
      end_time: schedule.end_time,
    })
    setShowScheduleForm(true)
    setScheduleError(null)
    setErrors(defaultErrors)
    setTouched(defaultTouched)
  }

  const handleDeleteSchedule = async (id: number) => {
    if (!confirm('Delete this schedule?')) return
    try {
      await api.deleteSchedule(id)
      await loadSchedules()
    } catch {
      // Ignore
    }
  }

  const handleToggleSchedule = async (schedule: DownloadSchedule) => {
    try {
      await api.updateSchedule(schedule.id, { enabled: !schedule.enabled })
      await loadSchedules()
    } catch {
      // Ignore
    }
  }

  const toggleDay = (day: string) => {
    const newDays = scheduleForm.days_of_week.includes(day)
      ? scheduleForm.days_of_week.filter((d) => d !== day)
      : [...scheduleForm.days_of_week, day]
    handleFieldChange('days_of_week', newDays)
  }

  const cancelScheduleForm = () => {
    setShowScheduleForm(false)
    setEditingSchedule(null)
    setScheduleForm(defaultScheduleForm)
    setScheduleError(null)
    setErrors(defaultErrors)
    setTouched(defaultTouched)
  }

  const isScheduleFormValid =
    scheduleForm.name.length >= 2 &&
    scheduleForm.days_of_week.length > 0 &&
    scheduleForm.start_time &&
    scheduleForm.end_time &&
    !errors.name &&
    !errors.days_of_week &&
    !errors.start_time &&
    !errors.end_time

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <div className="space-y-6 rounded-lg border border-[var(--border)] bg-[var(--card)] p-6">
        <div>
          <h2 className="mb-4 font-medium">API Configuration</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm text-[var(--muted)]">
                API URL (leave empty for default)
              </label>
              <input
                type="url"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:5001/api"
                className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
              />
              <p className="mt-1 text-xs text-[var(--muted)]">Default: http://localhost:5001/api</p>
            </div>
            <button
              onClick={handleSave}
              className="rounded-md bg-[var(--accent)] px-4 py-2 text-white transition-colors hover:bg-[var(--accent-hover)]"
            >
              {saved ? 'Saved!' : 'Save'}
            </button>
          </div>
        </div>

        <hr className="border-[var(--border)]" />

        <div>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-medium">Download Schedules</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Define time windows when automatic downloads are allowed. Syncing always runs
                regardless of schedule. Downloads are always allowed if no schedules are enabled.
              </p>
            </div>
            {scheduleStatus && (
              <div
                className={`flex shrink-0 items-center gap-2 self-start rounded-full px-3 py-1 text-sm sm:self-auto ${
                  scheduleStatus.downloads_allowed
                    ? 'bg-green-500/10 text-green-500'
                    : 'bg-red-500/10 text-red-500'
                }`}
              >
                <Clock size={14} />
                {scheduleStatus.downloads_allowed ? 'Downloads Active' : 'Downloads Paused'}
              </div>
            )}
          </div>

          {/* Schedule List */}
          {schedules.length > 0 && (
            <div className="mb-4 space-y-2">
              {schedules.map((schedule) => (
                <div
                  key={schedule.id}
                  className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--background)] p-3"
                >
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleToggleSchedule(schedule)}
                      className={`h-5 w-9 rounded-full transition-colors ${
                        schedule.enabled ? 'bg-[var(--accent)]' : 'bg-[var(--border)]'
                      }`}
                    >
                      <div
                        className={`h-4 w-4 rounded-full bg-white transition-transform ${
                          schedule.enabled ? 'translate-x-4' : 'translate-x-0.5'
                        }`}
                      />
                    </button>
                    <div>
                      <button
                        onClick={() => handleEditSchedule(schedule)}
                        className="font-medium hover:text-[var(--accent)]"
                      >
                        {schedule.name}
                      </button>
                      <p className="text-sm text-[var(--muted)]">
                        {schedule.days_of_week
                          .map((d) => d.charAt(0).toUpperCase() + d.slice(1))
                          .join(', ')}{' '}
                        • {schedule.start_time} - {schedule.end_time}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteSchedule(schedule.id)}
                    className="p-2 text-[var(--muted)] hover:text-red-500"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add/Edit Form */}
          {showScheduleForm ? (
            <form
              onSubmit={handleScheduleSubmit}
              className="space-y-4 rounded-md border border-[var(--border)] bg-[var(--background)] p-4"
            >
              <FormField
                label="Schedule Name"
                required
                error={touched.name ? errors.name : null}
                showSuccess={touched.name && !errors.name && scheduleForm.name.length > 0}
              >
                <ValidatedInput
                  type="text"
                  value={scheduleForm.name}
                  onChange={(e) => handleFieldChange('name', e.target.value)}
                  onBlur={() => handleBlur('name')}
                  error={errors.name}
                  touched={touched.name}
                  placeholder="e.g., Night Downloads"
                  autoFocus
                />
              </FormField>

              <FormField
                label="Days of Week"
                required
                error={touched.days_of_week ? errors.days_of_week : null}
              >
                <div className="flex flex-wrap gap-2">
                  {DAYS_OF_WEEK.map((day) => (
                    <button
                      key={day.value}
                      type="button"
                      onClick={() => toggleDay(day.value)}
                      onBlur={() => handleBlur('days_of_week')}
                      className={`rounded-md px-3 py-2 text-sm transition-colors sm:py-1.5 ${
                        scheduleForm.days_of_week.includes(day.value)
                          ? 'bg-[var(--accent)] text-white'
                          : 'bg-[var(--card)] text-[var(--muted)] hover:bg-[var(--border)]'
                      }`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </FormField>

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  label="Start Time"
                  required
                  error={touched.start_time ? errors.start_time : null}
                >
                  <ValidatedInput
                    type="time"
                    value={scheduleForm.start_time}
                    onChange={(e) => handleFieldChange('start_time', e.target.value)}
                    onBlur={() => handleBlur('start_time')}
                    error={errors.start_time}
                    touched={touched.start_time}
                  />
                </FormField>
                <FormField
                  label="End Time"
                  required
                  error={touched.end_time ? errors.end_time : null}
                >
                  <ValidatedInput
                    type="time"
                    value={scheduleForm.end_time}
                    onChange={(e) => handleFieldChange('end_time', e.target.value)}
                    onBlur={() => handleBlur('end_time')}
                    error={errors.end_time}
                    touched={touched.end_time}
                  />
                </FormField>
              </div>

              {scheduleError && (
                <p className="flex items-center gap-1 text-sm text-red-500">
                  <AlertCircle size={14} />
                  {scheduleError}
                </p>
              )}

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={scheduleSaving || !isScheduleFormValid}
                  className="rounded-md bg-[var(--accent)] px-4 py-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {scheduleSaving ? 'Saving...' : editingSchedule ? 'Update' : 'Create'}
                </button>
                <button
                  type="button"
                  onClick={cancelScheduleForm}
                  className="rounded-md border border-[var(--border)] px-4 py-2 transition-colors hover:bg-[var(--border)]"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowScheduleForm(true)}
              className="flex items-center gap-2 rounded-md border border-dashed border-[var(--border)] px-4 py-2 text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
            >
              <Plus size={16} />
              Add Schedule
            </button>
          )}
        </div>

        <hr className="border-[var(--border)]" />

        <div>
          <h2 className="mb-4 font-medium">About</h2>
          <div className="space-y-2 text-sm text-[var(--muted)]">
            <p>Corvin is a video download manager powered by yt-dlp.</p>
            <p className="flex items-center gap-2">
              <a
                href="https://github.com/yt-dlp/yt-dlp"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[var(--accent)] hover:underline"
              >
                yt-dlp Documentation
                <ExternalLink size={12} />
              </a>
            </p>
          </div>
        </div>

        <hr className="border-[var(--border)]" />

        <div>
          <h2 className="mb-4 font-medium">Output Template Variables</h2>
          <p className="mb-3 text-sm text-[var(--muted)]">
            Common variables for output templates.{' '}
            <a
              href="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#output-template"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--accent)] hover:underline"
            >
              See full documentation
              <ExternalLink size={12} className="ml-1 inline" />
            </a>
          </p>
          <div className="space-y-1 rounded-md bg-[var(--background)] p-4 font-mono text-sm text-[var(--muted)]">
            <p>%(title)s - Video title</p>
            <p>%(uploader)s - Channel name</p>
            <p>%(upload_date)s - Upload date (YYYYMMDD)</p>
            <p>%(id)s - Video ID</p>
            <p>%(ext)s - File extension</p>
            <p>%(duration)s - Duration in seconds</p>
            <p>%(view_count)s - View count</p>
            <p>%(playlist_index)s - Playlist index</p>
          </div>
        </div>
      </div>
    </div>
  )
}
