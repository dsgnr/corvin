'use client'

import { useEffect, useState } from 'react'
import { Clock, ExternalLink, Plus, Trash2 } from 'lucide-react'
import { api, DownloadSchedule, ScheduleStatus } from '@/lib/api'

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

const defaultScheduleForm: ScheduleFormData = {
  name: '',
  enabled: true,
  days_of_week: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
  start_time: '00:00',
  end_time: '23:59',
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

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
    setScheduleForm((prev) => ({
      ...prev,
      days_of_week: prev.days_of_week.includes(day)
        ? prev.days_of_week.filter((d) => d !== day)
        : [...prev.days_of_week, day],
    }))
  }

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
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-medium">Download Schedules</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Define time windows when automatic downloads are allowed. Syncing always runs
                regardless of schedule. Downloads are always allowed if no schedules are enabled.
              </p>
            </div>
            {scheduleStatus && (
              <div
                className={`flex items-center gap-2 rounded-full px-3 py-1 text-sm ${
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
              <div>
                <label className="mb-1 block text-sm text-[var(--muted)]">Schedule Name</label>
                <input
                  type="text"
                  value={scheduleForm.name}
                  onChange={(e) => setScheduleForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Night Downloads"
                  required
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-[var(--muted)]">Days of Week</label>
                <div className="flex flex-wrap gap-2">
                  {DAYS_OF_WEEK.map((day) => (
                    <button
                      key={day.value}
                      type="button"
                      onClick={() => toggleDay(day.value)}
                      className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                        scheduleForm.days_of_week.includes(day.value)
                          ? 'bg-[var(--accent)] text-white'
                          : 'bg-[var(--card)] text-[var(--muted)] hover:bg-[var(--border)]'
                      }`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">Start Time</label>
                  <input
                    type="time"
                    value={scheduleForm.start_time}
                    onChange={(e) =>
                      setScheduleForm((prev) => ({ ...prev, start_time: e.target.value }))
                    }
                    required
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-[var(--muted)]">End Time</label>
                  <input
                    type="time"
                    value={scheduleForm.end_time}
                    onChange={(e) =>
                      setScheduleForm((prev) => ({ ...prev, end_time: e.target.value }))
                    }
                    required
                    className="w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
                  />
                </div>
              </div>

              {scheduleError && <p className="text-sm text-red-500">{scheduleError}</p>}

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={scheduleSaving || scheduleForm.days_of_week.length === 0}
                  className="rounded-md bg-[var(--accent)] px-4 py-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
                >
                  {scheduleSaving ? 'Saving...' : editingSchedule ? 'Update' : 'Create'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowScheduleForm(false)
                    setEditingSchedule(null)
                    setScheduleForm(defaultScheduleForm)
                    setScheduleError(null)
                  }}
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
