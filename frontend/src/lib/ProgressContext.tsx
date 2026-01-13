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

interface ProgressContextValue {
  progress: ProgressMap
  subscribe: () => () => void
}

const ProgressContext = createContext<ProgressContextValue>({
  progress: {},
  subscribe: () => () => {},
})

export function useProgress(videoId: number): DownloadProgress | null {
  const { progress, subscribe } = useContext(ProgressContext)

  useEffect(() => {
    return subscribe()
  }, [subscribe])

  return progress[videoId] || null
}

export function useProgressMap(): ProgressMap {
  const { progress, subscribe } = useContext(ProgressContext)

  useEffect(() => {
    return subscribe()
  }, [subscribe])

  return progress
}

export function ProgressProvider({ children }: { children: ReactNode }) {
  const [progress, setProgress] = useState<ProgressMap>({})
  const sourceRef = useRef<EventSource | null>(null)
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const subscriberCount = useRef(0)

  const connect = useCallback(() => {
    if (sourceRef.current) return

    const source = new EventSource(getProgressStreamUrl())
    sourceRef.current = source

    source.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.status === 'timeout') {
          source.close()
          sourceRef.current = null
          if (subscriberCount.current > 0) {
            reconnectTimeout.current = setTimeout(connect, 1000)
          }
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
      if (subscriberCount.current > 0) {
        reconnectTimeout.current = setTimeout(connect, 2000)
      }
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
    setProgress({})
  }, [])

  const subscribe = useCallback(() => {
    subscriberCount.current++
    if (subscriberCount.current === 1) {
      connect()
    }

    return () => {
      subscriberCount.current--
      if (subscriberCount.current === 0) {
        disconnect()
      }
    }
  }, [connect, disconnect])

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return (
    <ProgressContext.Provider value={{ progress, subscribe }}>
      {children}
    </ProgressContext.Provider>
  )
}
