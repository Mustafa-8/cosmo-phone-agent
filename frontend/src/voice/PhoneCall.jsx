// Two-phone mode: open /?phone on two phones. One is the patient (English), one the receptionist (Hungarian).
// COSMO sits in the middle: each phone hears only what COSMO says to it.
import { useEffect, useRef, useState } from 'react'
import { startMic } from './audio'
import { openStt, speakItem } from './voiceApi'
import './phone.css'

const LANG = { patient: 'en', receptionist: 'hu' }
const TEXT = {
  patient: {
    title: 'Patient phone', you: 'You', other: 'Receptionist', agent: 'COSMO',
    talk: 'Tap to talk', stop: 'Tap when done', listening: 'Listening…', thinking: 'COSMO is thinking…',
    typePlaceholder: 'Or type your answer…', send: 'Send',
  },
  receptionist: {
    title: 'Recepció telefon', you: 'Ön', other: 'Páciens', agent: 'COSMO',
    talk: 'Koppintson és beszéljen', stop: 'Koppintson, ha végzett', listening: 'Hallgatom…', thinking: 'COSMO gondolkodik…',
    typePlaceholder: 'Vagy írja be a választ…', send: 'Küldés',
  },
}

function newRoomCode() {
  const abc = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  return Array.from({ length: 4 }, () => abc[Math.floor(Math.random() * abc.length)]).join('')
}

function wsUrl(path) {
  const url = new URL(path, window.location.href)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url
}

// Plays COSMO's MP3s through one unlocked AudioContext (works on iOS after the first tap).
class Speaker {
  constructor(ctx, onPlaying) {
    this.ctx = ctx
    this.chain = Promise.resolve()
    this.source = null
    this.onPlaying = onPlaying
    this.pending = 0
  }

  unlock() { return this.ctx.resume() }

  say(text, language) {
    const item = speakItem(text, language) // start fetching now, play in order
    this.pending += 1
    this.onPlaying(true)
    this.chain = this.chain.then(async () => {
      try {
        const { blob } = await item
        if (blob) await this._playBlob(blob)
        else await this._browserVoice(text, language)
      } catch {
        // skip this message, keep the queue going
      } finally {
        this.pending -= 1
        if (this.pending === 0) this.onPlaying(false)
      }
    })
  }

  async _playBlob(blob) {
    const buffer = await this.ctx.decodeAudioData(await blob.arrayBuffer())
    await new Promise((resolve) => {
      const src = this.ctx.createBufferSource()
      src.buffer = buffer
      src.connect(this.ctx.destination)
      src.onended = resolve
      this.source = src
      src.start()
    })
    this.source = null
  }

  _browserVoice(text, language) {
    return new Promise((resolve) => {
      if (!window.speechSynthesis) return resolve()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = language === 'hu' ? 'hu-HU' : 'en-US'
      u.onend = u.onerror = resolve
      window.speechSynthesis.speak(u)
    })
  }

  stop() {
    try { this.source?.stop() } catch { /* already stopped */ }
    window.speechSynthesis?.cancel()
  }

  close() { this.stop() }
}

function Lobby({ onJoin }) {
  const params = new URLSearchParams(window.location.search)
  const [room, setRoom] = useState(params.get('room') || '')
  const [role, setRole] = useState(params.get('role') || '')

  if (!role) {
    return (
      <div className="phone-lobby">
        <h1>COSMO · two-phone call</h1>
        <p>Use two phones: one is the patient, one is the Hungarian clinic reception.</p>
        <button className="phone-big" onClick={() => { setRole('patient'); if (!room) setRoom(newRoomCode()) }}>I am the patient (English)</button>
        <button className="phone-big phone-big--hu" onClick={() => setRole('receptionist')}>Recepció vagyok (magyar)</button>
      </div>
    )
  }
  return (
    <div className="phone-lobby">
      <h1>{role === 'patient' ? 'Patient phone' : 'Recepció telefon'}</h1>
      <label className="phone-label" htmlFor="room-code">{role === 'patient' ? 'Room code' : 'Szobakód'}</label>
      <input id="room-code" className="phone-code" value={room} maxLength={8} autoCapitalize="characters"
        onChange={(e) => setRoom(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))} placeholder="ABCD" />
      <button className="phone-big" disabled={!room} onClick={() => onJoin(room, role)}>
        {role === 'patient' ? 'Join call' : 'Csatlakozás'}
      </button>
      <button className="phone-link" onClick={() => setRole('')}>← back</button>
    </div>
  )
}

function CallScreen({ room, role, audioCtx }) {
  const t = TEXT[role]
  const [messages, setMessages] = useState([])
  const [state, setState] = useState({ started: false, thinking: false, roles: {} })
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [micOn, setMicOn] = useState(false)
  const [heard, setHeard] = useState('')
  const [typed, setTyped] = useState('')
  const [name, setName] = useState('')
  const [request, setRequest] = useState('I need a dentist appointment next week, in the afternoon.')
  const wsRef = useRef(null)
  const speakerRef = useRef(null)
  const micRef = useRef(null)
  const busyRef = useRef(false) // any phone is playing COSMO audio
  const localPlayingRef = useRef(false)
  const listRef = useRef(null)

  useEffect(() => {
    const speaker = new Speaker(audioCtx, (on) => {
      localPlayingRef.current = on
      busyRef.current = on
      if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'playing', on }))
    })
    speakerRef.current = speaker
    speaker.unlock()
    const ws = new WebSocket(wsUrl(`/call/ws?room=${room}&role=${role}`))
    wsRef.current = ws
    let replaying = true
    ws.onopen = () => { setConnected(true); setTimeout(() => { replaying = false }, 500) }
    ws.onclose = () => setConnected(false)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'message') {
        setMessages((cur) => [...cur.filter((m) => m.id !== msg.id), msg])
        if (!replaying && msg.speaker === 'agent' && msg.to === role) speaker.say(msg.text, msg.language)
      } else if (msg.type === 'translation') {
        setMessages((cur) => cur.map((m) => (m.id === msg.id ? { ...m, translation: msg.text } : m)))
      } else if (msg.type === 'state') {
        setState(msg)
      } else if (msg.type === 'playing') {
        busyRef.current = msg.on || localPlayingRef.current
      } else if (msg.type === 'reset') {
        setMessages([])
      } else if (msg.type === 'error') {
        setError(msg.message)
      }
    }
    return () => {
      ws.close()
      speaker.close()
      micRef.current?.stopMic()
      micRef.current?.stt.close()
    }
  }, [room, role, audioCtx])

  useEffect(() => { listRef.current?.scrollTo(0, listRef.current.scrollHeight) }, [messages, state.thinking])

  function send(msg) {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(msg))
  }

  async function toggleMic() {
    if (micRef.current) {
      const current = micRef.current
      micRef.current = null
      setMicOn(false)
      setHeard('')
      current.stopMic()
      current.stt.commit()
      setTimeout(() => current.stt.close(), 2000)
      return
    }
    setError('')
    speakerRef.current.unlock()
    const stt = openStt(LANG[role], {
      onPartial: (text) => setHeard(text),
      onCommitted: (text) => { setHeard(''); send({ type: 'say', text }) },
      onError: (message) => setError(message),
    })
    try {
      const stopMic = await startMic((chunk) => {
        if (!busyRef.current) stt.send(chunk) // never transcribe COSMO's voice from either phone
      })
      micRef.current = { stt, stopMic }
      setMicOn(true)
    } catch (e) {
      stt.close()
      setError(`Microphone not available: ${e.message}`)
    }
  }

  function startCall(e) {
    e.preventDefault()
    speakerRef.current.unlock()
    setError('')
    send({ type: 'start', name: name.trim(), request: request.trim() })
  }

  function sendTyped(e) {
    e.preventDefault()
    if (!typed.trim()) return
    send({ type: 'say', text: typed.trim() })
    setTyped('')
  }

  const visible = role === 'patient'
    ? messages
    : messages.filter((m) => m.speaker === 'receptionist' || (m.speaker === 'agent' && m.to === 'receptionist'))
  const otherRole = role === 'patient' ? 'receptionist' : 'patient'
  const otherHere = (state.roles?.[otherRole] ?? 0) > 0
  const shareLink = `${window.location.origin}/?phone&role=receptionist&room=${room}`

  return (
    <div className={`phone-call phone-call--${role}`}>
      <header className="phone-header">
        <div><strong>{t.title}</strong><span>Room {room}</span></div>
        <span className={`phone-dot ${connected ? 'phone-dot--on' : ''}`}>{connected ? (otherHere ? '● both phones' : '● waiting for other phone') : '○ offline'}</span>
      </header>

      {role === 'patient' && !state.started && messages.length === 0 && (
        <form className="phone-start" onSubmit={startCall}>
          <p className="phone-share">Receptionist phone: open <b>{shareLink}</b> or enter code <b>{room}</b></p>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name (fictional)" required />
          <textarea rows="3" value={request} onChange={(e) => setRequest(e.target.value)} required />
          <button className="phone-big" type="submit" disabled={!connected || !name.trim() || !request.trim()}>Start the call</button>
        </form>
      )}

      <div className="phone-messages" ref={listRef} aria-live="polite">
        {visible.map((m) => {
          const who = m.speaker === role ? t.you : m.speaker === 'agent' ? t.agent : t.other
          const showTranslation = role === 'patient' && m.language === 'hu'
          return (
            <article key={m.id} className={`phone-msg phone-msg--${m.speaker === role ? 'me' : m.speaker}`}>
              <small>{who}{m.speaker === 'agent' && role === 'patient' ? (m.to === 'patient' ? ' → you' : ' → reception') : ''}</small>
              {showTranslation
                ? <><p>{m.translation || '…'}</p><p className="phone-orig" lang="hu">{m.text}</p></>
                : <p lang={m.language}>{m.text}</p>}
            </article>
          )
        })}
        {state.thinking && <p className="phone-thinking">{t.thinking}</p>}
      </div>

      {error && <p className="phone-error" role="alert">⚠ {error}</p>}

      <footer className="phone-controls">
        {micOn && <p className="phone-heard" lang={LANG[role]}>{heard || t.listening}</p>}
        <button className={`phone-mic ${micOn ? 'phone-mic--on' : ''}`} onClick={toggleMic} disabled={!connected}>
          {micOn ? t.stop : t.talk}
        </button>
        <form className="phone-type" onSubmit={sendTyped}>
          <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={t.typePlaceholder} lang={LANG[role]} />
          <button type="submit" disabled={!typed.trim()}>{t.send}</button>
        </form>
      </footer>
    </div>
  )
}

export default function PhoneCall() {
  const [joined, setJoined] = useState(null)
  // Create and unlock audio inside the Join tap: phones only allow playback that starts from a tap,
  // and the receptionist may hear COSMO before touching anything else.
  function join(room, role) {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    audioCtx.resume()
    setJoined({ room, role, audioCtx })
  }
  if (!joined) return <Lobby onJoin={join} />
  return <CallScreen room={joined.room} role={joined.role} audioCtx={joined.audioCtx} />
}
