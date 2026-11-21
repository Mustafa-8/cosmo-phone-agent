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
adk web            # chat UI for testing
adk api_server     # HTTP API for the frontend
```

If `adk web` fails with `_make_subprocess_transport NotImplementedError`, run `adk web --no-reload`.

## Frontend

The React interface for the student appointment-booking flow is in `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

The current frontend is a simulated prototype. It does not connect to the ADK agent or live voice services yet; agree on the API and audio contracts before integrating them.

## Rules for contributors
- Never commit `.env` or paste keys in chat. Only `.env.example` (variable names) is committed.
- Work on your own branch (`<name>/<feature>`), pull before you push.
- Every agent tool has type hints and a precise docstring, and returns a `dict` with a `status` field.
