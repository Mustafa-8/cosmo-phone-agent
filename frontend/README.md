# COSMO Frontend

React UI prototype for COSMO's clinic-appointment booking MVP.

## What is included

- Student booking request form
- English/Hungarian language selectors
- Simulated call panel with original Hungarian speech and English translations
- Demo microphone, audio, and end-call controls
- Responsive layout for desktop and mobile

## Run locally

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite. Submit the sample appointment request to start a simulated call, then use **Show next sample reply** to advance the example conversation.

## Prototype limitations

This frontend currently uses local sample data. It does not make clinic calls, capture microphone audio, run speech recognition, use text-to-speech, contact the ADK agent, or create calendar events. Do not enter real personal or medical information into this demo.

The API and voice integration should be added after agreeing on the request/response format with Developers 1 and 2. Configure service URLs through Vite environment variables; never place provider secrets in frontend variables.

## Checks

```powershell
npm run lint
npm run build
```
