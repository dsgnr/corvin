'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from 'react'
import { DownloadProgress, ProgressMap, getProgressStreamUrl } from './api'

/**
 * Check if the current tab is active (visible and focused).
 * SSE connections should only be active when the tab is in view.
 */
function isTabActive(): boolean {
  return !document.hidden && document.hasFocus()
}

interface ProgressContextValue {
  progress: ProgressMap
  subscribe: () => () => void
}

const ProgressContext = createContext<ProgressContextValue>({
  progress: {},
  subscribe: () => () => {},
})

/**
 * Hook to get download progress for a specific video.
 * Returns null if no progress data is available.
 */
export function useProgress(videoId: number): DownloadProgress | null {
  const { progress, subscribe } = useContext(ProgressContext)

  useEffect(() => {
    return subscribe()
  }, [subscribe])

  return progress[videoId] || null
}

/**
 * Hook to get the full progress map for all active downloads.
 * Useful when displaying multiple download progress indicators.
 */
export function useProgressMap(): ProgressMap {
  const { progress, subscribe } = useContext(ProgressContext)

  useEffect(() => {
    return subscribe()
  }, [subscribe])

  return progress
}

/**
 * Provider component that manages the SSE connection for download progress.
 * Wraps the application to provide progress data to all child components.
 * Automatically handles connection lifecycle based on subscriber count and tab activity.
 */
export function ProgressProvider({ children }: { children: ReactNode }) {
  const [progress, setProgress] = useState<ProgressMap>({})
  const sourceRef = useRef<EventSource | null>(null)
  const isClosingRef = useRef(false)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const subscriberCount = useRef(0)

  const connect = useCallback(() => {
    if (sourceRef.current) return
    if (!isTabActive()) return

    isClosingRef.current = false
    const source = new EventSource(getProgressStreamUrl())
    sourceRef.current = source

    source.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.status === 'timeout') {
          source.close()
          sourceRef.current = null
          // Will reconnect via activity change or subscribe
        } else {
          setProgress(data as ProgressMap)
        }
      } catch {
        // ignore
      }
    }

    source.onerror = () => {
      if (isClosingRef.current) return
      source.close()
      sourceRef.current = null
      // Will reconnect via activity change or subscribe
    }
  }, [])

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current)
      reconnectTimeout.current = null
    }
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [])

  const subscribe = useCallback(() => {
    subscriberCount.current++
    if (subscriberCount.current === 1 && isTabActive()) {
      connect()
    }

    return () => {
      subscriberCount.current--
      if (subscriberCount.current === 0) {
        disconnect()
        setProgress({})
      }
    }
  }, [connect, disconnect])

  useEffect(() => {
    const handleActivityChange = () => {
      if (isTabActive()) {
        if (subscriberCount.current > 0) {
          connect()
        }
      } else {
        disconnect()
      }
    }

    const handleBeforeUnload = () => {
      isClosingRef.current = true
      disconnect()
    }

    document.addEventListener('visibilitychange', handleActivityChange)
    window.addEventListener('focus', handleActivityChange)
    window.addEventListener('blur', handleActivityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)

    return () => {
      document.removeEventListener('visibilitychange', handleActivityChange)
      window.removeEventListener('focus', handleActivityChange)
      window.removeEventListener('blur', handleActivityChange)
      window.removeEventListener('beforeunload', handleBeforeUnload)
      isClosingRef.current = true
      disconnect()
    }
  }, [connect, disconnect])

  return (
    <ProgressContext.Provider value={{ progress, subscribe }}>{children}</ProgressContext.Provider>
  )
}
