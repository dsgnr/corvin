'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { api, Profile, ProfileOptions } from '@/lib/api'
import { Plus, Trash2, Edit2, Loader2, Copy, X, Check } from 'lucide-react'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'

export default function ProfilesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center">
          <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
        </div>
      }
    >
      <ProfilesContent />
    </Suspense>
  )
}

function ProfilesContent() {
  const searchParams = useSearchParams()
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [profileOptions, setProfileOptions] = useState<ProfileOptions | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [profilesData, options] = await Promise.all([
          api.getProfiles(),
          api.getProfileOptions(),
        ])
        setProfiles(profilesData)
        setProfileOptions(options)

        // Check for edit query param
        const editParam = searchParams.get('edit')
        if (editParam) {
          const editId = parseInt(editParam, 10)
          if (!isNaN(editId) && profilesData.some((p) => p.id === editId)) {
            setEditingId(editId)
          }
        }
      } catch (err) {
        console.error('Failed to fetch profiles:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [searchParams])

  const handleDelete = async (profile: Profile) => {
    if (!confirm(`Delete profile "${profile.name}"?`)) return
    try {
      await api.deleteProfile(profile.id)
      setProfiles(profiles.filter((p) => p.id !== profile.id))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete'
      alert(message)
    }
  }

  const handleSave = async (data: Partial<Profile>, id?: number) => {
    if (id) {
      const updated = await api.updateProfile(id, data)
      setProfiles(profiles.map((p) => (p.id === updated.id ? updated : p)))
    } else {
      const created = await api.createProfile(data)
      setProfiles([...profiles, created])
    }
    setEditingId(null)
  }

  const handleDuplicate = (profile: Profile) => {
    const copy: Partial<Profile> = { ...profile }
    delete copy.id
    copy.name = `${profile.name} (copy)`
    handleSave(copy)
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin text-[var(--muted)]" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold">Profiles</h1>
        {editingId !== 'new' && (
          <button
            onClick={() => setEditingId('new')}
            className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-2 text-sm text-white transition-colors hover:bg-[var(--accent-hover)] sm:py-1.5"
          >
            <Plus size={14} />
            Add Profile
          </button>
        )}
      </div>

      <div className="grid gap-4">
        {editingId === 'new' && profileOptions && (
          <ProfileForm
            defaults={profileOptions.defaults}
            sponsorBlockOpts={profileOptions.sponsorblock}
            outputFormats={profileOptions.output_formats}
            onSave={(data) => handleSave(data)}
            onCancel={() => setEditingId(null)}
          />
        )}

        {profiles.length === 0 && editingId !== 'new' ? (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-8 text-center">
            <p className="text-[var(--muted)]">No profiles yet. Create one to get started.</p>
          </div>
        ) : (
          profiles.map((profile) =>
            editingId === profile.id && profileOptions ? (
              <ProfileForm
                key={profile.id}
                profile={profile}
                defaults={profileOptions.defaults}
                sponsorBlockOpts={profileOptions.sponsorblock}
                outputFormats={profileOptions.output_formats}
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
          )
        )}
      </div>
    </div>
  )
}

function ProfileCard({
  profile,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  profile: Profile
  onEdit: () => void
  onDuplicate: () => void
  onDelete: () => void
}) {
  const features = []
  if (profile.embed_metadata) features.push('Metadata')
  if (profile.embed_thumbnail) features.push('Thumbnail')
  if (profile.download_subtitles) features.push('Subtitles')
  if (!profile.include_shorts) features.push('No Shorts')
  if (!profile.include_live) features.push('No Live')
  if (profile.sponsorblock_behaviour !== 'disabled') features.push('SponsorBlock')

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-medium">{profile.name}</h3>
          <p className="mt-1 font-mono text-sm text-[var(--muted)]">{profile.output_template}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {features.map((f) => (
              <span
                key={f}
                className="rounded bg-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted)]"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onDuplicate}
            className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]"
            title="Duplicate"
          >
            <Copy size={16} />
          </button>
          <button
            onClick={onEdit}
            className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]"
            title="Edit"
          >
            <Edit2 size={16} />
          </button>
          <button
            onClick={onDelete}
            className="rounded-md p-2 text-[var(--muted)] transition-colors hover:bg-[var(--card-hover)] hover:text-[var(--error)]"
            title="Delete"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function ProfileForm({
  profile,
  defaults,
  sponsorBlockOpts,
  outputFormats,
  onSave,
  onCancel,
}: {
  profile?: Profile
  defaults: ProfileOptions['defaults']
  sponsorBlockOpts: ProfileOptions['sponsorblock']
  outputFormats: string[]
  onSave: (data: Partial<Profile>) => Promise<void>
  onCancel: () => void
}) {
  const [form, setForm] = useState<{
    name: string
    output_template: string
    output_format: string
    embed_metadata: boolean
    embed_thumbnail: boolean
    include_shorts: boolean
    include_live: boolean
    download_subtitles: boolean
    embed_subtitles: boolean
    auto_generated_subtitles: boolean
    subtitle_languages: string
    audio_track_language: string
    sponsorblock_behaviour: string
    sponsorblock_categories: string[]
    extra_args: string
  }>({
    name: profile?.name || '',
    output_template: profile?.output_template || defaults.output_template,
    output_format: profile?.output_format || defaults.output_format,
    embed_metadata: profile?.embed_metadata ?? defaults.embed_metadata,
    embed_thumbnail: profile?.embed_thumbnail ?? defaults.embed_thumbnail,
    include_shorts: profile?.include_shorts ?? defaults.include_shorts,
    include_live: profile?.include_live ?? defaults.include_live,
    download_subtitles: profile?.download_subtitles ?? defaults.download_subtitles,
    embed_subtitles: profile?.embed_subtitles ?? defaults.embed_subtitles,
    auto_generated_subtitles:
      profile?.auto_generated_subtitles ?? defaults.auto_generated_subtitles,
    subtitle_languages: profile?.subtitle_languages || defaults.subtitle_languages,
    audio_track_language: profile?.audio_track_language || defaults.audio_track_language,
    sponsorblock_behaviour: profile?.sponsorblock_behaviour || defaults.sponsorblock_behaviour,
    sponsorblock_categories: profile?.sponsorblock_categories || defaults.sponsorblock_categories,
    extra_args: profile?.extra_args || defaults.extra_args,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSave(form)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save profile'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  const toggleCategory = (cat: string) => {
    const current = form.sponsorblock_categories
    const updated = current.includes(cat)
      ? current.filter((c: string) => c !== cat)
      : [...current, cat]
    setForm({ ...form, sponsorblock_categories: updated })
  }

  const selectedCategories = form.sponsorblock_categories

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <div>
        <label className="mb-1 block text-sm font-medium">Name</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 focus:border-[var(--accent)] focus:outline-none"
          required
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">Output Template</label>
        <p className="mb-2 text-xs text-[var(--muted)]">
          yt-dlp output path template. Default outputs in a format Plex likes, (eg. s2026e0101 -
          title.ext). Use variables like %(uploader)s, %(title)s, %(ext)s.{' '}
          <a
            href="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#output-template"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--accent)] hover:underline"
          >
            See yt-dlp docs for all options
          </a>
        </p>
        <input
          type="text"
          value={form.output_template}
          onChange={(e) => setForm({ ...form, output_template: e.target.value })}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 font-mono text-sm focus:border-[var(--accent)] focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium">Output Format</label>
        <p className="mb-2 text-xs text-[var(--muted)]">
          Remux video to a specific container format (leave empty to keep original)
        </p>
        <Select
          value={form.output_format}
          onChange={(e) => setForm({ ...form, output_format: e.target.value })}
        >
          <option value="">Keep original</option>
          {outputFormats.map((fmt: string) => (
            <option key={fmt} value={fmt}>
              {fmt}
            </option>
          ))}
        </Select>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
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
          label="Include shorts"
          description="Include YouTube Shorts when syncing channels"
          checked={form.include_shorts}
          onChange={() => setForm({ ...form, include_shorts: !form.include_shorts })}
        />

        <ToggleOption
          label="Include live recordings"
          description="Include livestream recordings when syncing channels"
          checked={form.include_live}
          onChange={() => setForm({ ...form, include_live: !form.include_live })}
        />
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
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
          onChange={() =>
            setForm({ ...form, auto_generated_subtitles: !form.auto_generated_subtitles })
          }
        />

        <div>
          <label className="mb-1 block text-sm font-medium">Subtitle languages</label>
          <p className="mb-2 text-xs text-[var(--muted)]">
            Comma-separated language codes (e.g. en, es, fr)
          </p>
          <input
            type="text"
            value={form.subtitle_languages}
            onChange={(e) => setForm({ ...form, subtitle_languages: e.target.value })}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
            placeholder="en"
          />
        </div>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Audio language</label>
          <p className="mb-2 text-xs text-[var(--muted)]">
            Preferred audio track language code (leave empty for default)
          </p>
          <input
            type="text"
            value={form.audio_track_language}
            onChange={(e) => setForm({ ...form, audio_track_language: e.target.value })}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
            placeholder="en"
          />
        </div>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <div>
          <label className="mb-1 block text-sm font-medium">SponsorBlock</label>
          <p className="mb-2 text-xs text-[var(--muted)]">
            Automatically handle sponsored segments using SponsorBlock data
          </p>
          <Select
            value={form.sponsorblock_behaviour}
            onChange={(e) => setForm({ ...form, sponsorblock_behaviour: e.target.value })}
          >
            <option value="disabled">Disabled</option>
            <option value="delete">Remove segments</option>
            <option value="mark_chapter">Mark as chapters</option>
          </Select>
          {form.sponsorblock_behaviour !== 'disabled' && (
            <div className="mt-3 flex flex-wrap gap-2">
              {sponsorBlockOpts.categories.map((cat: string) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className={`rounded px-2 py-1 text-xs transition-colors ${
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
          disabled={saving || !form.name}
          className="rounded-md bg-[var(--accent)] p-2 text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
        >
          <Check size={18} />
        </button>
      </div>
    </form>
  )
}
