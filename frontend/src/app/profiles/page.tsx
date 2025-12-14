'use client'

import { useEffect, useState } from 'react'
import { api, Profile, SponsorBlockOptions } from '@/lib/api'
import { Plus, Trash2, Edit2, Loader2, Copy, X, Check } from 'lucide-react'

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [sponsorBlockOpts, setSponsorBlockOpts] = useState<SponsorBlockOptions | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)

  const fetchData = async () => {
    try {
      const [profilesData, sbOpts] = await Promise.all([
        api.getProfiles(),
        api.getSponsorBlockOptions(),
      ])
      setProfiles(profilesData)
      setSponsorBlockOpts(sbOpts)
    } catch (err) {
      console.error('Failed to fetch profiles:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleDelete = async (profile: Profile) => {
    if (!confirm(`Delete profile "${profile.name}"?`)) return
    try {
      await api.deleteProfile(profile.id)
      setProfiles(profiles.filter(p => p.id !== profile.id))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete'
      alert(message)
    }
  }

  const handleSave = async (data: Partial<Profile>, id?: number) => {
    try {
      if (id) {
        const updated = await api.updateProfile(id, data)
        setProfiles(profiles.map(p => p.id === updated.id ? updated : p))
      } else {
        const created = await api.createProfile(data)
        setProfiles([...profiles, created])
      }
      setEditingId(null)
    } catch (err) {
      console.error('Failed to save:', err)
    }
  }

  const handleDuplicate = (profile: Profile) => {
    const copy: Partial<Profile> = { ...profile }
    delete copy.id
    copy.name = `${profile.name} (copy)`
    handleSave(copy)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Profiles</h1>
        {editingId !== 'new' && (
          <button
            onClick={() => setEditingId('new')}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-md transition-colors"
          >
            <Plus size={16} />
            Add Profile
          </button>
        )}
      </div>

      <div className="grid gap-4">
        {editingId === 'new' && sponsorBlockOpts && (
          <ProfileForm
            sponsorBlockOpts={sponsorBlockOpts}
            onSave={(data) => handleSave(data)}
            onCancel={() => setEditingId(null)}
          />
        )}

        {profiles.length === 0 && editingId !== 'new' ? (
          <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-8 text-center">
            <p className="text-[var(--muted)]">No profiles yet. Create one to get started.</p>
          </div>
        ) : (
          profiles.map(profile => (
            editingId === profile.id && sponsorBlockOpts ? (
              <ProfileForm
                key={profile.id}
                profile={profile}
                sponsorBlockOpts={sponsorBlockOpts}
                onSave={(data) => handleSave(data, profile.id)}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <ProfileCard
                key={profile.id}
                profile={profile}
                onEdit={() => setEditingId(profile.id)}
                onDuplicate={() => handleDuplicate(profile)}
                onDelete={() => handleDelete(profile)}
              />
            )
          ))
        )}
      </div>
    </div>
  )
}

function ProfileCard({ profile, onEdit, onDuplicate, onDelete }: {
  profile: Profile
  onEdit: () => void
  onDuplicate: () => void
  onDelete: () => void
}) {
  const features = []
  if (profile.embed_metadata) features.push('Metadata')
  if (profile.embed_thumbnail) features.push('Thumbnail')
  if (profile.download_subtitles) features.push('Subtitles')
  if (profile.exclude_shorts) features.push('No Shorts')
  if (profile.sponsorblock_behavior !== 'disabled') features.push('SponsorBlock')

  return (
    <div className="bg-[var(--card)] rounded-lg border border-[var(--border)] p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-medium">{profile.name}</h3>
          <p className="text-sm text-[var(--muted)] mt-1 font-mono">{profile.output_template}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {features.map(f => (
              <span key={f} className="text-xs px-2 py-0.5 rounded bg-[var(--border)] text-[var(--muted)]">
                {f}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onDuplicate}
            className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
            title="Duplicate"
          >
            <Copy size={16} />
          </button>
          <button
            onClick={onEdit}
            className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
            title="Edit"
          >
            <Edit2 size={16} />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--error)] transition-colors"
            title="Delete"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function ProfileForm({ profile, sponsorBlockOpts, onSave, onCancel }: {
  profile?: Profile
  sponsorBlockOpts: SponsorBlockOptions
  onSave: (data: Partial<Profile>) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState({
    name: profile?.name || '',
    output_template: profile?.output_template || '%(uploader)s/%(title)s.%(ext)s',
    embed_metadata: profile?.embed_metadata ?? true,
    embed_thumbnail: profile?.embed_thumbnail ?? false,
    exclude_shorts: profile?.exclude_shorts ?? false,
    download_subtitles: profile?.download_subtitles ?? false,
    embed_subtitles: profile?.embed_subtitles ?? false,
    auto_generated_subtitles: profile?.auto_generated_subtitles ?? false,
    subtitle_languages: profile?.subtitle_languages || 'en',
    audio_track_language: profile?.audio_track_language || '',
    sponsorblock_behavior: profile?.sponsorblock_behavior || 'disabled',
    sponsorblock_categories: profile?.sponsorblock_categories || '',
    extra_args: profile?.extra_args || '{}',
  })
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    await onSave(form)
    setSaving(false)
  }

  const toggleCategory = (cat: string) => {
    const current = form.sponsorblock_categories.split(',').filter(Boolean)
    const updated = current.includes(cat)
      ? current.filter(c => c !== cat)
      : [...current, cat]
    setForm({ ...form, sponsorblock_categories: updated.join(',') })
  }

  const selectedCategories = form.sponsorblock_categories.split(',').filter(Boolean)

  return (
    <form onSubmit={handleSubmit} className="bg-[var(--card)] rounded-lg border border-[var(--accent)] p-4 space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">Name</label>
        <input
          type="text"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Output Template</label>
        <p className="text-xs text-[var(--muted)] mb-2">yt-dlp output path template. Use variables like %(uploader)s, %(title)s, %(ext)s</p>
        <input
          type="text"
          value={form.output_template}
          onChange={e => setForm({ ...form, output_template: e.target.value })}
          className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)] font-mono text-sm"
        />
      </div>

      <div className="space-y-4 pt-4 border-t border-[var(--border)]">
        <ToggleOption
          label="Embed metadata"
          description="Write video info (title, description, upload date) into the file"
          checked={form.embed_metadata}
          onChange={() => setForm({ ...form, embed_metadata: !form.embed_metadata })}
        />

        <ToggleOption
          label="Embed thumbnail"
          description="Download and embed the video thumbnail as cover art"
          checked={form.embed_thumbnail}
          onChange={() => setForm({ ...form, embed_thumbnail: !form.embed_thumbnail })}
        />

        <ToggleOption
          label="Exclude shorts"
          description="Skip YouTube Shorts when syncing channels"
          checked={form.exclude_shorts}
          onChange={() => setForm({ ...form, exclude_shorts: !form.exclude_shorts })}
        />
      </div>

      <div className="space-y-4 pt-4 border-t border-[var(--border)]">
        <p className="text-sm font-medium">Subtitles</p>

        <ToggleOption
          label="Download subtitles"
          description="Save subtitle files alongside the video"
          checked={form.download_subtitles}
          onChange={() => setForm({ ...form, download_subtitles: !form.download_subtitles })}
        />

        <ToggleOption
          label="Embed subtitles"
          description="Embed subtitles directly into the video file"
          checked={form.embed_subtitles}
          onChange={() => setForm({ ...form, embed_subtitles: !form.embed_subtitles })}
        />

        <ToggleOption
          label="Auto-generated subtitles"
          description="Include YouTube's auto-generated captions if no manual subtitles exist"
          checked={form.auto_generated_subtitles}
          onChange={() => setForm({ ...form, auto_generated_subtitles: !form.auto_generated_subtitles })}
        />

        <div>
          <label className="block text-sm font-medium mb-1">Subtitle languages</label>
          <p className="text-xs text-[var(--muted)] mb-2">Comma-separated language codes (e.g. en, es, fr)</p>
          <input
            type="text"
            value={form.subtitle_languages}
            onChange={e => setForm({ ...form, subtitle_languages: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)] text-sm"
            placeholder="en"
          />
        </div>
      </div>

      <div className="space-y-4 pt-4 border-t border-[var(--border)]">
        <div>
          <label className="block text-sm font-medium mb-1">Audio language</label>
          <p className="text-xs text-[var(--muted)] mb-2">Preferred audio track language code (leave empty for default)</p>
          <input
            type="text"
            value={form.audio_track_language}
            onChange={e => setForm({ ...form, audio_track_language: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)] text-sm"
            placeholder="en"
          />
        </div>
      </div>

      <div className="space-y-4 pt-4 border-t border-[var(--border)]">
        <div>
          <label className="block text-sm font-medium mb-1">SponsorBlock</label>
          <p className="text-xs text-[var(--muted)] mb-2">Automatically handle sponsored segments using SponsorBlock data</p>
          <select
            value={form.sponsorblock_behavior}
            onChange={e => setForm({ ...form, sponsorblock_behavior: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--accent)]"
          >
            <option value="disabled">Disabled</option>
            <option value="delete">Remove segments</option>
            <option value="mark_chapter">Mark as chapters</option>
          </select>
          {form.sponsorblock_behavior !== 'disabled' && (
            <div className="flex flex-wrap gap-2 mt-3">
              {sponsorBlockOpts.categories.map(cat => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${
                    selectedCategories.includes(cat)
                      ? 'bg-[var(--accent)] text-white'
                      : 'bg-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]'
                  }`}
                >
                  {sponsorBlockOpts.category_labels[cat] || cat}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="p-2 rounded-md hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
        >
          <X size={18} />
        </button>
        <button
          type="submit"
          disabled={saving || !form.name}
          className="p-2 rounded-md bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white transition-colors disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}

function ToggleOption({ label, description, checked, onChange }: {
  label: string
  description: string
  checked: boolean
  onChange: () => void
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-[var(--muted)]">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${checked ? 'bg-[var(--accent)]' : 'bg-[var(--border)]'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${checked ? 'translate-x-4' : ''}`} />
      </button>
    </div>
  )
}
