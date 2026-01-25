// Form validation utilities

export interface ValidationError {
  field: string
  message: string
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationError[]
}

// Validators
export const validators = {
  required: (value: string | number | null | undefined, fieldName: string): string | null => {
    if (value === null || value === undefined || value === '') {
      return `${fieldName} is required`
    }
    return null
  },

  minLength: (value: string, min: number, fieldName: string): string | null => {
    if (value.length < min) {
      return `${fieldName} must be at least ${min} characters`
    }
    return null
  },

  maxLength: (value: string, max: number, fieldName: string): string | null => {
    if (value.length > max) {
      return `${fieldName} must be at most ${max} characters`
    }
    return null
  },

  url: (value: string, fieldName: string): string | null => {
    if (!value) return null
    try {
      new URL(value)
      return null
    } catch {
      return `${fieldName} must be a valid URL`
    }
  },

  regex: (value: string): string | null => {
    if (!value) return null
    try {
      new RegExp(value, 'i')
      return null
    } catch {
      return 'Invalid regex pattern'
    }
  },

  time: (value: string, fieldName: string): string | null => {
    if (!value) return null
    const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/
    if (!timeRegex.test(value)) {
      return `${fieldName} must be in HH:MM format`
    }
    return null
  },

  timeRange: (startTime: string, endTime: string): string | null => {
    if (!startTime || !endTime) return null
    // Allow overnight schedules (e.g., 22:00 - 06:00)
    return null
  },

  languageCodes: (value: string): string | null => {
    if (!value) return null
    const codes = value.split(',').map((c) => c.trim())
    const invalidCodes = codes.filter((code) => !/^[a-z]{2,3}(-[A-Z]{2})?$/.test(code))
    if (invalidCodes.length > 0) {
      return `Invalid language code(s): ${invalidCodes.join(', ')}. Use ISO 639-1 codes (e.g., en, es, fr)`
    }
    return null
  },

  outputTemplate: (value: string): string | null => {
    if (!value) return null
    // Check for at least one valid yt-dlp variable
    const hasVariable = /%\([^)]+\)s/.test(value)
    if (!hasVariable) {
      return 'Template should include at least one variable like %(title)s or %(ext)s'
    }
    // Check for %(ext)s which is usually required
    if (!value.includes('%(ext)s')) {
      return 'Template should include %(ext)s for the file extension'
    }
    return null
  },

  nonEmptyArray: (value: unknown[], fieldName: string): string | null => {
    if (!value || value.length === 0) {
      return `At least one ${fieldName} must be selected`
    }
    return null
  },
}

// Field-level validation state
export interface FieldState {
  value: string
  touched: boolean
  error: string | null
}

// Create initial field state
export function createFieldState(initialValue: string = ''): FieldState {
  return {
    value: initialValue,
    touched: false,
    error: null,
  }
}

// Validate a single field
export function validateField(
  value: string,
  validatorFns: Array<(value: string) => string | null>
): string | null {
  for (const validate of validatorFns) {
    const error = validate(value)
    if (error) return error
  }
  return null
}

// Check if form has any errors
export function hasErrors(errors: Record<string, string | null>): boolean {
  return Object.values(errors).some((error) => error !== null)
}

// Get error class for input styling
export function getInputErrorClass(error: string | null, touched: boolean): string {
  if (!touched) return 'border-[var(--border)] focus:border-[var(--accent)]'
  if (error) return 'border-[var(--error)] focus:border-[var(--error)]'
  return 'border-[var(--success)] focus:border-[var(--success)]'
}
