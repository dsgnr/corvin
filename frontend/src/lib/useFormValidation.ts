'use client'

import { useState, useCallback, useMemo } from 'react'

export interface FieldConfig<T> {
  initialValue: T
  validators?: Array<(value: T, allValues?: Record<string, unknown>) => string | null>
}

export interface FieldState<T> {
  value: T
  touched: boolean
  error: string | null
  dirty: boolean
}

export interface UseFormValidationReturn<T extends Record<string, unknown>> {
  values: T
  errors: Record<keyof T, string | null>
  touched: Record<keyof T, boolean>
  isValid: boolean
  isDirty: boolean
  setValue: <K extends keyof T>(field: K, value: T[K]) => void
  setTouched: (field: keyof T) => void
  setAllTouched: () => void
  validateField: (field: keyof T) => string | null
  validateAll: () => boolean
  reset: (newValues?: Partial<T>) => void
  getFieldProps: (field: keyof T) => {
    value: T[keyof T]
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
    ) => void
    onBlur: () => void
  }
  getFieldError: (field: keyof T) => string | null
  isFieldValid: (field: keyof T) => boolean
}

export function useFormValidation<T extends Record<string, unknown>>(config: {
  [K in keyof T]: FieldConfig<T[K]>
}): UseFormValidationReturn<T> {
  // Initialise values from config (computed once on mount)
  const [initialValues] = useState<T>(() => {
    const values = {} as T
    for (const key in config) {
      values[key] = config[key].initialValue
    }
    return values
  })

  const [values, setValues] = useState<T>(initialValues)
  const [touched, setTouchedState] = useState<Record<keyof T, boolean>>(() => {
    const t = {} as Record<keyof T, boolean>
    for (const key in config) {
      t[key] = false
    }
    return t
  })
  const [errors, setErrors] = useState<Record<keyof T, string | null>>(() => {
    const e = {} as Record<keyof T, string | null>
    for (const key in config) {
      e[key] = null
    }
    return e
  })

  // Validate a single field
  const validateField = useCallback(
    (field: keyof T): string | null => {
      const fieldConfig = config[field]
      if (!fieldConfig.validators) return null

      for (const validator of fieldConfig.validators) {
        const error = validator(values[field], values as Record<string, unknown>)
        if (error) {
          setErrors((prev) => ({ ...prev, [field]: error }))
          return error
        }
      }
      setErrors((prev) => ({ ...prev, [field]: null }))
      return null
    },
    [config, values]
  )

  // Set a field value and validate
  const setValue = useCallback(
    <K extends keyof T>(field: K, value: T[K]) => {
      setValues((prev) => ({ ...prev, [field]: value }))

      // Validate on change if field has been touched
      if (touched[field]) {
        const fieldConfig = config[field]
        if (fieldConfig.validators) {
          let error: string | null = null
          for (const validator of fieldConfig.validators) {
            const result = validator(value, { ...values, [field]: value } as Record<
              string,
              unknown
            >)
            if (result) {
              error = result
              break
            }
          }
          setErrors((prev) => ({ ...prev, [field]: error }))
        }
      }
    },
    [config, touched, values]
  )

  // Mark a field as touched and validate
  const setTouched = useCallback(
    (field: keyof T) => {
      setTouchedState((prev) => ({ ...prev, [field]: true }))
      validateField(field)
    },
    [validateField]
  )

  // Mark all fields as touched
  const setAllTouched = useCallback(() => {
    const allTouched = {} as Record<keyof T, boolean>
    for (const key in config) {
      allTouched[key] = true
    }
    setTouchedState(allTouched)
  }, [config])

  // Validate all fields
  const validateAll = useCallback((): boolean => {
    setAllTouched()
    let isValid = true
    const newErrors = {} as Record<keyof T, string | null>

    for (const field in config) {
      const fieldConfig = config[field]
      newErrors[field] = null

      if (fieldConfig.validators) {
        for (const validator of fieldConfig.validators) {
          const error = validator(values[field], values as Record<string, unknown>)
          if (error) {
            newErrors[field] = error
            isValid = false
            break
          }
        }
      }
    }

    setErrors(newErrors)
    return isValid
  }, [config, values, setAllTouched])

  // Reset form
  const reset = useCallback(
    (newValues?: Partial<T>) => {
      const resetValues = { ...initialValues, ...newValues } as T
      setValues(resetValues)

      const resetTouched = {} as Record<keyof T, boolean>
      const resetErrors = {} as Record<keyof T, string | null>
      for (const key in config) {
        resetTouched[key] = false
        resetErrors[key] = null
      }
      setTouchedState(resetTouched)
      setErrors(resetErrors)
    },
    [config, initialValues]
  )

  // Get props for a field (for easy binding)
  const getFieldProps = useCallback(
    (field: keyof T) => ({
      value: values[field],
      onChange: (
        e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
      ) => {
        const value =
          e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value
        setValue(field, value as T[keyof T])
      },
      onBlur: () => setTouched(field),
    }),
    [values, setValue, setTouched]
  )

  // Get error for a field (only if touched)
  const getFieldError = useCallback(
    (field: keyof T): string | null => {
      return touched[field] ? errors[field] : null
    },
    [touched, errors]
  )

  // Check if a field is valid
  const isFieldValid = useCallback(
    (field: keyof T): boolean => {
      return touched[field] && errors[field] === null
    },
    [touched, errors]
  )

  // Computed values
  const isValid = useMemo(() => {
    return Object.values(errors).every((error) => error === null)
  }, [errors])

  const isDirty = useMemo(() => {
    for (const key in config) {
      if (values[key] !== initialValues[key]) return true
    }
    return false
  }, [config, values, initialValues])

  return {
    values,
    errors,
    touched,
    isValid,
    isDirty,
    setValue,
    setTouched,
    setAllTouched,
    validateField,
    validateAll,
    reset,
    getFieldProps,
    getFieldError,
    isFieldValid,
  }
}
