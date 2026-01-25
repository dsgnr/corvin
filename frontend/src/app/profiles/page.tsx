'use client'

import { useEffect, useState, Suspense, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import { api, Profile, ProfileOptions } from '@/lib/api'
import { Plus, Trash2, Edit2, Loader2, Copy, X, Check, AlertCircle } from 'lucide-react'
import { Select } from '@/components/Select'
import { ToggleOption } from '@/components/ToggleOption'
import { FormField, ValidatedInput } from '@/components/FormField'
import { validators } from '@/lib/validation'

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

interface FormErrors {
  name: string | null
  output_template: string | null
  subtitle_languages: string | null
  audio_track_language: string | null
}

interface TouchedFields {
  name: boolean
  output_template: boolean
  subtitle_languages: boolean
  audio_track_language: boolean
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
  const [errors, setErrors] = useState<FormErrors>({
    name: null,
    output_template: null,
    subtitle_languages: null,
    audio_track_language: null,
  })
  const [touched, setTouched] = useState<TouchedFields>({
    name: false,
    output_template: false,
    subtitle_languages: false,
    audio_track_language: false,
  })

  const validateName = useCallback((value: string): string | null => {
    const required = validators.required(value, 'Name')
    if (required) return required
    const minLen = validators.minLength(value, 2, 'Name')
    if (minLen) return minLen
    const maxLen = validators.maxLength(value, 50, 'Name')
    if (maxLen) return maxLen
    return null
  }, [])

  const validateOutputTemplate = useCallback((value: string): string | null => {
    const required = validators.required(value, 'Output template')
    if (required) return required
    return validators.outputTemplate(value)
  }, [])

  const validateLanguageCodes = useCallback((value: string): string | null => {
    if (!value) return null
    return validators.languageCodes(value)
  }, [])

  const handleFieldChange = (field: keyof FormErrors, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (touched[field]) {
      let error: string | null = null
      if (field === 'name') error = validateName(value)
      else if (field === 'output_template') error = validateOutputTemplate(value)
      else if (field === 'subtitle_languages' || field === 'audio_track_language') {
        error = validateLanguageCodes(value)
      }
      setErrors((prev) => ({ ...prev, [field]: error }))
    }
  }

  const handleBlur = (field: keyof TouchedFields) => {
    setTouched((prev) => ({ ...prev, [field]: true }))
    let error: string | null = null
    if (field === 'name') error = validateName(form.name)
    else if (field === 'output_template') error = validateOutputTemplate(form.output_template)
    else if (field === 'subtitle_languages') error = validateLanguageCodes(form.subtitle_languages)
    else if (field === 'audio_track_language')
      error = validateLanguageCodes(form.audio_track_language)
    setErrors((prev) => ({ ...prev, [field]: error }))
  }

  const validateAll = (): boolean => {
    const nameError = validateName(form.name)
    const templateError = validateOutputTemplate(form.output_template)
    const subtitleError = validateLanguageCodes(form.subtitle_languages)
    const audioError = validateLanguageCodes(form.audio_track_language)

    setErrors({
      name: nameError,
      output_template: templateError,
      subtitle_languages: subtitleError,
      audio_track_language: audioError,
    })
    setTouched({
      name: true,
      output_template: true,
      subtitle_languages: true,
      audio_track_language: true,
    })

    return !nameError && !templateError && !subtitleError && !audioError
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateAll()) return

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

  const isFormValid =
    form.name.length >= 2 &&
    form.output_template.length > 0 &&
    !errors.name &&
    !errors.output_template &&
    !errors.subtitle_languages &&
    !errors.audio_track_language

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-[var(--accent)] bg-[var(--card)] p-4"
    >
      <FormField
        label="Name"
        required
        error={touched.name ? errors.name : null}
        showSuccess={touched.name && !errors.name && form.name.length > 0}
      >
        <ValidatedInput
          type="text"
          value={form.name}
          onChange={(e) => handleFieldChange('name', e.target.value)}
          onBlur={() => handleBlur('name')}
          error={errors.name}
          touched={touched.name}
          placeholder="My Profile"
          autoFocus
        />
      </FormField>

      <FormField
        label="Output Template"
        description={
          <>
            yt-dlp output path template. Use variables like %(uploader)s, %(title)s, %(ext)s.{' '}
            <a
              href="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#output-template"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--accent)] hover:underline"
            >
              See yt-dlp docs
            </a>
          </>
        }
        required
        error={touched.output_template ? errors.output_template : null}
        showSuccess={
          touched.output_template && !errors.output_template && form.output_template.length > 0
        }
      >
        <ValidatedInput
          type="text"
          value={form.output_template}
          onChange={(e) => handleFieldChange('output_template', e.target.value)}
          onBlur={() => handleBlur('output_template')}
          error={errors.output_template}
          touched={touched.output_template}
          className="font-mono text-sm"
        />
      </FormField>

      <FormField
        label="Output Format"
        description="Remux video to a specific container format (leave empty to keep original)"
      >
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
      </FormField>

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

        <FormField
          label="Subtitle languages"
          description="Comma-separated language codes (e.g., en, es, fr)"
          error={touched.subtitle_languages ? errors.subtitle_languages : null}
        >
          <ValidatedInput
            type="text"
            value={form.subtitle_languages}
            onChange={(e) => handleFieldChange('subtitle_languages', e.target.value)}
            onBlur={() => handleBlur('subtitle_languages')}
            error={errors.subtitle_languages}
            touched={touched.subtitle_languages}
            className="text-sm"
            placeholder="en"
          />
        </FormField>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <FormField
          label="Audio language"
          description="Preferred audio track language code (leave empty for default)"
          error={touched.audio_track_language ? errors.audio_track_language : null}
        >
          <ValidatedInput
            type="text"
            value={form.audio_track_language}
            onChange={(e) => handleFieldChange('audio_track_language', e.target.value)}
            onBlur={() => handleBlur('audio_track_language')}
            error={errors.audio_track_language}
            touched={touched.audio_track_language}
            className="text-sm"
            placeholder="en"
          />
        </FormField>
      </div>

      <div className="space-y-4 border-t border-[var(--border)] pt-4">
        <FormField
          label="SponsorBlock"
          description="Automatically handle sponsored segments using SponsorBlock data"
        >
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
        </FormField>
      </div>

      <div className="flex items-center justify-end gap-2 pt-2">
        {error && (
          <p className="mr-auto flex items-center gap-1 text-sm text-[var(--error)]">
            <AlertCircle size={14} />
            {error}
          </p>
        )}
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
