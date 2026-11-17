export type ChatStreamEvent = {
  event: string
  data: Record<string, unknown>
}

export async function consumeChatStream(
  response: Response,
  onEvent: (event: ChatStreamEvent) => void
) {
  if (!response.body) throw new Error('The streaming response has no readable body.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  function dispatch(block: string) {
    let event = 'message'
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) return
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(data.join('\n')) as Record<string, unknown>
    } catch {
      throw new Error('The assistant sent an invalid streaming event.')
    }
    onEvent({ event, data: parsed })
    if (event === 'error') {
      throw new Error(typeof parsed.message === 'string' ? parsed.message : 'The assistant stream failed.')
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(/\r\n/g, '\n')
      let separator = buffer.indexOf('\n\n')
      while (separator >= 0) {
        dispatch(buffer.slice(0, separator))
        buffer = buffer.slice(separator + 2)
        separator = buffer.indexOf('\n\n')
      }
      if (done) break
    }
    if (buffer.trim()) dispatch(buffer)
  } finally {
    reader.releaseLock()
  }
}
