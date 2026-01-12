import { useEffect, useRef, useCallback } from 'react'
import { Video, ActiveTasks, getVideoListStreamUrl } from './api'

interface VideoListStreamData {
  videos: Video[]
  tasks: ActiveTasks
}

export function useVideoListStream(
  listId: number,
  enabled: boolean,
  onUpdate: (videos: Video[], tasks: ActiveTasks) => void
) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const onUpdateRef = useRef(onUpdate)

  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  const connect = useCallback(() => {
    if (!enabled || !listId) return

    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const url = getVideoListStreamUrl(listId)
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if ('status' in data && data.status === 'timeout') {
          eventSource.close()
          setTimeout(connect, 1000)
          return
        }
        const streamData = data as VideoListStreamData
        onUpdateRef.current(streamData.videos, streamData.tasks)
      } catch (err) {
        console.error('Failed to parse SSE data:', err)
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
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
