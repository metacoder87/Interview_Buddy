import { useCallback, useState } from 'react'

export type AudioSource = 'microphone' | 'system'

interface UseAudioCaptureReturn {
  isCapturing: boolean
  error: string | null
  audioSource: AudioSource
  startCapture: (source?: AudioSource, sourceId?: string) => Promise<void>
  stopCapture: () => Promise<void>
  setAudioSource: (source: AudioSource) => void
}

/**
 * Core mode (Interview Buddy v2): audio capture lives in buddy-core — WASAPI
 * loopback on the Python side hears exactly what plays to speakers (the
 * interviewer), never the mic. The renderer no longer runs Web Audio
 * getDisplayMedia/getUserMedia; it only tells main to start/stop, which is
 * forwarded over WebSocket to the core.
 */
export function useAudioCapture(): UseAudioCaptureReturn {
  const [isCapturing, setIsCapturing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [audioSource, setAudioSource] = useState<AudioSource>('system')

  const startCapture = useCallback(async (_source: AudioSource = 'system', _sourceId?: string): Promise<void> => {
    try {
      setError(null)
      await window.api.startCapture()
      setIsCapturing(true)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start capture'
      setError(message)
      console.error('Audio capture error:', err)

      try {
        await window.api.stopCapture()
      } catch {
        // Ignore stop errors
      }
    }
  }, [])

  const stopCapture = useCallback(async (): Promise<void> => {
    try {
      await window.api.stopCapture()
      setIsCapturing(false)
      setError(null)
    } catch (err) {
      console.error('Stop capture error:', err)
    }
  }, [])

  return { isCapturing, error, audioSource, startCapture, stopCapture, setAudioSource }
}
