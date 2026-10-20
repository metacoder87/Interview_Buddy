import { EventEmitter } from 'events'
import { coreLink } from './coreLink'

export interface OpenAIConfig {
  apiKey?: string
  model?: string
  maxTokens?: number
  temperature?: number
  resumeDescription?: string
}

/**
 * Interview Buddy v2 — answer generation lives in the local Python core:
 * RAG over the markdown brain (resume + project case studies + QA bank + JD)
 * grounded into a streaming Ollama call. This adapter preserves the legacy
 * event contract ('stream' chunks, 'complete') used by ipc/handlers.ts and the
 * renderer — no other file needs to change.
 */
export class OpenAIService extends EventEmitter {
  private hToken = (tok: string): void => this.emit('stream', tok)
  private hAnswerEnd = ({ full }: { full: string; latency_ms: number }): void => {
    console.log(`[openaiService] answer complete (${full.length} chars, core-side)`)
    this.emit('complete', full)
  }
  private hAnswerError = (err: string): void => {
    this.emit('error', new Error(err))
  }

  constructor(_config?: OpenAIConfig) {
    super()
  }

  async generateAnswer(question: string): Promise<void> {
    coreLink.connect();
    coreLink.on('token', this.hToken);
    coreLink.on('answer_end', this.hAnswerEnd);
    coreLink.on('answer_error', this.hAnswerError);
    console.log(`[openaiService] asking core: "${question.slice(0, 80)}..."`);
    coreLink.send({ t: 'ask', text: question });
  }

  clearHistory(): void {
    // context now lives in the core's RAG brain; nothing to clear client-side
  }

  dispose(): void {
    coreLink.off('token', this.hToken)
    coreLink.off('answer_end', this.hAnswerEnd)
    coreLink.off('answer_error', this.hAnswerError)
  }
}
