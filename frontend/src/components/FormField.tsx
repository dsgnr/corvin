'use client'

import { ReactNode } from 'react'
import { AlertCircle, CheckCircle2 } from 'lucide-react'

interface FormFieldProps {
  label: string
  description?: ReactNode
  error?: string | null
  showSuccess?: boolean
  required?: boolean
  children: ReactNode
}

export function FormField({
  label,
  description,
  error,
  showSuccess,
  required,
  children,
}: FormFieldProps) {
  return (
    <div>
      <label className="mb-1 flex items-center gap-1 text-sm font-medium">
        {label}
        {required && <span className="ml-0.5 text-[var(--error)]">*</span>}
      </label>
      {description && <p className="mb-2 text-xs text-[var(--muted)]">{description}</p>}
      {children}
      {error && (
        <p className="mt-1 flex items-center gap-1 text-xs text-[var(--error)]">
          <AlertCircle size={12} />
          {error}
        </p>
      )}
      {showSuccess && !error && (
        <p className="mt-1 flex items-center gap-1 text-xs text-[var(--success)]">
          <CheckCircle2 size={12} />
          Looks good
        </p>
      )}
    </div>
  )
}

// Input wrapper with validation styling
interface ValidatedInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string | null
  touched?: boolean
}

export function ValidatedInput({
  error,
  touched,
  className = '',
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  required: _required,
  ...props
}: ValidatedInputProps) {
  const borderClass =
    touched && error
      ? 'border-[var(--error)] focus:border-[var(--error)]'
      : touched && !error
        ? 'border-[var(--success)] focus:border-[var(--success)]'
        : 'border-[var(--border)] focus:border-[var(--accent)]'

  return (
    <input
      {...props}
      className={`w-full rounded-md border bg-[var(--background)] px-3 py-2 focus:outline-none ${borderClass} ${className}`}
    />
  )
}

// Textarea wrapper with validation styling
interface ValidatedTextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string | null
  touched?: boolean
}

export function ValidatedTextarea({
  error,
  touched,
  className = '',
  ...props
}: ValidatedTextareaProps) {
  const borderClass =
    touched && error
      ? 'border-[var(--error)] focus:border-[var(--error)]'
      : touched && !error
        ? 'border-[var(--success)] focus:border-[var(--success)]'
        : 'border-[var(--border)] focus:border-[var(--accent)]'

  return (
    <textarea
      {...props}
      className={`w-full rounded-md border bg-[var(--background)] px-3 py-2 focus:outline-none ${borderClass} ${className}`}
    />
  )
}
