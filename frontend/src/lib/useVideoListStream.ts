import { useEffect, useRef, useCallback } from 'react'
import { Video, ActiveTasks, getVideoListStreamUrl } from './api'

interface VideoListStreamData {
  type: 'full' | 'incremental'
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
  const videosRef = useRef<Map<number, Video>>(new Map())

  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  const connect = useCallback(() => {
    if (!enabled || !listId) return

    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    // Reset video cache on new connection
    videosRef.current = new Map()

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

        if (streamData.type === 'full' || videosRef.current.size === 0) {
          // Full update: replace entire cache
          videosRef.current = new Map(streamData.videos.map(v => [v.id, v]))
        } else {
          // Incremental update: merge changes into cache
          for (const video of streamData.videos) {
            videosRef.current.set(video.id, video)
          }
        }

        // Convert map to sorted array (by created_at desc)
        const sortedVideos = Array.from(videosRef.current.values()).sort((a, b) => {
          const dateA = a.created_at || ''
          const dateB = b.created_at || ''
          return dateB.localeCompare(dateA)
        })

        onUpdateRef.current(sortedVideos, streamData.tasks)
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
