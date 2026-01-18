/**
 * Text utility functions for formatting and sanitisation.
 */

/**
 * Converts URLs in text to clickable anchor tags.
 * Escapes HTML entities first to prevent XSS attacks.
 */
export function linkifyText(text: string): string {
  // Escape HTML entities to prevent XSS
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

  // Convert URLs to clickable links
  const urlRegex = /(https?:\/\/[^\s<]+)/g
  return escaped.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
}
