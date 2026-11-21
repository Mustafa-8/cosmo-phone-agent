# Integration checks (Dev 4)

Scripts to check that the agent, the voice bridge and the keys work together before a demo. Use fictional patient data only.

Start the servers from the repo root first:

```bash
adk api_server --allow_origins http://localhost:5173   # agent, port 8000
uvicorn voice.server:app --port 8001                   # voice bridge, port 8001
```

| Script | What it checks | Gemini / ElevenLabs use |
|---|---|---|
| `scripts/health_check.py` | Both servers are up, the keys are set and valid | none |
| `scripts/run_booking_demo.py` | **The stage demo:** AI disclosure, a 09:00 slot declined, 15:00 accepted, booking only after confirmation | about 10 Gemini requests |
| `scripts/run_demo.py` | Translation of five interpreting turns (`--mock` runs offline) | 5 Gemini requests |
| `scripts/test_translation.py` | 13 translation cases (numbers, drug names, unclear input, safety traps); writes a CSV for a Hungarian reviewer | 13 Gemini requests (26 with `--backtranslate`) |
| `scripts/generate_pronunciation.py` | Writes MP3s with the demo voice (`VOICE_ID_HU`, `TTS_MODEL_ID`) and a review table for a Hungarian listener | 10 ElevenLabs generations |

```bash
python integration/scripts/health_check.py
python integration/scripts/run_booking_demo.py
```

The free tier allows **15 Gemini requests per minute per Google project**, so wait about a minute between runs. Reports and audio go to `output/`, which git ignores.
