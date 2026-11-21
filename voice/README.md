# Voice layer (Dev 2)

Microphone → ElevenLabs Scribe (speech to text) → Gemini (translation) → ElevenLabs Flash v2.5 (text to speech) → speaker.

The voice layer never changes words: it transcribes and speaks exactly what it is given. Only `committed` transcripts should be sent on (to the agent or to translation). Partial transcripts change a lot while someone is speaking and are only for showing a live preview.

## Files
| File | What it does |
|---|---|
| `stt.py` | Scribe realtime WebSocket client (`ElevenLabsSTT`), a `MockSTT`, and `make_stt(language, on_partial, on_committed, on_error)`. Interface: `start()`, `send_audio(pcm16_bytes)`, `commit()`, `close()`. Audio is 16 kHz 16-bit mono PCM. |
| `tts.py` | `synthesize(text, language)` → MP3 bytes, or `None` in mock mode or for empty text. |
| `translation.py` | `translate(text, source, target, speaker, context)` → `TranslationResult` with `translated_text`, `needs_clarification`, `urgent`, `detected_language`. Also `summarise()`. |
| `config.py` | Settings read from the repo-root `.env`. |
| `check_voice.py` | Standalone smoke test of all three APIs. |
| `web/audio.js` | Browser side: `startMic(onChunk, onLevel)` and `PlaybackQueue` (plays replies in order, `stop()` interrupts). |
| `web/pcm-worklet.js` | AudioWorklet that turns mic audio into 16 kHz PCM16. Serve it from the frontend's `public/` folder. |

## Run the smoke test
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ELEVENLABS_API_KEY, GOOGLE_API_KEY (agent) and GEMINI_API_KEY (translation, other project)
python -m voice.check_voice
```
Then play `out_hu.mp3`. Each API falls back to mock mode when its key is missing (`STT_MODE`, `TRANSLATE_MODE` and `TTS_MODE` can force `real` or `mock`).

## Notes from testing
- Gemini: `gemini-2.5-flash` returns 404 for new users. `gemini-3.5-flash-lite` translated medical sentences in about 1 s and kept doses, dates and drug names exact. `gemini-3.5-flash` and `gemini-3.8-flash` often took over 20 s because they think by default.
- Scribe partial transcripts can be very wrong mid-sentence; the committed transcript was close to the original.

## Run the full voice demo (3 terminals, from the repo root)
```bash
pip install -r requirements.txt
cp .env.example .env                                   # ELEVENLABS_API_KEY + GOOGLE_API_KEY + GEMINI_API_KEY
adk api_server --allow_origins http://localhost:5173   # agent, port 8000
uvicorn voice.server:app --port 8001                   # voice bridge, port 8001 (keys stay here)
cd frontend && npm install && npm run dev              # website, port 5173 (Vite 8 needs Node 20.19+ or 22.12+)
```
In the website choose **Live agent**, start a call, then press **Speak as receptionist** and talk Hungarian.
- Finished sentences (committed transcripts) go to the agent exactly as heard; the grey "Hearing: ..." line is only the live preview.
- Every COSMO message is spoken by ElevenLabs (Hungarian voice Andris to the clinic, English to the student), in order.
- Hungarian lines get an English translation underneath (Gemini, display only; the agent always gets the original Hungarian).
- Half duplex: the mic is ignored while COSMO speaks, so it never hears itself even without headphones. **Sound off** stops playback; **Mute** stops sending the mic.
- If the voice server is down, typing receptionist replies still works and replies are read by the browser's own voice.

Bridge endpoints (`voice/server.py`): `GET /health`, `WS /ws/stt?language=hu` (binary 16 kHz PCM16 in, `{"type": "partial"|"committed"|"error", "text"}` out, send `{"type":"commit"}` to end a sentence), `POST /tts {text, language}` → MP3 (204 = use browser speech), `POST /translate {text, source, target}`.

## Integration with the agent (`phone_agent/contract.py`)
`voice/events.py` produces and consumes exactly the event format in `contract.py`.

```python
from voice import stt, events, tts
from phone_agent import contract

# Speech in: one STT stream per human on the call
async def on_committed(text, detected_language=None):
    ev = events.transcript_event(session_id, "receptionist", "hu", text, committed=True)
    r = contract.event_to_run_request(ev, user_id)
    if r["status"] == "ok":
        adk_events = (await http.post(f"{base}/run", json=r["request"])).json()
        for out in contract.run_response_to_events(adk_events, session_id):
            mp3 = await events.speak_event(out)   # speech out, word for word
            # send mp3 (or out["original_text"] if mp3 is None) to the browser

async def on_partial(text):
    pass  # UI preview only, never sent to the agent

receptionist_stt = stt.make_stt("hu", on_partial, on_committed, on_error)
await receptionist_stt.start()
await receptionist_stt.send_audio(pcm16_bytes)   # 16 kHz 16-bit mono from web/pcm-worklet.js
```

Browser side: copy `web/pcm-worklet.js` into `frontend/public/` (it is loaded from `/pcm-worklet.js`) and import `startMic` and `PlaybackQueue` from `web/audio.js`. Call `PlaybackQueue.stop()` to interrupt playback when the person starts talking. Use headphones to avoid echo.

## Tests
```bash
python -m pytest voice/tests    # mock mode, no keys needed (includes the bridge endpoints)
```
