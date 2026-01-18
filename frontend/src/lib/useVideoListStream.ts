import { useEffect, useRef } from 'react'
import {
  ActiveTasks,
  VideoListStats,
  VideoListStatsUpdate,
  getVideoListStreamUrl,
} from './api'

/**
 * Check if the current tab is active (visible and focused).
 * SSE connections should only be active when the tab is in view.
 */
function isTabActive(): boolean {
  return !document.hidden && document.hasFocus()
}

/**
 * Hook for subscribing to real-time video list updates via SSE.
 * Provides stats updates and notifications when videos change.
 * Automatically pauses when the browser tab is hidden or loses focus.
 *
 * @param listId - The ID of the video list to monitor
 * @param enabled - Whether the stream should be active
 * @param onUpdate - Callback invoked when stats or videos change
 */
export function useVideoListStream(
  listId: number,
  enabled: boolean,
  onUpdate: (stats: VideoListStats, tasks: ActiveTasks, changedVideoIds: number[]) => void
) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const isClosingRef = useRef(false)
  const onUpdateRef = useRef(onUpdate)
  const listIdRef = useRef(listId)
  const enabledRef = useRef(enabled)

  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  useEffect(() => {
    listIdRef.current = listId
  }, [listId])

  useEffect(() => {
    enabledRef.current = enabled
  }, [enabled])

  useEffect(() => {
    if (!enabled || !listId) return

    isClosingRef.current = false

    const closeConnection = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }

    const connect = () => {
      if (!enabledRef.current || !listIdRef.current) return
      if (!isTabActive()) return
      if (eventSourceRef.current) return

      const url = getVideoListStreamUrl(listIdRef.current)
      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if ('status' in data && data.status === 'timeout') {
            eventSource.close()
            eventSourceRef.current = null
            setTimeout(() => {
              if (isTabActive() && enabledRef.current && listIdRef.current) {
                connect()
              }
            }, 1000)
            return
          }
          const streamData = data as VideoListStatsUpdate

          onUpdateRef.current(
            streamData.stats,
            streamData.tasks,
            streamData.changed_video_ids || []
          )
        } catch (err) {
          console.error('Failed to parse SSE data:', err)
        }
      }

      eventSource.onerror = () => {
        if (isClosingRef.current) return
        eventSource.close()
        eventSourceRef.current = null
      }
    }

    const handleActivityChange = () => {
      if (isTabActive()) {
        connect()
      } else {
        closeConnection()
      }
    }

    const handleBeforeUnload = () => {
      isClosingRef.current = true
      closeConnection()
    }

    document.addEventListener('visibilitychange', handleActivityChange)
    window.addEventListener('focus', handleActivityChange)
    window.addEventListener('blur', handleActivityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)

    connect()

    return () => {
      document.removeEventListener('visibilitychange', handleActivityChange)
      window.removeEventListener('focus', handleActivityChange)
      window.removeEventListener('blur', handleActivityChange)
      window.removeEventListener('beforeunload', handleBeforeUnload)
      isClosingRef.current = true
      closeConnection()
    }
  }, [listId, enabled])
}
