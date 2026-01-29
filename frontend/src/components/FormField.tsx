'use client'

import { ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'

interface FormFieldProps {
  label: string
  description?: ReactNode
  error?: string | null
  required?: boolean
  children: ReactNode
}

export function FormField({ label, description, error, required, children }: FormFieldProps) {
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
    </div>
  )
}

// Input wrapper
export function ValidatedInput({
  className = '',
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  required: _required,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`input ${className}`} />
}

// Textarea wrapper
export function ValidatedTextarea({
  className = '',
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`input min-h-[80px] resize-y ${className}`} />
}
