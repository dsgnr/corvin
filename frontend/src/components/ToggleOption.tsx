'use client'

interface ToggleOptionProps {
  label: string
  description: string
  checked: boolean
  onChange: () => void
  disabled?: boolean
}

/**
 * Reusable toggle switch component for boolean options.
 * Used in forms for settings like "enabled", "auto download", etc.
 */
export function ToggleOption({
  label,
  description,
  checked,
  onChange,
  disabled,
}: ToggleOptionProps) {
  return (
    <div className={`flex items-start justify-between gap-4 ${disabled ? 'opacity-50' : ''}`}>
      <div className="flex-1">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-[var(--muted-foreground)]">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        disabled={disabled}
        className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-all duration-200 disabled:cursor-not-allowed ${
          checked
            ? 'bg-[var(--accent)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.1)]'
            : 'bg-[var(--border)] shadow-[inset_0_1px_2px_rgba(0,0,0,0.3)]'
        }`}
      >
        <span
          className={`absolute top-1 left-1 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
    </div>
  )
}
