# COSMO demo runbook

This runbook gives the team a repeatable clinic-booking demo, a receptionist
role-play script, Hungarian voice checks, and a short presentation outline.
Use fictional details only.

## Current demo boundary

The frontend has two paths: sample mode keeps the **Show next sample reply**
demo, and the integration branch adds a live-agent path through
`phone_agent/integration.py`. The gateway connects the browser microphone to
STT, translation, and the ADK agent; audio is returned to the browser for
playback. Confirm this integration is present in the branch being rehearsed;
it is not part of `main` until the integration PR is reviewed and merged.

In mock voice mode the microphone activity triggers scripted booking replies;
it does not recognize actual speech. A live provider run needs team-owned
credentials. Neither mode calls a real clinic or places a telephone call.

The agent includes clinic lookup, time-window resolution, slot checking,
speech output, and calendar-event creation. Calendar events are written only
after receptionist confirmation. A live human handoff tool is not available;
present the refusal path as a scripted scenario unless it has been separately
implemented and verified.

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

| Turn | Speaker | Script / action |
|---|---|---|
| 1 | Patient | Enter the fictional name and request above. |
| 2 | COSMO | Selects a clinic and time window, then tells the patient in English which clinic and dates it will ask about. |
| 3 | COSMO | Starts the call in Hungarian and identifies itself as an AI assistant calling on behalf of a student. |
| 4 | Receptionist | “Jó napot kívánok! Miben segíthetek?” |
| 5 | COSMO | Briefly explains the appointment request in Hungarian, using the dates and hours returned by the agent. |
| 6 | Receptionist | Offers a time outside the patient's window first, for example 10:00 on one of the requested weekdays. |
| 7 | COSMO | Checks the offered time, politely declines if it does not fit, and asks for a time in the requested window. |
| 8 | Receptionist | Offers an available time inside the requested window and the clinic's opening hours, for example 15:00 on a requested weekday. |
| 9 | COSMO | Checks the offered time before accepting. If accepted, asks for the patient's name only if the receptionist requests it. |
| 10 | Receptionist | “Rendben, [weekday] [time]-kor várjuk. Viszont hallásra!” Confirm only within the role-play; the agent can create a local `.ics` event after confirmation. |
| 11 | COSMO | Thanks the receptionist in Hungarian, then gives the patient a concise English summary. |

Useful receptionist prompts:

- Ask for the patient's name: **“Mi a beteg neve?”**
- If COSMO accepts an invalid time without checking it, stop and mark the
  integration check as failed.
- Do not add medical advice, insurance details, or required documents that were
  not supplied by the demo.

## Scenario B: receptionist refuses an AI caller

Use the same fictional patient and request. The receptionist refuses immediately
after COSMO's required AI disclosure.

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

## Integration rehearsal checklist

- [ ] Start the agent API and verify a text request can create an ADK session and
  return agent speech events in the agreed contract format.
- [ ] Start the integration gateway and verify a browser live session connects
  to the agent API.
- [ ] Verify partial transcripts remain UI-only; only committed patient or
  receptionist transcripts reach the agent.
- [ ] Verify agent messages are routed by `to`: Hungarian to the receptionist
  and English to the patient.
- [ ] Verify speech output speaks the exact `original_text` in
  `source_language`; do not paraphrase medical details.
- [ ] Verify the microphone stream is 16 kHz, mono, signed PCM16 and that
  stopping or muting the microphone stops further chunks.
- [ ] Verify the browser audio worklet is served at `/pcm-worklet.js`, and test
  playback interruption with headphones to avoid echo.
- [ ] Run both scenarios above in mock mode before using provider credentials.
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
