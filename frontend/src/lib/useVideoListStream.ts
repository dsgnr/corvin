import { useEffect, useRef, useCallback } from 'react'
import { Video, getVideoListStreamUrl } from './api'

type VideoListStreamData = Video[] | { status: 'timeout' }

export function useVideoListStream(
  listId: number,
  enabled: boolean,
  onUpdate: (videos: Video[]) => void
) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const onUpdateRef = useRef(onUpdate)

  // Keep callback ref updated
  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  const connect = useCallback(() => {
    if (!enabled || !listId) return

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const url = getVideoListStreamUrl(listId)
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data: VideoListStreamData = JSON.parse(event.data)
        if ('status' in data && data.status === 'timeout') {
          // Reconnect on timeout
          eventSource.close()
          setTimeout(connect, 1000)
          return
        }
        onUpdateRef.current(data as Video[])
      } catch (err) {
        console.error('Failed to parse SSE data:', err)
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      // Reconnect after a delay
      setTimeout(connect, 3000)
    }
  }, [listId, enabled])

  useEffect(() => {
    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [connect])
}
