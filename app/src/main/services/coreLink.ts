import { EventEmitter } from 'events'

/**
 * CoreLink — singleton WebSocket client to the local Python core (buddy-core).
 *
 * The core owns audio capture (WASAPI loopback), STT (faster-whisper) and the
 * RAG + Ollama answer engine. It emits events that mirror the legacy
 * WhisperService/OpenAIService contract so ipc/handlers.ts keeps working:
 *
 *   transcript {text, isFinal}  — partials while speaking, final at endpoint
 *   utteranceEnd                — an utterance ended (final was emitted)
 *   speechStarted               — VAD saw speech begin
 *   questionDetected            — forwarded from the shell's detector? no:
 *                                 core does NOT gate; the shell detector does.
 *   answer_start / token / answer_end / answer_error — streamed answers
 *   status {msg}                — human-readable lifecycle messages
 */

export interface CoreTranscriptEvent {
  text: string
  isFinal: boolean
  confidence: number
}

const CORE_WS_URL = process.env.BUDDY_CORE_URL || 'ws://127.0.0.1:8790/ws'

class CoreLink extends EventEmitter {
  private ws: WebSocket | null = null
  private reconnectTimer: NodeJS.Timeout | null = null
  private pendingQueue: string[] = []   // messages buffered while not yet connected
  connected = false

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }
    try {
      const ws = new WebSocket(CORE_WS_URL)
      this.ws = ws
      ws.onopen = () => {
        console.log('[coreLink] WebSocket opened, readyState:', this.ws?.readyState)

        this.connected = true
        console.log('[coreLink] connected to buddy-core')
        this.emit('status', 'connected to local core')
        // Flush any messages that were queued while connecting
        const queued = this.pendingQueue.splice(0)
        for (const raw of queued) {
          ws.send(raw)
          console.log('[coreLink] flushed queued message:', JSON.parse(raw).t)
        }
      }
      ws.onmessage = (ev: MessageEvent) => {
        try {
          const m = JSON.parse(String(ev.data)) as Record<string, unknown> & { t: string }
          this.handle(m)
        } catch {
          // ignore malformed frames
        }
      }
      ws.onclose = () => {
        console.log('[coreLink] WebSocket closed, readyState:', this.ws?.readyState)

        this.connected = false
        if (this.reconnectTimer === null) {
          console.log('[coreLink] disconnected, retrying in 1.5s')
          this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null
            this.connect()
          }, 1500) as unknown as NodeJS.Timeout
        }
      }
      ws.onerror = (err) => {
        console.error('[coreLink] WebSocket error:', err)

        // onclose follows; reconnect handled there
      }
    } catch (e) {
      console.error('[coreLink] connect error', e)
      setTimeout(() => this.connect(), 2000)
    }
  }

  private handle(m: Record<string, unknown> & { t: string }): void {
    switch (m.t) {
      case 'partial':
        this.emit('transcript', { text: String(m.text ?? ''), isFinal: false, confidence: 1 })
        break
      case 'final':
        this.emit('transcript', { text: String(m.text ?? ''), isFinal: true, confidence: 1 })
        this.emit('utteranceEnd')
        break
      case 'speech_started':
        this.emit('speechStarted')
        break
      case 'answer_start':
        this.emit('answer_start', m)
        break
      case 'token':
        this.emit('token', String(m.text ?? ''))
        break
      case 'answer_end':
        this.emit('answer_end', { full: String(m.full ?? ''), latency_ms: Number(m.latency_ms ?? 0) })
        break
      case 'answer_error':
        this.emit('answer_error', String(m.error ?? 'unknown error'))
        break
      case 'status':
        console.log('[core]', m.msg)
        this.emit('status', String(m.msg))
        break
    }
  }

  send(msg: Record<string, unknown>): void {
    const raw = JSON.stringify(msg)
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(raw)
    } else {
      // Buffer the message; it will be flushed as soon as the socket opens
      console.warn('[coreLink] not connected; message queued after connect:', msg.t)
      this.pendingQueue.push(raw)
      this.connect()
    }
  }
}

export const coreLink = new CoreLink()
