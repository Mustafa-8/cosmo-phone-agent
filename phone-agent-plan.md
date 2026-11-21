# COSMO Phone Agent – Plan

## Goal
An agent that books a clinic appointment for an international student by talking Hungarian with the receptionist, then reports back in English.

- **MVP (today):** live booking conversation with a simulated receptionist (a teammate on the microphone).
- **Phase 2:** live two-way translation mode.

## Principles
1. **The model decides, Python computes.** Gemini understands the request and leads the conversation. Dates, slots and files are computed by plain Python tools, so the model never invents a time.
2. **One agent with good tools.** Every tool has type hints, a precise docstring, and returns a `dict` with a `status` field (`"ok"`, `"error"`, ...). Tools never crash the agent.
3. **The instruction and `tools=[...]` must match.** When a tool is added or renamed, update both together.
4. **The agent is text in, text out.** Voice (Dev 2) and frontend (Dev 3) wrap around it. If voice fails during the demo, the text flow still works.
5. **Transparency.** The agent's first Hungarian sentence says it is an AI assistant calling on the student's behalf.

## Agent behaviour
1. Student request in English → choose specialty and time window.
2. Find a clinic → call (simulated).
3. Disclose AI in the first sentence, then negotiate a slot in Hungarian.
4. Confirm → create the calendar event → English summary to the student.
5. If the receptionist refuses to talk to an AI → hand off to the student and act as interpreter.

## Agent tools (Dev 1)
| Tool | The model decides | Python computes |
|---|---|---|
| `find_clinics(specialty, district)` | which specialty | filter `data/clinics.json` |
| `resolve_time_window(week_offset, part_of_day)` | "next week, afternoon" → (1, "afternoon") | concrete date and time ranges (Europe/Budapest) |
| `propose_slot(clinic_id, window_start, window_end)` | – | first free slot in the mock schedule |
| `create_calendar_event(clinic_id, start_iso, duration_min)` | the final agreed time | write an `.ics` file |
| `handoff_to_student(reason)` | when the receptionist refuses AI | return `status: "handoff"` |

## Folder layout
```
cosmo-phone-agent/          <- run adk web / adk api_server here
  phone_agent/              <- underscore: must be a valid Python package
    __init__.py
    agent.py                root_agent, instruction, tools=[...]
    tools/                  one file per area, to avoid merge conflicts
    data/clinics.json       3–5 mock Budapest clinics
  voice/                    Dev 2
  frontend/                 Dev 3
```

## Roles
| Dev | Member | Focus | First deliverable |
|---|---|---|---|
| 1 | Mustafa Ali Mohsin Albusultan (Leader) | Agent core, tools, `adk api_server`, error handling, merging | Agent replies in Hungarian in `adk web` |
| 2 | Noureldeen Elshawaf | Voice: Scribe STT, mic streaming, TTS, playback and interruption | A Hungarian sentence spoken by a standalone script |
| 3 | Redha Ali Hussein Hasan Al-Ashwal | React UI: transcript, call controls, language selection | UI that sends text to the API and shows the reply |
| 4 | Moises Raul Raunde | Integration, Hungarian tests, demo scenario, presentation | Written receptionist script (normal and refusal case) |

**Contract between Dev 1 and Dev 3:** the frontend calls `adk api_server` over HTTP. Agree on the request and response format at the start, and test it early.

## Workflow
- Each member works on their own branch (`<name>/<feature>`).
- When a piece works, push your branch. The leader merges it into `main` and tests it.
- Everyone pulls `main` regularly. Integrate small and often, not all at the end.
- Never commit `.env`. Variable names live in `.env.example`.

## Timeline (11:00–17:00)
| Time | Milestone |
|---|---|
| 11:00–11:45 | Setup on all machines; agent skeleton replies in Hungarian; API contract agreed |
| 11:45–13:15 | Agent tools; standalone voice script; UI talks to the API |
| 13:15–14:00 | Calendar event and English summary; text flow works end to end |
| 14:00–15:00 | Voice connected to the agent; handoff case |
| 15:00–16:00 | Full integration and demo rehearsals |
| 16:00–16:30 | Bug fixes only; record a backup demo video |
| 16:30–17:00 | Presentation |

## Risks
- **Free-tier limits on Gemini.** Keep test runs short. Test the logic with text before using voice.
- **ElevenLabs credits (coupon).** Check the balance. Pre-generate fixed sentences such as the AI disclosure and reuse them.
- **Live audio latency or failure.** The text flow is the fallback, and the backup video is the last resort.
- **Last-minute changes.** Nothing new after 16:00 unless it has been tested twice.

## Open questions for the organizers
1. Can partner tools (ElevenLabs) be used, and do they affect scoring?
2. Do participants get Google API access? If so, is it an AI Studio key or Google Cloud/Vertex credits?

## Future work
- Real phone calls (telephony, e.g. Twilio).
- General live translation for any call.
- More tasks beyond clinics (pharmacy, city offices, landlords).
