'use client'

import { createContext, useContext, useEffect, useState, useCallback, useRef, ReactNode } from 'react'
import { DownloadProgress, ProgressMap, getProgressStreamUrl } from './api'

const ProgressContext = createContext<ProgressMap>({})

export function useProgress(videoId: number): DownloadProgress | null {
  const progress = useContext(ProgressContext)
  return progress[videoId] || null
}

export function useProgressMap(): ProgressMap {
  return useContext(ProgressContext)
}

export function ProgressProvider({ children }: { children: ReactNode }) {
  const [progress, setProgress] = useState<ProgressMap>({})
  const sourceRef = useRef<EventSource | null>(null)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (sourceRef.current) return

    const source = new EventSource(getProgressStreamUrl())
    sourceRef.current = source

    source.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.status === 'timeout') {
          // Server timed out, reconnect
          source.close()
          sourceRef.current = null
          reconnectTimeout.current = setTimeout(connect, 1000)
        } else {
          setProgress(data as ProgressMap)
        }
      } catch {
        // ignore
      }
    }

    source.onerror = () => {
      source.close()
      sourceRef.current = null
      // Reconnect after a delay
      reconnectTimeout.current = setTimeout(connect, 2000)
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      sourceRef.current?.close()
      sourceRef.current = null
    }
  }, [connect])

  return <ProgressContext.Provider value={progress}>{children}</ProgressContext.Provider>
}
