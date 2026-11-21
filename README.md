# COSMO – Hungarian Phone Agent

> Team COSMO · Agentic AI Hackathon · GDG on Campus UD

## Problem
International students in Hungary often need to handle everyday tasks by phone, such as booking a doctor or dentist. Many receptionists speak only Hungarian, so a simple booking becomes a stressful barrier.

## What it does
The student tells COSMO in English what they need, for example *"Book me a dentist next week, in the afternoon."* COSMO then:

1. Picks a suitable clinic.
2. Calls the receptionist and speaks Hungarian. Its first sentence says that it is an AI assistant calling on the student's behalf.
3. Negotiates a time slot in a live conversation.
4. Adds the confirmed appointment to the student's calendar.
5. Sends the student a short summary in English.

If the receptionist does not want to talk to an AI, COSMO brings the student onto the call and acts as a live interpreter.

**Hackathon MVP:** one task, booking a clinic appointment. The call is simulated: a teammate plays the receptionist through the microphone.
**Phase 2:** a general two-way live translation mode.

## Architecture
```
Receptionist (Hungarian, mic)
   → Speech-to-text (ElevenLabs Scribe)
   → COSMO agent (Google ADK + Gemini): decides, calls tools, replies in Hungarian
   → Text-to-speech (ElevenLabs)
   → Frontend (React): live transcript and call controls
```
The agent works on **text in, text out**. Voice and frontend sit around it, so each part can be built and tested on its own.

## Agent tools
The model decides what to do; plain Python computes and checks. Every tool returns a `dict` with a `status` field.

| Tool | What Python does |
|---|---|
| `find_clinics(specialty, district)` | Picks a real clinic from `phone_agent/data/clinics.json` (4 mock Budapest clinics) |
| `resolve_time_window(when, part_of_day)` | Turns "next week, afternoon" into real Budapest dates and hours (weekends skipped) |
| `check_slot(clinic_id, slot_start, when, part_of_day)` | Decides whether an offered time fits the patient's window and the clinic's opening hours |
| `create_calendar_event(clinic_id, slot_start, duration_min, patient_name, notes)` | Writes the confirmed appointment as an `.ics` file to `bookings/` (git-ignored) |
| `say(to, text)` | The only way the agent speaks: to `patient` (English) or `receptionist` (Hungarian) |

Messages to the agent are tagged with the speaker: `[patient|en] ...` or `[receptionist|hu] ...`. `phone_agent/contract.py` converts the voice layer's JSON events to and from ADK's `/run` format.

## Tech stack
| Layer | Tool |
|---|---|
| Agent | Google ADK, Gemini `gemini-3.5-flash-lite` |
| Backend API | `adk api_server` (FastAPI, built into ADK) |
| Voice | ElevenLabs Scribe (STT) and TTS |
| Frontend | React |
| Calendar | `.ics` file generated in Python |

## Team
| # | Member | Role | Owns |
|---|---|---|---|
| 1 | Mustafa Ali Mohsin Albusultan **(Leader)** | Backend & agent | ADK root agent, instruction, tools (clinic search, slot finding), `adk api_server`, error and timeout handling |
| 2 | Noureldeen Elshawaf | Voice AI engineer | ElevenLabs Scribe live STT, microphone streaming, TTS, audio playback and interruption |
| 3 | Redha Ali Hussein Hasan Al-Ashwal | Frontend | React interface, live transcript, call controls, language selection |
| 4 | Moises Raul Raunde | Integration & product | Integrating all parts, Hungarian pronunciation tests, demo scenario, presentation |

Full plan and timeline: [phone-agent-plan.md](phone-agent-plan.md)

## Setup
Requires Python 3.10+.

```bash
git clone https://github.com/Mustafa-8/cosmo-phone-agent.git
cd cosmo-phone-agent
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in your own keys
```

Run the agent (from the repository root, the folder **above** the agent folder):

```bash
adk web                                                # chat UI for testing
adk api_server --allow_origins http://localhost:5173   # HTTP API for the React frontend
```

- `--allow_origins` is needed so the browser (Vite on port 5173) may call the API on port 8000 (CORS).
- After changing agent code, **restart** the server and start a **new session** before testing.
- If `adk web` fails with `_make_subprocess_transport NotImplementedError`, run `adk web --no-reload`.

Run the offline tests (no Gemini calls, no keys needed):

```bash
for t in contract clinics time_window slots calendar_event; do python -m tests.test_$t; done
```

## Free-tier limits
- `gemini-3.5-flash-lite` on the free tier allows **15 requests per minute per Google project**. One booking call uses about 8–10 requests, because every tool step is a request.
- Use API keys from **different Google projects** for the agent and for the voice layer's translation, so they don't share one quota.
- During rehearsals, wait about a minute between full test calls. A `429 RESOURCE_EXHAUSTED` in the server log means the quota ran out.

## Rules for contributors
- Never commit `.env` or paste keys in chat. Only `.env.example` (variable names) is committed.
- Work on your own branch (`<name>/<feature>`), pull before you push.
- Nobody pushes to `main` directly. Open a pull request and wait for the leader's review; the leader merges.
- Every agent tool has type hints and a precise docstring, and returns a `dict` with a `status` field.
