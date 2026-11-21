# COSMO Frontend

React UI for COSMO's simulated clinic-booking conversation.

## What is included

- Required student name and appointment request form
- Live-agent and sample-data modes
- Receptionist role-play by typing or browser microphone
- Hungarian speech recognition, English subtitles, and spoken agent replies through the voice bridge
- Call controls, status and error feedback, and a responsive desktop/mobile layout

The browser sends finished receptionist transcripts to the ADK agent. Partial
transcripts are previews only. No real clinic is contacted and no telephone
call or live transfer is made.

## Run locally

Start the ADK API and voice bridge from the repository root in separate
terminals:

```powershell
adk api_server --allow_origins http://localhost:5173
uvicorn voice.server:app --port 8001
```

Then start Vite:

```powershell
npm ci
npm run dev
```

Use Node.js 20.19+ or 22.12+ for Vite 8. Open the local URL, select **Live
agent**, start a call, and use **Speak as receptionist** or type a receptionist
reply. Choose **Sample data** to run the conversation without the agent or
voice services, then use **Show next sample reply**.

The default service URLs are `http://localhost:8000` for ADK and
`http://localhost:8001` for the voice bridge. Optional `VITE_AGENT_URL` and
`VITE_VOICE_URL` values configure them; never put provider secrets in frontend
variables.

Use fictional patient details only. Translation subtitles are a convenience
and are not verified medical advice.

## Checks

```powershell
npm run lint
npm run build
```
