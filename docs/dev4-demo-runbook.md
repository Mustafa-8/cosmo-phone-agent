# COSMO demo runbook

This runbook gives the team a repeatable clinic-booking demo, a receptionist
role-play script, Hungarian voice checks, and a short presentation outline.
Use fictional details only.

## Current demo boundary

The live experience uses the React frontend, ADK API server, and the voice
bridge in `voice/server.py`. The browser sends finished receptionist
transcripts to the agent; partial transcripts are UI previews. The bridge
handles speech recognition, spoken replies, and subtitle translation. Sample
data remains available when services or provider credentials are unavailable.

The receptionist is a teammate role-playing a clinic. No mode places a real
telephone call or contacts a real clinic. A refusal can be demonstrated as a
scenario, but do not claim a live human transfer occurred. Calendar events are
created only after the agent receives receptionist confirmation.

## Start the demo

From the repository root, use three terminals:

```powershell
# Terminal 1: agent API
adk api_server --allow_origins http://localhost:5173
```

```powershell
# Terminal 2: voice bridge
uvicorn voice.server:app --port 8001
```

```powershell
# Terminal 3: frontend
cd frontend
npm ci
npm run dev
```

Open the Vite URL, select **Live agent**, start a call, and use **Speak as
receptionist** or type a receptionist reply. Use **Sample data** and **Show
next sample reply** for a standalone demo. Vite 8 requires Node.js 20.19+ or
22.12+.

## Demo setup

- Patient name: **Alex Morgan** (fictional).
- Request: **“I need a dentist appointment next week, in the afternoon.”**
- Clinic for the role-play: **Dental Plus Fogászat**, 1061 Budapest, Király utca
  10. The agent should select the clinic from its data; the receptionist script
  should not imply a real clinic was contacted.
- The receptionist should use a weekday and time that the agent has actually
  requested and that the clinic is open. For the standard request, afternoon
  means 12:00–17:00 Budapest time. Do not hard-code a calendar date: use the
  date shown by the running demo.
- If live speech is unavailable, use the frontend's sample-data mode and say
  that the conversation is simulated.

## Scenario A: successful booking role-play

The receptionist is a teammate playing the clinic. Keep each line short and
wait for COSMO to finish before responding.

COSMO's **first** Hungarian message already contains the AI disclosure and the
full request (doctor type, weekdays and hours), so the receptionist answers
with an offer straight away. A greeting such as "Miben segíthetek?" would make
COSMO repeat the request and waste quota.

| Turn | Speaker | Script / action |
|---|---|---|
| 1 | Patient | Enter the fictional name and request above. |
| 2 | COSMO | Tells the patient in English which clinic it is calling, then opens the call in Hungarian: AI disclosure plus the request with the weekdays and hours. |
| 3 | Receptionist | Offers a time **outside** the window: “Jó napot! Jövő kedden reggel 9-kor tudnék adni időpontot.” |
| 4 | COSMO | Checks the slot, politely declines, and asks for an afternoon time. |
| 5 | Receptionist | Offers a time **inside** the window: “Akkor jövő kedden 15 órakor megfelel? Mi a beteg neve?” |
| 6 | COSMO | Checks the slot, accepts it and gives the name. It must **not** book or say goodbye yet. |
| 7 | Receptionist | Confirms: “Rendben, rögzítettem, fél órás vizsgálat lesz. Viszonthallásra!” |
| 8 | COSMO | Books (a local `.ics` file), says goodbye in Hungarian, and sends the patient an English summary with the exact date and time. |

This exact script is checked automatically by
`integration/scripts/run_booking_demo.py` (about 10 Gemini requests). Run it
before rehearsing with the voice layer.

Useful receptionist prompts:

- Ask for the patient's name: **“Mi a beteg neve?”**
- If COSMO accepts an invalid time without checking it, stop and mark the
  integration check as failed.
- Do not add medical advice, insurance details, or required documents that were
  not supplied by the demo.

## Scenario B: receptionist refuses an AI caller

Use the same fictional patient and request. The receptionist refuses immediately
after COSMO's required AI disclosure.

> **Not yet verified live.** The agent handles a refusal through its
> instruction only (there is no handoff tool yet). Run this scenario once in a
> rehearsal before showing it, and skip it if COSMO does not behave as below.

| Turn | Speaker | Script / action |
|---|---|---|
| 1 | COSMO | Discloses in Hungarian that it is an AI assistant calling on the student's behalf. |
| 2 | Receptionist | “Sajnálom, mesterséges intelligenciával nem tudunk időpontot egyeztetni. Kérem, a beteg telefonáljon személyesen.” |
| 3 | COSMO | Apologises briefly in Hungarian, then tells the patient in English that they need to join the call and that COSMO can interpret. |
| 4 | Presenter | Explain that this is a scripted handoff scenario unless a live handoff implementation has been completed and verified. Do not claim a person was actually connected. |

## Hungarian voice and translation checks

Run these checks with a fluent Hungarian speaker listening to the actual voice
output. Browser speech synthesis is only a fallback and does not validate the
ElevenLabs voice.

| Check | Expected result |
|---|---|
| AI disclosure | Clearly understandable; “mesterséges intelligencia” is not dropped or mispronounced. |
| Appointment request | The specialty, requested weekdays, and time window match the English request. |
| Invalid slot | COSMO does not accept a time outside the requested window or clinic opening hours. |
| Valid slot | COSMO repeats the offered weekday and time accurately before confirming. |
| Patient update | English summary preserves the clinic, address, date, and time returned by the agent; no invented details. |
| Refusal | The receptionist refusal is understood and the patient-facing update explains the next step without claiming a transfer happened. |
| Audio quality | Speech is intelligible at normal playback volume, with no clipped start/end, overlapping replies, or stale queued audio after interruption. |

Record pass/fail, the tested mode (mock or real), and any exact misheard words
in the demo notes. Never use real patient information.

## Free-tier quota

- `gemini-3.5-flash-lite` allows **15 requests per minute per Google project**.
  One booking call uses about 8–10 requests, and voice subtitles add about two
  per turn.
- Put a key from a **different Google project** in `GEMINI_API_KEY`, so the
  translation does not use the agent's quota (`GOOGLE_API_KEY`).
- Wait about **one minute** between full rehearsal runs. If COSMO stops
  answering or the frontend shows an HTTP 500 error, the quota has probably run
  out: wait a minute, then start a new call.

## Integration rehearsal checklist

- [ ] Run `python integration/scripts/health_check.py`: both servers up, keys
  set and valid.
- [ ] Run `python integration/scripts/run_booking_demo.py`: 4/4 turns pass.

- [ ] Start the agent API and verify a text request can create an ADK session and
  return agent speech events in the agreed contract format.
- [ ] Start the voice bridge and verify `GET http://localhost:8001/health`
  responds.
- [ ] Verify a browser live session connects to both the ADK API and voice
  bridge.
- [ ] Verify partial transcripts remain UI-only; only committed patient or
  receptionist transcripts reach the agent.
- [ ] Verify agent messages are routed by `to`: Hungarian to the receptionist
  and English to the patient.
- [ ] Verify speech output speaks the exact `original_text` in the message's
  language; do not paraphrase medical details.
- [ ] Verify the microphone stream is 16 kHz, mono, signed PCM16 and that
  stopping or muting the microphone stops further chunks.
- [ ] Verify the browser audio worklet is served at `/pcm-worklet.js`, and check
  that the microphone is ignored while COSMO is speaking.
- [ ] Run sample-data mode before using provider credentials; exercise mock
  voice modes where configured.
- [ ] Test real STT, translation, and TTS only with team-owned credentials in a
  local `.env`; never put keys in frontend environment variables or commit
  them.
- [ ] Confirm a confirmed booking writes the expected `.ics` file and summary;
  use fictional patient data and check that generated booking files remain
  untracked.
- [ ] Do not mark the end-to-end voice integration complete until the browser,
  voice service, and ADK agent have passed a live rehearsal together.
- [ ] Treat human handoff as unavailable until its tool and end-to-end checks
  exist.

## Three-minute presentation

1. **Problem (20 sec):** International students can struggle to book care when
   the clinic conversation is in Hungarian.
2. **Demo (90 sec):** Enter a fictional request, show the English patient
   message, the AI disclosure, the Hungarian receptionist exchange, and the
   English summary. If using sample data, call it a simulated conversation.
3. **Reliability (40 sec):** Show that the agent checks offered slots against
   the patient's time window and clinic hours, and explain the refusal scenario.
4. **Architecture (30 sec):** Explain the separate React, ADK, and voice
   components, and identify which integrations were actually exercised.
5. **Limitations and next step (20 sec):** State clearly whether the run was
   sample-data, mock voice, or live voice. Do not claim a real call, booking,
   calendar event, or handoff unless it was verified.

Keep a second operator ready to switch to sample-data mode if audio, API access,
or provider quotas fail. Do not spend presentation time exposing API keys or
debug logs.
