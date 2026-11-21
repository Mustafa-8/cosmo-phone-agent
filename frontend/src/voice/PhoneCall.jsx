// Two-phone call: open /?phone on two phones. One is the patient (English), one the clinic reception (Hungarian).
// It works like a real phone call: one tap to call/answer, then the mic stays open hands-free and
// Scribe detects the end of each sentence. COSMO sits in the middle and each phone hears only what
// COSMO says to it, in its own language.
import { useEffect, useRef, useState } from 'react'
import { startMic } from './audio'
import { openStt, speakItem } from './voiceApi'
import './phone.css'

const LANG = { patient: 'en', receptionist: 'hu' }
const TEXT = {
  patient: {
    title: 'Patient phone', callee: 'COSMO', calleeSub: 'AI booking assistant',
    action: 'Call COSMO', hint: 'Tap to call, then just talk: say your name and the appointment you need.',
    example: '“Hi, I\'m Alex Smith. I need a dentist appointment next week in the afternoon.”',
    listening: 'Listening…', youSpeak: 'You', thinking: 'COSMO is thinking…', speaking: 'COSMO is speaking…',
    waitOther: 'Waiting for the clinic phone to join…', mute: 'Mute', unmute: 'Unmute', hangup: 'Hang up',
    transcript: 'Transcript', ended: 'Call ended', again: 'Call again', newCall: 'New call',
  },
  receptionist: {
    title: 'Recepció', callee: 'COSMO', calleeSub: 'MI asszisztens · bejövő hívás',
    action: 'Hívás fogadása', hint: 'COSMO egy diák nevében kér időpontot. Önnek nem kell beszélnie: csak erősítse meg vagy utasítsa el.',
    example: 'Ha emberi segítség kell, a „Beszélni szeretnék” gombbal bekapcsolódhat a hívásba.',
    listening: 'Hallgatom…', youSpeak: 'Ön', thinking: 'COSMO gondolkodik…', speaking: 'COSMO beszél…',
    waitOther: 'Várakozás a páciensre…', mute: 'Némítás', unmute: 'Hang be', hangup: 'Letenni',
    transcript: 'Átirat', ended: 'A hívás véget ért', again: 'Újra fogadás', newCall: 'Új hívás',
    confirm: '✓ Megerősítem', deny: '✕ Nem szabad', joinLine: '🎤 Beszélni szeretnék', leaveLine: 'Mikrofon ki',
    decide: 'Erősítse meg vagy utasítsa el az időpontot:', waiting: 'Várjuk COSMO kérését…', withPatient: 'COSMO a pácienssel beszél, mindjárt kapcsolja Önt…', onLine: 'Ön a vonalban van — beszéljen',
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

// The online demo is protected by an access code (demo_access.py): POST it once, the browser gets a
// cookie that unlocks the agent, the voice bridge and the call WebSocket.
async function demoLogin(code) {
  const res = await fetch('/demo-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
    credentials: 'same-origin',
  })
  if (res.status === 404 || res.status === 405) return true // server without access control
  return res.ok
}

function codeFromHash() {
  return new URLSearchParams(window.location.hash.slice(1)).get('code') || ''
}

function mmss(secs) {
  return `${String(Math.floor(secs / 60)).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`
}

// Plays COSMO's MP3s in order through one AudioContext that was unlocked by a tap (works on iPhones).
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
    const item = speakItem(text, language) // fetch now, play in order
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
}

function Lobby({ onJoin }) {
  const params = new URLSearchParams(window.location.search)
  const [room, setRoom] = useState(params.get('room') || '')
  const [role, setRole] = useState(params.get('role') || '')
  const [code, setCode] = useState(codeFromHash())
  const [busy, setBusy] = useState(false)
  const [loginError, setLoginError] = useState('')

  async function continueToCall() {
    setBusy(true)
    setLoginError('')
    const ok = await onJoin(room, role, code.trim())
    if (!ok) {
      setLoginError(role === 'patient' ? 'Wrong access code.' : 'Hibás hozzáférési kód.')
      setBusy(false)
    }
  }

  if (!role) {
    return (
      <div className="phone-lobby">
        <h1>COSMO · phone call</h1>
        <p>Two phones: one is the patient, one is the Hungarian clinic reception.</p>
        <button className="phone-big" onClick={() => { setRole('patient'); if (!room) setRoom(newRoomCode()) }}>I am the patient (English)</button>
        <button className="phone-big phone-big--hu" onClick={() => setRole('receptionist')}>Recepció vagyok (magyar)</button>
      </div>
    )
  }
  return (
    <div className="phone-lobby">
      <h1>{role === 'patient' ? 'Patient phone' : 'Recepció'}</h1>
      <label className="phone-label" htmlFor="room-code">{role === 'patient' ? 'Room code' : 'Szobakód'}</label>
      <input id="room-code" className="phone-code" value={room} maxLength={8} autoCapitalize="characters"
        onChange={(e) => setRoom(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))} placeholder="ABCD" />
      <label className="phone-label" htmlFor="access-code">{role === 'patient' ? 'Access code' : 'Hozzáférési kód'}</label>
      <input id="access-code" className="phone-input" value={code} autoComplete="off" autoCapitalize="none"
        onChange={(e) => setCode(e.target.value)} placeholder={role === 'patient' ? 'From the person running the demo' : 'A demó kódja'} />
      {loginError && <p className="phone-error" role="alert">⚠ {loginError}</p>}
      <button className="phone-big" disabled={!room || busy} onClick={continueToCall}>
        {role === 'patient' ? 'Continue' : 'Tovább'}
      </button>
      <button className="phone-link" onClick={() => setRole('')}>← back</button>
    </div>
  )
}

function CallScreen({ room, role, audioCtx, code }) {
  const t = TEXT[role]
  const [messages, setMessages] = useState([])
  const [state, setState] = useState({ started: false, thinking: false, roles: {} })
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [phase, setPhase] = useState('idle') // idle | live | ended
  const [muted, setMuted] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [heard, setHeard] = useState('')
  const [seconds, setSeconds] = useState(0)
  const [showTranscript, setShowTranscript] = useState(false)
  const [micOn, setMicOn] = useState(false)
  const wsRef = useRef(null)
  const speakerRef = useRef(null)
  const micRef = useRef(null)
  const busyRef = useRef(false) // any phone is playing COSMO: pause mics so nobody transcribes COSMO
  const remoteBusyRef = useRef(false)
  const mutedRef = useRef(false)
  const phaseRef = useRef('idle')
  const spokenRef = useRef(0) // id of the last COSMO message this phone has played
  mutedRef.current = muted
  phaseRef.current = phase

  useEffect(() => {
    const speaker = new Speaker(audioCtx, (on) => {
      setSpeaking(on)
      busyRef.current = on || remoteBusyRef.current
      if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'playing', on }))
    })
    speakerRef.current = speaker
    const ws = new WebSocket(wsUrl(`/call/ws?room=${room}&role=${role}`))
    wsRef.current = ws
    let replaying = true
    ws.onopen = () => { setConnected(true); setTimeout(() => { replaying = false }, 500) }
    ws.onclose = () => setConnected(false)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'message') {
        setMessages((cur) => [...cur.filter((m) => m.id !== msg.id), msg])
        if (!replaying && phaseRef.current === 'live' && msg.speaker === 'agent' && msg.to === role) {
          spokenRef.current = msg.id
          speaker.say(msg.text, msg.language)
        }
      } else if (msg.type === 'translation') {
        setMessages((cur) => cur.map((m) => (m.id === msg.id ? { ...m, translation: msg.text } : m)))
      } else if (msg.type === 'state') {
        setState(msg)
      } else if (msg.type === 'playing') {
        remoteBusyRef.current = msg.on
        busyRef.current = msg.on || speaker.pending > 0
      } else if (msg.type === 'reset') {
        setMessages([])
      } else if (msg.type === 'error') {
        setError(msg.message)
      }
    }
    return () => {
      ws.close()
      speaker.stop()
      micRef.current?.stopMic()
      micRef.current?.stt.close()
    }
  }, [room, role, audioCtx])

  useEffect(() => {
    if (phase !== 'live') return undefined
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [phase])

  function send(msg) {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(msg))
  }

  // Open the mic for hands-free talking (end of each sentence detected by Scribe VAD).
  async function openMic() {
    const stt = openStt(LANG[role], {
      onPartial: (text) => setHeard(text),
      onCommitted: (text) => { setHeard(''); send({ type: 'say', text }) },
      onError: (message) => setError(message),
    })
    try {
      const stopMic = await startMic((chunk) => {
        if (!busyRef.current && !mutedRef.current) stt.send(chunk)
      })
      micRef.current = { stt, stopMic }
      setMicOn(true)
    } catch (e) {
      stt.close()
      setError(`Microphone not available: ${e.message}`)
    }
  }

  function closeMic() {
    const current = micRef.current
    micRef.current = null
    setMicOn(false)
    setHeard('')
    if (current) {
      current.stopMic()
      current.stt.close()
    }
  }

  // One tap: unlock audio (phones require a tap), start the call. The patient talks hands-free;
  // the reception only listens and confirms or denies, and opens the mic only to join the line.
  async function startCall() {
    setError('')
    await speakerRef.current.unlock()
    if (role === 'patient') await openMic()
    setSeconds(0)
    setPhase('live')
    {
      // Answering a ringing call: play what COSMO already said to this phone.
      for (const m of messages) {
        if (m.speaker === 'agent' && m.to === role && m.id > spokenRef.current) {
          spokenRef.current = m.id
          speakerRef.current.say(m.text, m.language)
        }
      }
    }
  }

  function hangUp() {
    closeMic()
    speakerRef.current.stop()
    setPhase('ended')
  }

  function decide(value) {
    speakerRef.current.stop()
    send({ type: 'decision', value })
  }

  function newCall() {
    send({ type: 'reset' })
    setPhase('idle')
  }

  const otherRole = role === 'patient' ? 'receptionist' : 'patient'
  const otherHere = (state.roles?.[otherRole] ?? 0) > 0
  // The code rides in the #fragment, which browsers never send to the server or the tunnel.
  const shareLink = `${window.location.origin}/?phone&role=receptionist&room=${room}#code=${encodeURIComponent(code)}`
  const toMe = messages.filter((m) => m.speaker === 'agent' && m.to === role)
  const lastToMe = toMe[toMe.length - 1]
  const mine = messages.filter((m) => m.speaker === role)
  const lastMine = mine[mine.length - 1]
  const patientActive = messages.some((m) => m.speaker === 'patient') || state.thinking
  const lastHuman = messages.filter((m) => m.speaker === 'receptionist').pop()
  const awaitingDecision = role === 'receptionist' && phase === 'live' && !state.thinking && lastToMe
    && !/viszontlát/i.test(lastToMe.text) && (!lastHuman || lastHuman.id < lastToMe.id) // every COSMO request except the goodbye
  const ringing = phase === 'idle' && toMe.some((m) => m.id > spokenRef.current)
  const status = speaking ? t.speaking
    : state.thinking ? t.thinking
      : heard ? `${t.youSpeak}: ${heard}`
        : muted ? t.unmute
          : role === 'receptionist' ? (micOn ? t.onLine : awaitingDecision ? t.decide : patientActive && !lastToMe ? t.withPatient : t.waiting)
            : t.listening

  return (
    <div className={`phone-call phone-call--${role}`}>
      <header className="phone-header">
        <div><strong>{t.title}</strong><span>Room {room}</span></div>
        <span className={`phone-dot ${connected && otherHere ? 'phone-dot--on' : ''}`}>
          {connected ? (otherHere ? '● 2/2' : '● 1/2') : '○ offline'}
        </span>
      </header>

      <section className="call-stage">
        <div className={`call-avatar ${speaking ? 'call-avatar--speaking' : ''} ${state.thinking ? 'call-avatar--thinking' : ''} ${ringing ? 'call-avatar--ringing' : ''}`}>
          <span>C</span>
        </div>
        <h2>{t.callee}</h2>
        <p className="call-sub">{phase === 'live' ? mmss(seconds) : ringing ? (role === 'patient' ? 'Incoming call…' : 'Bejövő hívás…') : t.calleeSub}</p>

        {phase === 'idle' && (
          <div className="call-intro">
            {role === 'patient' && !otherHere && (
              <p className="phone-share">Clinic phone: open <b>{shareLink}</b> or code <b>{room}</b></p>
            )}
            {role === 'receptionist' && patientActive && !ringing && <p className="call-status">{t.withPatient}</p>}
            <p>{t.hint}</p>
            <p className="call-example">{t.example}</p>
          </div>
        )}

        {phase === 'live' && (
          <>
            <p className="call-status" aria-live="polite">{status}</p>
            {!otherHere && <p className="call-wait">{t.waitOther}</p>}
            {lastToMe && (
              <blockquote className="call-caption" lang={lastToMe.language}>{lastToMe.text}</blockquote>
            )}
            {lastMine && !heard && <p className="call-mine" lang={LANG[role]}>{t.youSpeak}: {lastMine.text}</p>}
          </>
        )}

        {phase === 'ended' && <p className="call-status">{t.ended} · {mmss(seconds)}</p>}
        {error && <p className="phone-error" role="alert">⚠ {error}</p>}
      </section>

      {showTranscript && (
        <div className="phone-messages" aria-label={t.transcript}>
          {messages.map((m) => (
            <article key={m.id} className={`phone-msg phone-msg--${m.speaker === role ? 'me' : m.speaker}`}>
              <small>{m.speaker === 'agent' ? `COSMO → ${m.to}` : m.speaker}</small>
              <p lang={m.language}>{m.text}</p>
              {m.translation && role === 'patient' && <p className="phone-orig">{m.translation}</p>}
            </article>
          ))}
        </div>
      )}

      <footer className="call-controls">
        {phase === 'idle' && (
          <button className="call-btn call-btn--green" onClick={startCall} disabled={!connected}>
            <span aria-hidden="true">📞</span>{t.action}
          </button>
        )}
        {awaitingDecision && (
          <div className="call-decide">
            <button className="call-btn call-btn--green" onClick={() => decide('confirm')}>{t.confirm}</button>
            <button className="call-btn call-btn--red" onClick={() => decide('deny')}>{t.deny}</button>
          </div>
        )}
        {phase === 'live' && role === 'receptionist' && (
          <button className={`call-btn call-btn--round ${micOn ? 'call-btn--on' : ''}`} onClick={micOn ? closeMic : openMic}>
            {micOn ? t.leaveLine : t.joinLine}
          </button>
        )}
        {phase === 'live' && (
          <>
            {micOn && (
              <button className={`call-btn call-btn--round ${muted ? 'call-btn--on' : ''}`} onClick={() => setMuted(!muted)} aria-pressed={muted}>
                {muted ? t.unmute : t.mute}
              </button>
            )}
            <button className="call-btn call-btn--red" onClick={hangUp}>{t.hangup}</button>
          </>
        )}
        {phase === 'ended' && (
          <>
            <button className="call-btn call-btn--green" onClick={startCall}>{t.again}</button>
            {role === 'patient' && <button className="call-btn call-btn--round" onClick={newCall}>{t.newCall}</button>}
          </>
        )}
        <button className="phone-link" onClick={() => setShowTranscript(!showTranscript)}>
          {showTranscript ? '▾' : '▸'} {t.transcript}
        </button>
      </footer>
    </div>
  )
}

export default function PhoneCall() {
  const [joined, setJoined] = useState(null)
  // Create the audio context inside a tap: phones only allow playback that starts from a tap.
  async function join(room, role, code) {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)() // still inside the tap
    audioCtx.resume()
    if (!(await demoLogin(code))) {
      audioCtx.close()
      return false
    }
    setJoined({ room, role, audioCtx, code })
    return true
  }
  if (!joined) return <Lobby onJoin={join} />
  return <CallScreen room={joined.room} role={joined.role} audioCtx={joined.audioCtx} code={joined.code} />
}
