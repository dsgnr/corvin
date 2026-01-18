import { useEffect, useRef } from 'react'

/**
 * Check if the current tab is active (visible and focused).
 * SSE connections should only be active when the tab is in view.
 */
function isTabActive(): boolean {
  return !document.hidden && document.hasFocus()
}

/**
 * Hook for managing EventSource (SSE) connections with proper cleanup.
 * Automatically pauses connections when the browser tab is hidden or loses focus
 * to free up connection slots, and reconnects when the tab becomes active again.
 *
 * @param url - The SSE endpoint URL, or null to disable the connection
 * @param onMessage - Callback invoked when a message is received
 * @param onError - Optional callback invoked when an error occurs
 */
export function useEventSource<T>(
  url: string | null,
  onMessage: (data: T) => void,
  onError?: () => void
) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const isClosingRef = useRef(false)
  const onMessageRef = useRef(onMessage)
  const onErrorRef = useRef(onError)

  // Keep refs updated
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  useEffect(() => {
    if (!url) return

    isClosingRef.current = false

    const createConnection = () => {
      if (eventSourceRef.current) return
      if (!isTabActive()) return

      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as T
          onMessageRef.current(data)
        } catch {
          // ignore parse errors
        }
      }

      eventSource.onerror = () => {
        if (isClosingRef.current) return
        onErrorRef.current?.()
        eventSource.close()
        eventSourceRef.current = null
      }
    }

    const closeConnection = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }

    const handleActivityChange = () => {
      if (isTabActive()) {
        createConnection()
      } else {
        closeConnection()
      }
    }

    const handleBeforeUnload = () => {
      isClosingRef.current = true
      closeConnection()
    }

    // Listen for visibility and focus changes to pause/resume SSE
    document.addEventListener('visibilitychange', handleActivityChange)
    window.addEventListener('focus', handleActivityChange)
    window.addEventListener('blur', handleActivityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)

    // Initial connection if tab is active
    createConnection()

    return () => {
      document.removeEventListener('visibilitychange', handleActivityChange)
      window.removeEventListener('focus', handleActivityChange)
      window.removeEventListener('blur', handleActivityChange)
      window.removeEventListener('beforeunload', handleBeforeUnload)
      isClosingRef.current = true
      closeConnection()
    }
  }, [url])

  return eventSourceRef
}
