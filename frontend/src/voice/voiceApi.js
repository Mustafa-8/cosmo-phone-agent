// Talks to the voice bridge (`uvicorn voice.server:app --port 8001`).
// API keys stay in the Python server; never put them in frontend code.

const VOICE_URL = import.meta.env.VITE_VOICE_URL ?? 'http://localhost:8001'

/**
 * Open a live speech-to-text stream. Send 16 kHz PCM16 chunks (ArrayBuffer) from startMic().
 * Callbacks: onPartial(text) for the live preview, onCommitted(text) for a finished sentence,
 * onError(message). Only committed text should ever be sent to the agent.
 */
export function openStt(language, { onPartial, onCommitted, onError, onOpen }) {
  const ws = new WebSocket(`${VOICE_URL.replace(/^http/, 'ws')}/ws/stt?language=${language}`)
  ws.binaryType = 'arraybuffer'
  ws.onopen = () => onOpen?.()
  ws.onmessage = (event) => {
    let msg
    try { msg = JSON.parse(event.data) } catch { return }
    if (msg.type === 'partial') onPartial?.(msg.text)
    else if (msg.type === 'committed') onCommitted?.(msg.text)
    else if (msg.type === 'error') onError?.(msg.text)
  }
  ws.onerror = () => onError?.('Cannot reach the voice server. Is it running on port 8001?')
  return {
    send(chunk) { if (ws.readyState === WebSocket.OPEN) ws.send(chunk) },
    commit() { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'commit' })) },
    close() { ws.close() },
  }
}

/** Speak text word for word. Returns a PlaybackQueue item: { blob } or { text, language } as fallback. */
export async function speakItem(text, language) {
  try {
    const res = await fetch(`${VOICE_URL}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language }),
    })
    if (res.status === 200) return { blob: await res.blob(), text, language }
  } catch {
    // fall through to browser speech
  }
  return { text, language }
}

/** Translation for display only. Returns the translated text, or null if unavailable. */
export async function translateText(text, source, target, speaker = 'receptionist') {
  try {
    const res = await fetch(`${VOICE_URL}/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source, target, speaker }),
    })
    if (!res.ok) return null
    const data = await res.json()
    return data.translated_text || null
  } catch {
    return null
  }
}
