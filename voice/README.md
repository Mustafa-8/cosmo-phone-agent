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
| `web/pcm-worklet.js` | AudioWorklet that turns mic audio into 16 kHz PCM16; Vite serves it from this directory. |

## Run the smoke test
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ELEVENLABS_API_KEY and GOOGLE_API_KEY
python -m voice.check_voice
```
Then play `out_hu.mp3`. Each API falls back to mock mode when its key is missing (`STT_MODE`, `TRANSLATE_MODE` and `TTS_MODE` can force `real` or `mock`).

## Notes from testing
- Gemini: `gemini-2.5-flash` returns 404 for new users. `gemini-3.5-flash-lite` translated medical sentences in about 1 s and kept doses, dates and drug names exact. `gemini-3.5-flash` and `gemini-3.8-flash` often took over 20 s because they think by default.
- Scribe partial transcripts can be very wrong mid-sentence; the committed transcript was close to the original.

## Integration with the agent and browser

`phone_agent/integration.py` is the local FastAPI gateway between the React
frontend, this voice package, and the ADK API server. It creates the ADK
session, sends only committed receptionist transcripts through
`phone_agent/contract.py`, translates committed speech for the transcript,
and returns agent speech plus optional MP3 audio. Partial transcripts are UI
preview only. Provider keys remain on the backend.

Run `adk api_server`, then
`python -m uvicorn phone_agent.integration:app --host 127.0.0.1 --port 8001`,
then start the Vite frontend. Vite proxies `/api` and `/ws` to the gateway and
serves `web/pcm-worklet.js` from this package. The browser streams 16 kHz,
16-bit mono PCM. Use headphones to reduce echo.

In mock mode, `MockSTT` detects microphone activity but supplies scripted
booking lines; it does not recognize actual speech. A live clinic or telephone
call is not made.

## Tests
```bash
python -m pytest voice/tests    # mock mode, no keys needed
```
