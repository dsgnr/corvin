'use client'

import { useState } from 'react'
import { ExternalLink } from 'lucide-react'

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState(
    typeof window !== 'undefined' ? localStorage.getItem('corvin_api_url') || '' : ''
  )
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    if (apiUrl) {
      localStorage.setItem('corvin_api_url', apiUrl)
    } else {
      localStorage.removeItem('corvin_api_url')
    }
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
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
