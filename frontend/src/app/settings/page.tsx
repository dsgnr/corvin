'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  Clock,
  ExternalLink,
  Plus,
  Trash2,
  AlertCircle,
  Bell,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { api, DownloadSchedule, ScheduleStatus, Notifier, NotifierLibrary } from '@/lib/api'
import { FormField, ValidatedInput } from '@/components/FormField'
import { validators } from '@/lib/validation'
import { ToggleOption } from '@/components/ToggleOption'

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

  // Notification state
  const [notifiers, setNotifiers] = useState<Notifier[]>([])
  const [notifierConfigs, setNotifierConfigs] = useState<Record<string, Record<string, string>>>({})
  const [notifierEvents, setNotifierEvents] = useState<Record<string, Record<string, boolean>>>({})
  const [notifierSaving, setNotifierSaving] = useState<Record<string, boolean>>({})
  const [notifierTesting, setNotifierTesting] = useState<Record<string, boolean>>({})
  const [notifierTestResults, setNotifierTestResults] = useState<
    Record<string, { success: boolean; message: string } | null>
  >({})
  const [notifierLibraries, setNotifierLibraries] = useState<Record<string, NotifierLibrary[]>>({})
  const [loadingLibraries, setLoadingLibraries] = useState<Record<string, boolean>>({})
  const [expandedNotifiers, setExpandedNotifiers] = useState<Record<string, boolean>>({})

  useEffect(() => {
    loadSchedules()
    loadNotifiers()
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

  const loadNotifiers = async () => {
    try {
      const data = await api.getNotifiers()
      setNotifiers(data)

      // Initialise config and events state from loaded data
      const configs: Record<string, Record<string, string>> = {}
      const events: Record<string, Record<string, boolean>> = {}
      for (const notifier of data) {
        // Password fields come as empty strings from API
        // We keep them empty - backend will use saved values
        configs[notifier.id] = { ...notifier.config }
        events[notifier.id] = { ...notifier.events }
      }
      setNotifierConfigs(configs)
      setNotifierEvents(events)

      // Load libraries for notifiers that have dynamic select fields with saved values
      for (const notifier of data) {
        const hasDynamicSelect = Object.values(notifier.config_schema).some(
          (field) => field.type === 'select' && field.dynamic_options
        )
        const libraryId = notifier.config.library_id
        if (hasDynamicSelect && libraryId) {
          loadNotifierLibraries(notifier.id, libraryId)
        }
      }
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

  // Notification handlers
  const handleNotifierConfigChange = (notifierId: string, field: string, value: string) => {
    setNotifierConfigs((prev) => ({
      ...prev,
      [notifierId]: { ...prev[notifierId], [field]: value },
    }))
    // Clear test result when config changes
    setNotifierTestResults((prev) => ({ ...prev, [notifierId]: null }))
  }

  const handleNotifierEventChange = (notifierId: string, eventId: string, enabled: boolean) => {
    setNotifierEvents((prev) => ({
      ...prev,
      [notifierId]: { ...prev[notifierId], [eventId]: enabled },
    }))
    // Clear test result when events change
    setNotifierTestResults((prev) => ({ ...prev, [notifierId]: null }))
  }

  const handleNotifierToggle = async (notifier: Notifier) => {
    setNotifierSaving((prev) => ({ ...prev, [notifier.id]: true }))
    try {
      await api.updateNotifier(notifier.id, {
        enabled: !notifier.enabled,
        config: notifierConfigs[notifier.id] || {},
        events: notifierEvents[notifier.id] || {},
      })
      await loadNotifiers()
    } catch {
      // Ignore
    } finally {
      setNotifierSaving((prev) => ({ ...prev, [notifier.id]: false }))
    }
  }

  const handleNotifierSave = async (notifierId: string) => {
    setNotifierSaving((prev) => ({ ...prev, [notifierId]: true }))
    try {
      const notifier = notifiers.find((n) => n.id === notifierId)
      await api.updateNotifier(notifierId, {
        enabled: notifier?.enabled ?? false,
        config: notifierConfigs[notifierId] || {},
        events: notifierEvents[notifierId] || {},
      })
      await loadNotifiers()
      setNotifierTestResults((prev) => ({
        ...prev,
        [notifierId]: { success: true, message: 'Settings saved' },
      }))
    } catch (err) {
      setNotifierTestResults((prev) => ({
        ...prev,
        [notifierId]: {
          success: false,
          message: err instanceof Error ? err.message : 'Failed to save',
        },
      }))
    } finally {
      setNotifierSaving((prev) => ({ ...prev, [notifierId]: false }))
    }
  }

  const handleNotifierTest = async (notifierId: string) => {
    setNotifierTesting((prev) => ({ ...prev, [notifierId]: true }))
    setNotifierTestResults((prev) => ({ ...prev, [notifierId]: null }))
    try {
      const result = await api.testNotifier(notifierId, notifierConfigs[notifierId] || {})
      setNotifierTestResults((prev) => ({ ...prev, [notifierId]: result }))
    } catch (err) {
      setNotifierTestResults((prev) => ({
        ...prev,
        [notifierId]: {
          success: false,
          message: err instanceof Error ? err.message : 'Test failed',
        },
      }))
    } finally {
      setNotifierTesting((prev) => ({ ...prev, [notifierId]: false }))
    }
  }

  const loadNotifierLibraries = async (notifierId: string, savedLibraryId?: string) => {
    setLoadingLibraries((prev) => ({ ...prev, [notifierId]: true }))
    try {
      const result = await api.getNotifierLibraries(notifierId)
      setNotifierLibraries((prev) => ({ ...prev, [notifierId]: result.libraries }))
      // If a saved library ID was provided (from initial load), ensure it's preserved
      if (
        savedLibraryId &&
        result.libraries.some((lib: NotifierLibrary) => lib.id === savedLibraryId)
      ) {
        setNotifierConfigs((prev) => ({
          ...prev,
          [notifierId]: { ...prev[notifierId], library_id: savedLibraryId },
        }))
      }
    } catch {
      setNotifierLibraries((prev) => ({ ...prev, [notifierId]: [] }))
    } finally {
      setLoadingLibraries((prev) => ({ ...prev, [notifierId]: false }))
    }
  }

  const toggleNotifierExpanded = (notifierId: string) => {
    setExpandedNotifiers((prev) => ({ ...prev, [notifierId]: !prev[notifierId] }))
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <div className="space-y-6">
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

        {/* Notifications Section */}
        <div>
          <div className="mb-4">
            <h2 className="flex items-center gap-2 font-medium">
              <Bell size={18} />
              Notifications
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Configure integrations to notify external services when events occur. Sensitive fields
              like tokens and API keys can also be set via environment variables (e.g.
              NOTIFICATION_PLEX_TOKEN).
            </p>
          </div>

          <div className="space-y-3">
            {notifiers.map((notifier) => {
              const isExpanded = expandedNotifiers[notifier.id]
              const hasConfig = Object.keys(notifier.config_schema).length > 0

              return (
                <div
                  key={notifier.id}
                  className={`rounded-md border bg-[var(--background)] transition-colors ${
                    notifier.enabled ? 'border-[var(--accent)]/30' : 'border-[var(--border)]'
                  }`}
                >
                  {/* Header - always visible */}
                  <div
                    className="flex cursor-pointer items-center justify-between p-4"
                    onClick={() => toggleNotifierExpanded(notifier.id)}
                  >
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        className="text-[var(--muted)]"
                        aria-label={isExpanded ? 'Collapse' : 'Expand'}
                      >
                        {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                      </button>
                      <div>
                        <h3 className="font-medium">{notifier.name}</h3>
                        <p className="text-xs text-[var(--muted)]">
                          {notifier.enabled ? (
                            <span className="text-green-500">Enabled</span>
                          ) : (
                            'Disabled'
                          )}
                          {notifier.enabled &&
                            notifier.supported_events.filter(
                              (e) => notifierEvents[notifier.id]?.[e.id] ?? e.default
                            ).length > 0 && (
                              <span>
                                {' • '}
                                {notifier.supported_events
                                  .filter((e) => notifierEvents[notifier.id]?.[e.id] ?? e.default)
                                  .map((e) => e.label)
                                  .join(', ')}
                              </span>
                            )}
                        </p>
                      </div>
                    </div>
                    <div onClick={(e) => e.stopPropagation()} className="flex items-center gap-2">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={notifier.enabled}
                        onClick={() => handleNotifierToggle(notifier)}
                        disabled={notifierSaving[notifier.id]}
                        className={`relative h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                          notifier.enabled ? 'bg-[var(--accent)]' : 'bg-[var(--border)]'
                        }`}
                      >
                        <span
                          className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                            notifier.enabled ? 'translate-x-4' : ''
                          }`}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="border-t border-[var(--border)] p-4">
                      {/* Configuration fields */}
                      {hasConfig && (
                        <div className="space-y-3">
                          {Object.entries(notifier.config_schema).map(
                            ([fieldName, fieldSchema]) => (
                              <div key={fieldName}>
                                <label className="mb-1 flex items-center gap-1 text-sm font-medium">
                                  {fieldSchema.label}
                                  {fieldSchema.required && (
                                    <span className="text-[var(--error)]">*</span>
                                  )}
                                </label>
                                {fieldSchema.help && (
                                  <p className="mb-2 text-xs text-[var(--muted)]">
                                    {fieldSchema.help}
                                  </p>
                                )}
                                {fieldSchema.type === 'select' && fieldSchema.dynamic_options ? (
                                  <div className="flex gap-2">
                                    <select
                                      value={notifierConfigs[notifier.id]?.[fieldName] || ''}
                                      onChange={(e) =>
                                        handleNotifierConfigChange(
                                          notifier.id,
                                          fieldName,
                                          e.target.value
                                        )
                                      }
                                      className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
                                    >
                                      <option value="">
                                        {fieldSchema.placeholder || 'Select...'}
                                      </option>
                                      {(notifierLibraries[notifier.id] || []).map((lib) => (
                                        <option key={lib.id} value={lib.id}>
                                          {lib.title} ({lib.type})
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        loadNotifierLibraries(
                                          notifier.id,
                                          notifierConfigs[notifier.id]?.library_id
                                        )
                                      }
                                      disabled={loadingLibraries[notifier.id]}
                                      className="rounded-md border border-[var(--border)] px-3 py-2 text-[var(--muted)] transition-colors hover:bg-[var(--border)] disabled:opacity-50"
                                      title="Refresh libraries"
                                    >
                                      {loadingLibraries[notifier.id] ? (
                                        <Loader2 size={16} className="animate-spin" />
                                      ) : (
                                        <RefreshCw size={16} />
                                      )}
                                    </button>
                                  </div>
                                ) : (
                                  <input
                                    type={fieldSchema.type === 'password' ? 'password' : 'text'}
                                    value={notifierConfigs[notifier.id]?.[fieldName] || ''}
                                    onChange={(e) =>
                                      handleNotifierConfigChange(
                                        notifier.id,
                                        fieldName,
                                        e.target.value
                                      )
                                    }
                                    placeholder={
                                      fieldSchema.type === 'password' &&
                                      notifier.config[`_${fieldName}_env`]
                                        ? '(set via environment variable)'
                                        : fieldSchema.type === 'password' &&
                                            notifier.config[`_${fieldName}_set`]
                                          ? '••••••••  (saved)'
                                          : fieldSchema.placeholder
                                    }
                                    disabled={
                                      !!(
                                        fieldSchema.type === 'password' &&
                                        notifier.config[`_${fieldName}_env`]
                                      )
                                    }
                                    className={`w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none ${
                                      fieldSchema.type === 'password' &&
                                      notifier.config[`_${fieldName}_env`]
                                        ? 'cursor-not-allowed opacity-60'
                                        : ''
                                    }`}
                                  />
                                )}
                              </div>
                            )
                          )}
                        </div>
                      )}

                      {/* Event Options */}
                      {notifier.supported_events.length > 0 && (
                        <div
                          className={`${hasConfig ? 'mt-4 border-t border-[var(--border)] pt-4' : ''}`}
                        >
                          <h4 className="mb-3 text-sm font-medium">Trigger Events</h4>
                          <div className="space-y-3">
                            {notifier.supported_events.map((event) => (
                              <ToggleOption
                                key={event.id}
                                label={event.label}
                                description={event.description}
                                checked={notifierEvents[notifier.id]?.[event.id] ?? event.default}
                                onChange={() =>
                                  handleNotifierEventChange(
                                    notifier.id,
                                    event.id,
                                    !(notifierEvents[notifier.id]?.[event.id] ?? event.default)
                                  )
                                }
                              />
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Test result */}
                      {notifierTestResults[notifier.id] && (
                        <div
                          className={`mt-4 flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
                            notifierTestResults[notifier.id]?.success
                              ? 'bg-green-500/10 text-green-500'
                              : 'bg-red-500/10 text-red-500'
                          }`}
                        >
                          {notifierTestResults[notifier.id]?.success ? (
                            <CheckCircle2 size={14} />
                          ) : (
                            <AlertCircle size={14} />
                          )}
                          {notifierTestResults[notifier.id]?.message}
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="mt-4 flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleNotifierSave(notifier.id)}
                          disabled={notifierSaving[notifier.id]}
                          className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
                        >
                          {notifierSaving[notifier.id] ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleNotifierTest(notifier.id)}
                          disabled={notifierTesting[notifier.id]}
                          className="rounded-md border border-[var(--border)] px-4 py-2 text-sm transition-colors hover:bg-[var(--border)] disabled:opacity-50"
                        >
                          {notifierTesting[notifier.id] ? (
                            <span className="flex items-center gap-2">
                              <Loader2 size={14} className="animate-spin" />
                              Testing...
                            </span>
                          ) : (
                            'Test Connection'
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}

            {notifiers.length === 0 && (
              <p className="text-sm text-[var(--muted)]">No notification integrations available.</p>
            )}
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
          <div className="space-y-1 rounded-md border border-[var(--border)] bg-[var(--card)] p-4 font-mono text-sm text-[var(--muted)]">
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
