// Talks to the COSMO ADK agent (`adk api_server`). Mirrors phone_agent/contract.py.
// Only the agent URL is configured here; never put API keys in frontend code.

const AGENT_URL = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8000'
const APP_NAME = 'phone_agent'
const LANGUAGE_OF_LISTENER = { patient: 'en', receptionist: 'hu' }
const LANGUAGE_NAME = { en: 'English', hu: 'Hungarian' }

/** Thrown when the online demo server asks for its access code (HTTP 401). */
export class AccessCodeRequired extends Error {}

/**
 * Send the demo access code once (online demo only, see demo_access.py). The server answers
 * with an HttpOnly cookie that the browser then sends automatically. Returns true if accepted.
 */
export async function submitAccessCode(code) {
  const res = await fetch(`${AGENT_URL}/demo-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  return res.ok
}

/** Create one ADK session per call. Throws on failure; AccessCodeRequired if the code is needed. */
export async function createSession(userId, sessionId) {
  const res = await fetch(`${AGENT_URL}/apps/${APP_NAME}/users/${userId}/sessions/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  })
  if (res.status === 401) throw new AccessCodeRequired('Enter the demo access code to start a live call.')
  if (!res.ok) throw new Error(`Could not start the call (HTTP ${res.status}). Is adk api_server running?`)
}

/**
 * Send one finished utterance to the agent and return its spoken messages.
 * speaker: 'patient' | 'receptionist'. Returns a list in the contract format;
 * errors come back as { type: 'error', message } instead of throwing.
 */
export async function sendToAgent(userId, sessionId, speaker, text) {
  const lang = LANGUAGE_OF_LISTENER[speaker]
  let res
  try {
    res = await fetch(`${AGENT_URL}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        appName: APP_NAME,
        userId,
        sessionId,
        newMessage: { role: 'user', parts: [{ text: `[${speaker}|${lang}] ${text}` }] },
      }),
    })
  } catch {
    return [{ type: 'error', message: 'Cannot reach the agent. Is adk api_server running with --allow_origins?' }]
  }
  if (res.status === 401) {
    return [{ type: 'error', message: 'The demo access code is missing or expired. End the call and start again.' }]
  }
  if (!res.ok) {
    const hint = res.status === 500 ? ' (often the Gemini free-tier limit; wait a minute and try again)' : ''
    return [{ type: 'error', message: `Agent error: HTTP ${res.status}${hint}` }]
  }
  return toAgentMessages(await res.json())
}

/** Same rules as contract.run_response_to_events: only validated `say` results are spoken. */
export function toAgentMessages(events) {
  if (!Array.isArray(events)) return [{ type: 'error', message: 'Unexpected reply from the agent.' }]
  const out = []
  for (const ev of events) {
    if (ev.errorCode) {
      out.push({ type: 'error', message: `${ev.errorCode}: ${ev.errorMessage ?? ''}` })
      continue
    }
    for (const part of ev.content?.parts ?? []) {
      const r = part.functionResponse
      if (r?.name !== 'say' || r.response?.status !== 'ok') continue
      const spoken = LANGUAGE_OF_LISTENER[r.response.to]
      out.push({
        type: 'transcript',
        speaker: 'agent',
        to: r.response.to,
        language: LANGUAGE_NAME[spoken],
        original_text: r.response.text,
        translated_text: null, // filled by the voice layer's translation later
      })
    }
  }
  return out
}
