import { EventEmitter } from 'events'
import { coreLink } from './coreLink'

export interface TranscriptEvent {
  text: string
  isFinal: boolean
  confidence: number
}

export interface WhisperConfig {
  apiKey?: string
  model?: string
  language?: string
}

/**
 * Interview Buddy v2 — audio capture + STT now live in the local Python core
 * (buddy-core): WASAPI loopback -> faster-whisper. This class is a thin adapter
 * that preserves the legacy event contract consumed by ipc/handlers.ts, so the
 * rest of the app (question detector, renderer) works unchanged.
 */
export class WhisperService extends EventEmitter {
  private hTranscript = (e: TranscriptEvent): void => this.emit('transcript', e)
  private hUtteranceEnd = (): void => this.emit('utteranceEnd')
  private hSpeechStarted = (): void => this.emit('speechStarted')

  constructor(_config?: WhisperConfig) {
    super()
  }

  start(): void {
    coreLink.connect()
    coreLink.on('transcript', this.hTranscript)
    coreLink.on('utteranceEnd', this.hUtteranceEnd)
    coreLink.on('speechStarted', this.hSpeechStarted)
    coreLink.send({ t: 'start' })
    console.log('WhisperService started (local core mode)')
    this.emit('started')
  }

  stop(): void {
    coreLink.send({ t: 'stop' })
    this.detach()
    console.log('WhisperService stopped')
    this.emit('stopped')
  }

  /** Renderer Web-Audio capture is no longer needed — the core captures the
   *  speaker output (WASAPI loopback) directly. Kept as a no-op for compat. */
  addAudioData(_audioData: Buffer | ArrayBuffer): void {
    // intentionally unused in local-core mode
  }

  private detach(): void {
    coreLink.off('transcript', this.hTranscript)
    coreLink.off('utteranceEnd', this.hUtteranceEnd)
    coreLink.off('speechStarted', this.hSpeechStarted)
  }
}
