# COSMO Frontend

React UI prototype for COSMO's clinic-appointment booking MVP.

## What is included

- Required student full name and appointment request form
- English-only student language selection and fixed Hungarian clinic language
- Simulated call panel with original Hungarian speech and English translations
- Distinct patient, receptionist, agent-to-receptionist, and agent-to-patient message data
- Demo microphone, audio, and end-call controls
- Responsive layout for desktop and mobile

Conversation messages use `speaker`, `original_text`, and `translated_text`. Agent messages also include `to: "receptionist"` for Hungarian call speech or `to: "patient"` for English student updates. The patient request includes `full_name`.

## Run locally

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite. Enter a full name, submit the sample appointment request to start a simulated call, then use **Show next sample reply** to advance through the receptionist and agent examples, including a sample English booking update.

## Prototype limitations

This frontend currently uses local sample data. It does not make clinic calls, capture microphone audio, run speech recognition, use text-to-speech, contact the ADK agent, or create calendar events. Do not enter real personal or medical information into this demo.

The API and voice integration should be added after agreeing on the request/response format with Developers 1 and 2. Configure service URLs through Vite environment variables; never place provider secrets in frontend variables.

## Checks

```powershell
npm run lint
npm run build
```
