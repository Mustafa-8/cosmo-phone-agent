# COSMO – Hungarian Phone Agent

> Team COSMO · Agentic AI Hackathon · GDG on Campus UD

## Problem
International students in Hungary often need to handle everyday tasks by phone, such as booking a doctor or dentist. Many receptionists speak only Hungarian, so a simple booking becomes a stressful barrier.

## What it does
The student tells COSMO in English what they need, for example *"Book me a dentist next week, in the afternoon."* COSMO then:

1. Picks a suitable clinic from the project's mock Budapest clinic data.
2. Starts a simulated receptionist conversation in Hungarian. Its first sentence says that it is an AI assistant calling on the student's behalf.
3. Negotiates a time slot in a live conversation.
4. Adds the confirmed appointment to the student's calendar.
5. Sends the student a short summary in English.

If the receptionist refuses to speak to an AI, COSMO can tell the student to
join the conversation. A live transfer and full two-way interpreter are not
implemented in this prototype.

**Hackathon MVP:** one task, booking a clinic appointment. A teammate plays
the receptionist through the microphone; no real phone call or clinic contact
is made.
**Phase 2:** a general two-way live translation mode.

## Architecture
```
Student (English form)
   → React frontend
   → Local FastAPI integration gateway
   → ADK API server (Gemini agent and booking tools)

Receptionist (Hungarian, browser microphone)
   → Local FastAPI integration gateway
   → Speech-to-text (ElevenLabs Scribe or scripted mock)
   → ADK agent → Hungarian speech (ElevenLabs TTS or browser speech)
   → React transcript with English receptionist translation
```

The receptionist is simulated by a teammate; no real clinic is called. Sample
mode remains available without the agent or microphone. Live mode sends the
entered name and request to the configured agent and can create a local `.ics`
file after the agent confirms a booking.

## Agent tools
The model decides what to do; plain Python computes and checks. Every tool returns a `dict` with a `status` field.

| Tool | What Python does |
|---|---|
| `find_clinics(specialty, district)` | Picks a matching mock clinic from `phone_agent/data/clinics.json` |
| `resolve_time_window(when, part_of_day)` | Turns "next week, afternoon" into real Budapest dates and hours (weekends skipped) |
| `check_slot(clinic_id, slot_start, when, part_of_day)` | Decides whether an offered time fits the patient's window and the clinic's opening hours |
| `create_calendar_event(clinic_id, slot_start, duration_min, patient_name, notes)` | Writes the confirmed appointment as an `.ics` file to `bookings/` (git-ignored) |
| `say(to, text)` | The only way the agent speaks: to `patient` (English) or `receptionist` (Hungarian) |

Messages to the agent are tagged with the speaker: `[patient|en] ...` or `[receptionist|hu] ...`. `phone_agent/contract.py` converts the voice layer's JSON events to and from ADK's `/run` format.

## Tech stack
| Layer | Tool |
|---|---|
| Agent | Google ADK, Gemini `gemini-3.5-flash-lite` |
| Backend API | Google ADK API server plus local FastAPI integration gateway |
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

Developer 4's demo scenarios, Hungarian voice checks, integration rehearsal
checklist, and presentation outline: [docs/dev4-demo-runbook.md](docs/dev4-demo-runbook.md)

## Setup
Requires Python 3.10+.

```bash
git clone https://github.com/Mustafa-8/cosmo-phone-agent.git
cd cosmo-phone-agent
python -m venv .venv
```

Activate the environment (`.venv\Scripts\Activate.ps1` in Windows PowerShell,
or `source .venv/bin/activate` on macOS/Linux), then install the dependencies:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your own keys to `.env`. Keep it local and use fictional patient details
during testing.

Start three terminals from the repository root:

```bash
adk api_server
python -m uvicorn phone_agent.integration:app --host 127.0.0.1 --port 8001
cd frontend
npm ci
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The frontend proxies its
API and WebSocket traffic to the local integration gateway; the gateway talks
to the ADK server. Select **Sample conversation** to use the built-in replies,
or **Live agent + microphone** to use configured services. For mock voice
testing, set `STT_MODE=mock`, `TRANSLATE_MODE=mock`, and `TTS_MODE=mock`. Live
agent mode still requires a valid Google API key and a running ADK server.
Use headphones when testing audio to reduce microphone echo.

Install test dependencies and run the offline tests (no provider calls or keys):

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest tests voice/tests
cd frontend
npm run lint
npm run build
```

## Free-tier limits
- `gemini-3.5-flash-lite` on the free tier allows **15 requests per minute per Google project**. One booking call uses about 8–10 requests, because every tool step is a request.
- Optionally set `TRANSLATION_GOOGLE_API_KEY` from a separate Google project so
  translation does not share the agent's quota.
- During rehearsals, wait about a minute between full test calls. A `429 RESOURCE_EXHAUSTED` in the server log means the quota ran out.

## Frontend

The React interface for the student appointment-booking flow is in `frontend/`.

```bash
cd frontend
npm ci
npm run dev
```

The frontend supports sample data and an opt-in live agent/audio mode. The live
mode uses the local integration gateway and does not place real clinic calls.
In live mode, the student's name and request are sent to the configured agent.
Confirmed appointments may create a local `.ics` file in the git-ignored
`bookings/` directory. Do not use real patient information.

## Rules for contributors
- Never commit `.env` or paste keys in chat. Only `.env.example` (variable names) is committed.
- Work on your own branch (`<name>/<feature>`), pull before you push.
- Nobody pushes to `main` directly. Open a pull request and wait for the leader's review; the leader merges.
- Every agent tool has type hints and a precise docstring, and returns a `dict` with a `status` field.
- Live integration is for a simulated receptionist only; it is not a real clinic or emergency service.
