"""One server for the online demo: ADK agent + voice bridge + built website on a single port.

    cd frontend && VITE_AGENT_URL= VITE_VOICE_URL=/voice npm run build && cd ..
    python serve.py                      # http://localhost:8080  (PORT=... to change)

Routes
  /apps/..., /run, ...   the ADK agent API (same as `adk api_server`)
  /voice/...             the voice bridge (voice/server.py: /voice/ws/stt, /voice/tts, /voice/translate, /voice/health)
  /                      the website from frontend/dist

Same origin for everything, so no CORS setup, and one HTTPS tunnel covers the microphone requirement.
`./run_online.sh` builds, starts this server and opens a public Cloudflare tunnel.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from voice import server as voice_server  # also loads .env (keys stay on this machine)

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "frontend" / "dist"
PORT = int(os.getenv("PORT", "8080"))


@asynccontextmanager
async def lifespan(_app):
    # Mounted sub-apps do not run their own startup, so warm up the TTS voices here.
    await voice_server.warm_up_voices()
    yield


app = get_fast_api_app(agents_dir=str(ROOT), web=False, host="127.0.0.1", port=PORT, lifespan=lifespan)
app.mount("/voice", voice_server.app)
if not DIST.exists():
    raise SystemExit("frontend/dist is missing: build it first (see the top of serve.py or run ./run_online.sh)")
app.mount("/", StaticFiles(directory=DIST, html=True), name="website")  # last, so API routes win

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
