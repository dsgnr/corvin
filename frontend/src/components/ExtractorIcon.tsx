'use client'

/**
 * Platform icons for video extractors.
 * Only added when they're tested for functionality.
 *
 * SVG paths and brand colors sourced from Simple Icons (https://simpleicons.org)
 */

import { clsx } from 'clsx'

interface ExtractorIconProps {
  extractor: string | null | undefined
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZES = {
  sm: 'w-4 h-4',
  md: 'w-5 h-5',
  lg: 'w-6 h-6',
}

/**
 * Renders the appropriate platform icon based on the extractor name.
 * Returns null if no matching extractor is found.
 */
export function ExtractorIcon({ extractor, size = 'md', className }: ExtractorIconProps) {
  if (!extractor) return null

  const name = extractor.toLowerCase()
  const sizeClass = SIZES[size]

  // YouTube
  if (name.includes('youtube')) {
    return (
      <svg
        viewBox="0 0 24 24"
        className={clsx(sizeClass, 'flex-shrink-0', className)}
        fill="#FF0000"
      >
        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
      </svg>
    )
  }

  // Twitch
  if (name.includes('twitch')) {
    return (
      <svg
        viewBox="0 0 24 24"
        className={clsx(sizeClass, 'flex-shrink-0', className)}
        fill="#9146FF"
      >
        <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z" />
      </svg>
    )
  }

  // Rumble
  if (name.includes('rumble')) {
    return (
      <svg
        viewBox="0 0 24 24"
        className={clsx(sizeClass, 'flex-shrink-0', className)}
        fill="#85C742"
      >
        <path d="M14.4528 13.5458c.8064-.6542.9297-1.8381.2756-2.6445a1.8802 1.8802 0 0 0-.2756-.2756 21.2127 21.2127 0 0 0-4.3121-2.776c-1.066-.51-2.256.2-2.4261 1.414a23.5226 23.5226 0 0 0-.14 5.5021c.116 1.23 1.292 1.964 2.372 1.492a19.6285 19.6285 0 0 0 4.5062-2.704v-.008zm6.9322-5.4002c2.0335 2.228 2.0396 5.637.014 7.8723A26.1487 26.1487 0 0 1 8.2946 23.846c-2.6848.6713-5.4168-.914-6.1662-3.5781-1.524-5.2002-1.3-11.0803.17-16.3045.772-2.744 3.3521-4.4661 6.0102-3.832 4.9242 1.174 9.5443 4.196 13.0764 8.0121v.002z" />
      </svg>
    )
  }

  // No matching extractor
  return null
}
