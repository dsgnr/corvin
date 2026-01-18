/**
 * Utility functions and constants for the UI.
 */

/** Available page size options for paginated lists */
export const PAGE_SIZE_OPTIONS: number[] = [10, 20, 50, 100]

/** Default page size for paginated lists */
export const DEFAULT_PAGE_SIZE = PAGE_SIZE_OPTIONS[0]

/**
 * Formats a byte count into a human-readable file size string.
 * @param bytes - The number of bytes to format
 * @returns A formatted string like "1.5 MB" or "2.34 GB"
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

/**
 * Formats a duration in seconds into a human-readable time string.
 * @param seconds - The duration in seconds (can be null)
 * @returns A formatted string like "1:23:45" or "5:30", or "--:--" if null
 */
export function formatDuration(seconds: number | null): string {
  if (!seconds) return '--:--'
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
