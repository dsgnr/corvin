'use client'

import { useEffect, useState, useRef } from 'react'
import { DownloadProgress, createProgressStream } from './api'

interface Options {
  enabled?: boolean
  onComplete?: () => void
}

export function useDownloadProgress(videoId: number, options: Options = {}) {
  const { enabled = true, onComplete } = options
  const [progress, setProgress] = useState<DownloadProgress | null>(null)
  const sourceRef = useRef<EventSource | null>(null)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    if (!enabled || !videoId) {
      sourceRef.current?.close()
      sourceRef.current = null
      setProgress(null)
      return
    }

    sourceRef.current = createProgressStream(videoId, (data) => {
      setProgress(data)

      if (data.status === 'completed' || data.status === 'error' || data.status === 'timeout') {
        sourceRef.current?.close()
        sourceRef.current = null
        if (data.status === 'completed') onCompleteRef.current?.()
      }
    })

    return () => {
      sourceRef.current?.close()
      sourceRef.current = null
    }
  }, [videoId, enabled])

  return progress
}
