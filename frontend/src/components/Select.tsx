'use client'

import { SelectHTMLAttributes, forwardRef } from 'react'
import { clsx } from 'clsx'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  fullWidth?: boolean
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, fullWidth = true, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={clsx(
          "cursor-pointer appearance-none rounded-md border border-[var(--border)] bg-[var(--card)] bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%236b7280%22%20d%3D%22M3%204.5L6%208l3-3.5H3z%22%2F%3E%3C%2Fsvg%3E')] bg-[right_0.5rem_center] bg-no-repeat px-3 py-1.5 pr-8 text-sm text-[var(--foreground)] focus:border-[var(--accent)] focus:outline-none",
          fullWidth && 'w-full',
          className
        )}
        {...props}
      >
        {children}
      </select>
    )
  }
)

Select.displayName = 'Select'
