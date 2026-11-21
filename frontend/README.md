# COSMO Frontend

React UI prototype for COSMO's clinic-appointment booking MVP.

## What is included

- Required student full name and appointment request form
- English-only student language selection and fixed Hungarian clinic language
- Sample-data mode with original Hungarian speech and English translations
- Live agent mode through the local integration gateway and a receptionist microphone stream
- Live transcript preview, translated committed receptionist speech, and routed agent audio playback
- Distinct patient, receptionist, agent-to-receptionist, and agent-to-patient message data
- Microphone mute, audio controls, and call teardown
- Responsive layout for desktop and mobile

Conversation messages use `speaker`, `original_text`, and `translated_text`. Agent messages also include `to: "receptionist"` for Hungarian call speech or `to: "patient"` for English student updates. The patient request includes `full_name`.

## Run locally

Start the ADK API server and the local integration gateway from the repository root:

```powershell
adk api_server
python -m uvicorn phone_agent.integration:app --host 127.0.0.1 --port 8001
```

Then start the frontend:

```powershell
npm ci
npm run dev
```

Open the local URL printed by Vite. Choose **Sample conversation** and use
**Show next sample reply** to advance through examples, or choose **Live agent
+ microphone** to start a session. Live mode requires a Google API key. STT,
translation, and TTS use mock mode when provider keys are absent; mock STT
responds with scripted booking lines and does not recognize actual speech.
Use headphones during audio tests.

## Live mode and privacy

The receptionist is still a teammate playing a clinic. This application does
not place real calls or contact clinics. The live gateway sends the entered
name and request to the local ADK service, streams microphone audio to the
configured speech service, and may write a local `.ics` file after a booking is
confirmed. Use fictional details only. Do not use this prototype for medical
advice or emergencies.

Provider credentials stay in the backend `.env` and must never be placed in
frontend variables. Vite proxies `/api` and `/ws` to the local gateway; a
production deployment needs an equivalent same-origin HTTP and WebSocket
reverse proxy.

## Checks

```powershell
npm run lint
npm run build
```
