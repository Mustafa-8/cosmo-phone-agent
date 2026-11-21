import { useState } from 'react'
import './App.css'

const languages = [
  { code: 'en', name: 'English' },
]

const simulatedReplies = [
  {
    speaker: 'receptionist',
    language: 'Hungarian',
    original_text: 'Jó napot! Melyik nap lenne megfelelő?',
    translated_text: 'Good afternoon! Which day would work for you?',
  },
  {
    speaker: 'agent',
    to: 'receptionist',
    language: 'Hungarian',
    original_text: 'A jövő hét kedd délután megfelelő lenne.',
    translated_text: 'Next Tuesday afternoon would work.',
  },
  {
    speaker: 'receptionist',
    language: 'Hungarian',
    original_text: 'Van szabad időpontunk kedden 15 órakor.',
    translated_text: 'We have an available appointment on Tuesday at 3:00 PM.',
  },
  {
    speaker: 'agent',
    to: 'patient',
    language: 'English',
    original_text: 'Your dentist appointment is confirmed for Tuesday at 3:00 PM at Budapest Dental Clinic.',
    translated_text: '',
  },
]

function Icon({ name, size = 20 }) {
  const paths = {
    activity: <path d="M3 12h4l3-8 4 16 3-8h4" />,
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 11h18" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    close: <path d="m18 6-12 12M6 6l12 12" />,
    headphones: <><path d="M3 14v-3a9 9 0 0 1 18 0v3" /><path d="M5 14h2v6H5a2 2 0 0 1-2-2v-2a2 2 0 0 1 2-2Zm14 0h-2v6h2a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2Z" /></>,
    language: <><path d="m5 8 6 6" /><path d="m4 14 6-6 2-3" /><path d="M2 5h12" /><path d="M7 2h1" /><path d="M22 22 17 12l-5 10" /><path d="M14 18h6" /></>,
    mic: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8" /></>,
    micOff: <><path d="m2 2 20 20" /><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-5.95-.54" /><path d="M5 10v2a7 7 0 0 0 12 4.9M19 10v2a7 7 0 0 1-.34 2.17M12 17v5m-4 0h8" /></>,
    phone: <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.2 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.96.36 1.9.7 2.8a2 2 0 0 1-.45 2.1L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.1-.45c.9.34 1.84.58 2.8.7A2 2 0 0 1 22 16.92Z" />,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    sparkles: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" /><path d="m19 14 1.2 2.8L23 18l-2.8 1.2L19 22l-1.2-2.8L15 18l2.8-1.2L19 14Z" /></>,
    volume: <><path d="M11 5 6 9H3v6h3l5 4V5Z" /><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

function LanguageSelect({ id, label, value, onChange }) {
  return (
    <label className="language-select" htmlFor={id}>
      <span>{label}</span>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {languages.map((language) => (
          <option value={language.code} key={language.code}>{language.name}</option>
        ))}
      </select>
    </label>
  )
}

function App() {
  const [fullName, setFullName] = useState('')
  const [request, setRequest] = useState('I need a dentist appointment next week, in the afternoon.')
  const [studentLanguage, setStudentLanguage] = useState('en')
  const [clinicLanguage, setClinicLanguage] = useState('hu')
  const [callState, setCallState] = useState('ready')
  const [isMuted, setIsMuted] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(true)
  const [replyIndex, setReplyIndex] = useState(-1)
  const [messages, setMessages] = useState([])

  const isCallActive = callState === 'active'

  function startDemoCall(event) {
    event.preventDefault()
    if (!fullName.trim() || !request.trim()) return

    setCallState('active')
    setReplyIndex(-1)
    setMessages([
      {
        id: 1,
        speaker: 'patient',
        full_name: fullName.trim(),
        language: 'English',
        original_text: request.trim(),
        translated_text: '',
      },
      {
        id: 2,
        speaker: 'agent',
        to: 'receptionist',
        language: 'Hungarian',
        original_text: 'Jó napot, a COSMO vagyok, egy AI-asszisztens. Egy diák nevében telefonálok időpontfoglalás miatt.',
        translated_text: 'Hello, I am COSMO, an AI assistant calling on behalf of a student to book an appointment.',
      },
      {
        id: 3,
        speaker: 'receptionist',
        language: 'Hungarian',
        original_text: 'Jó napot! Miben segíthetek?',
        translated_text: 'Good afternoon! How can I help you?',
      },
    ])
  }

  function addSimulatedReply() {
    const nextIndex = (replyIndex + 1) % simulatedReplies.length
    const reply = simulatedReplies[nextIndex]
    setMessages((current) => [...current, {
      ...reply,
      id: Date.now(),
      ...(reply.to === 'patient' ? { full_name: fullName.trim() } : {}),
    }])
    setReplyIndex(nextIndex)
  }

  function endCall() {
    setCallState('ended')
    setIsMuted(false)
  }

  function resetCall() {
    setCallState('ready')
    setMessages([])
    setReplyIndex(-1)
  }

  return (
    <div className="cosmo-app">
      <header className="topbar">
        <a className="brand" href="#home" aria-label="COSMO home">
          <span className="brand-mark"><Icon name="sparkles" size={20} /></span>
          <span><strong>COSMO</strong><small>PHONE AGENT</small></span>
        </a>
        <div className="topbar-note"><span className="prototype-dot" /> Hackathon demo</div>
      </header>

      <main className="page-content" id="home">
        <section className="welcome">
          <div className="welcome-copy">
            <div className="eyebrow"><Icon name="sparkles" size={14} /> YOUR HUNGARIAN APPOINTMENT ASSISTANT</div>
            <h1>Clinic calls, made easier.</h1>
            <p>Tell COSMO what you need. It will handle the Hungarian conversation and keep you updated in English.</p>
          </div>
          <div className="welcome-art" aria-hidden="true">
            <span className="art-orbit art-orbit--one" />
            <span className="art-orbit art-orbit--two" />
            <span className="art-sparkle"><Icon name="sparkles" size={28} /></span>
            <span className="art-caption">EN <Icon name="arrow" size={13} /> HU</span>
          </div>
        </section>

        <div className="prototype-banner" role="note">
          <Icon name="shield" size={17} />
          <span><strong>Prototype mode</strong> — this screen uses sample data. No real clinic call or appointment is made.</span>
        </div>

        <div className="workflow-grid">
          <section className="request-card" aria-labelledby="request-heading">
            <div className="section-heading">
              <span className="step-number">1</span>
              <div><h2 id="request-heading">Tell COSMO what you need</h2><p>Write naturally in your preferred language.</p></div>
            </div>

            <form onSubmit={startDemoCall}>
              <label className="field-label" htmlFor="full-name">Your full name</label>
              <input
                id="full-name"
                name="full_name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Enter your first and last name"
                required
                disabled={isCallActive}
              />
              <label className="field-label" htmlFor="appointment-request">Your appointment request</label>
              <textarea
                id="appointment-request"
                rows="4"
                value={request}
                onChange={(event) => setRequest(event.target.value)}
                placeholder="For example: I need a dentist next week in the afternoon."
                disabled={isCallActive}
              />
              <div className="request-hint"><Icon name="sparkles" size={14} /> Example request shown — edit it to try your own.</div>

              <div className="request-fields">
                <LanguageSelect id="student-language" label="I speak" value={studentLanguage} onChange={setStudentLanguage} />
                <label className="language-select" htmlFor="clinic-language">
                  <span>COSMO speaks to the clinic in</span>
                  <select id="clinic-language" value={clinicLanguage} onChange={(event) => setClinicLanguage(event.target.value)}>
                    <option value="hu">Hungarian</option>
                  </select>
                </label>
              </div>

              {!isCallActive && (
                <button className="primary-button" type="submit" disabled={!fullName.trim() || !request.trim()}>
                  <Icon name="phone" size={17} />
                  {callState === 'ended' ? 'Start another demo call' : 'Start demo call'}
                  <Icon name="arrow" size={16} />
                </button>
              )}
            </form>

            <div className="booking-note"><Icon name="calendar" size={16} /><span><strong>What happens next?</strong> COSMO will find a clinic, call in Hungarian, and show you the conversation.</span></div>
          </section>

          <section className="call-card" aria-labelledby="call-heading">
            <header className="call-header">
              <div className="section-heading">
                <span className="step-number step-number--two">2</span>
                <div><h2 id="call-heading">Booking call</h2><p>Hungarian receptionist · English updates</p></div>
              </div>
              <span className={`call-state call-state--${callState}`}>
                <span />
                {callState === 'active' ? 'DEMO CALL' : callState === 'ended' ? 'ENDED' : 'READY'}
              </span>
            </header>

            <div className={`call-visual ${isCallActive ? 'call-visual--active' : ''}`}>
              <div className="cosmo-avatar"><Icon name="sparkles" size={26} /></div>
              <div className="call-person"><strong>COSMO</strong><span>{isCallActive ? 'Talking with the clinic' : 'Your booking assistant'}</span></div>
              <div className="audio-bars" aria-hidden="true"><i /><i /><i /><i /><i /></div>
            </div>

            <div className="conversation-heading">
              <span>Conversation</span>
              <span className="live-label"><span /> {isCallActive ? 'LIVE DEMO' : 'SAMPLE'}</span>
            </div>

            <div className="conversation-list" aria-live="polite">
              {messages.length === 0 ? (
                <div className="empty-conversation">
                  <span className="empty-icon"><Icon name="headphones" size={21} /></span>
                  <strong>{callState === 'ended' ? 'Demo call ended' : 'Your call transcript will appear here'}</strong>
                  <p>{callState === 'ended' ? 'Start another demo when you are ready.' : 'Start a demo call to see COSMO speak Hungarian.'}</p>
                  {callState === 'ended' && <button className="text-button" type="button" onClick={resetCall}>Reset demo</button>}
                </div>
              ) : (
                messages.map((message) => {
                  const style = message.speaker === 'patient'
                    ? 'patient'
                    : message.speaker === 'receptionist'
                      ? 'receptionist'
                      : message.to === 'patient'
                        ? 'agent-patient'
                        : 'agent-receptionist'
                  const speakerLabel = message.speaker === 'patient'
                    ? `${message.full_name} · Patient`
                    : message.speaker === 'receptionist'
                      ? 'Receptionist'
                      : message.to === 'patient'
                        ? 'COSMO · Update for you'
                        : 'COSMO · Clinic call'

                  return (
                    <article className={`message message--${style}`} key={message.id}>
                      <div className="message-heading">
                        <strong>{speakerLabel}</strong>
                        <span>{message.to === 'patient' ? 'English update' : message.language}</span>
                      </div>
                      <p className="message-original">{message.original_text}</p>
                      {message.translated_text && <p className="message-translation"><Icon name="check" size={13} />{message.translated_text}</p>}
                    </article>
                  )
                })
              )}
            </div>

            {isCallActive && (
              <>
                <button className="simulate-button" type="button" onClick={addSimulatedReply}>Show next sample reply <Icon name="arrow" size={15} /></button>
                <footer className="call-controls">
                  <button className={`control-button ${isMuted ? 'control-button--active' : ''}`} type="button" onClick={() => setIsMuted((muted) => !muted)} aria-pressed={isMuted}>
                    <Icon name={isMuted ? 'micOff' : 'mic'} size={18} />{isMuted ? 'Unmute' : 'Mute'}
                  </button>
                  <button className={`control-button ${!isSpeaking ? 'control-button--active' : ''}`} type="button" onClick={() => setIsSpeaking((speaking) => !speaking)} aria-pressed={isSpeaking}>
                    <Icon name="volume" size={18} />{isSpeaking ? 'Sound on' : 'Sound off'}
                  </button>
                  <button className="end-button" type="button" onClick={endCall}><Icon name="phone" size={17} /> End demo</button>
                </footer>
              </>
            )}
          </section>
        </div>

        <footer className="page-footer"><Icon name="shield" size={14} /> Demo only — no personal information is sent or saved.</footer>
      </main>
    </div>
  )
}

export default App
