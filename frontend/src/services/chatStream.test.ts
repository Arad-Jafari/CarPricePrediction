// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { consumeChatStream } from './chatStream'

function streamResponse(chunks: string[]) {
  const encoder = new TextEncoder()
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    }
  }), { headers: { 'Content-Type': 'text/event-stream' } })
}

describe('chat SSE consumer', () => {
  it('dispatches event data progressively across network chunk boundaries', async () => {
    const events: Array<{ event: string; data: Record<string, unknown> }> = []
    const response = streamResponse([
      'event: token\ndata: {"token":"Peu',
      'geot"}\n\nevent: done\ndata: {"message":{"content":"Peugeot"}}\n\n'
    ])

    await consumeChatStream(response, (event) => events.push(event))

    expect(events).toEqual([
      { event: 'token', data: { token: 'Peugeot' } },
      { event: 'done', data: { message: { content: 'Peugeot' } } }
    ])
  })

  it('surfaces provider error events to the caller', async () => {
    const response = streamResponse([
      'event: error\ndata: {"message":"Provider unavailable."}\n\n'
    ])

    await expect(consumeChatStream(response, () => undefined))
      .rejects.toThrow('Provider unavailable.')
  })
})
