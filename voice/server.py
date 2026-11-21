"""Voice bridge for the browser: keeps the ElevenLabs and Gemini keys on this machine.

    uvicorn voice.server:app --port 8001          (run from the repo root, next to adk api_server on 8000)

Endpoints
  GET  /health                       which parts run real or mock
  WS   /ws/stt?language=hu           browser sends binary 16 kHz PCM16 chunks (voice/web/pcm-worklet.js),
                                     optionally the text message {"type": "commit"} to force the end of a sentence.
                                     Server sends {"type": "partial"|"committed"|"error", "text": ...}.
  POST /tts        {text, language}  -> audio/mpeg (204 when TTS is mocked or text is empty: use browser speech)
  POST /translate  {text, source, target, speaker} -> TranslationResult as JSON (display only)

The voice layer never changes words: transcripts and speech are passed through exactly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import translation, tts
from .config import settings
from .stt import make_stt

log = logging.getLogger("cosmo.voice")
logging.basicConfig(level=logging.INFO)

class TtsRequest(BaseModel):
    text: str
    language: str


class TranslateRequest(BaseModel):
    text: str
    source: str
    target: str
    speaker: str = "receptionist"


async def warm_up_voices() -> None:
    # The first request to a library voice can take ~9 s; pay that before the demo, not during it.
    if settings.tts_effective == "real" and os.getenv("VOICE_WARMUP", "true").lower() != "false":
        async def warm():
            for lang in ("hu", "en"):
                try:
                    await tts.synthesize("Jó napot!" if lang == "hu" else "Hello!", lang)
                except Exception as exc:  # warm-up must never stop the server
                    log.warning("TTS warm-up for %s failed: %s", lang, exc)
            log.info("TTS voices warmed up")
        asyncio.create_task(warm())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await warm_up_voices()
    yield


app = FastAPI(title="COSMO voice bridge", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("VOICE_CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"stt": settings.stt_effective, "translate": settings.translate_effective, "tts": settings.tts_effective,
            "gemini_model": settings.gemini_model, "voice_hu": settings.voice_for("hu"),
            "voice_en": settings.voice_for("en")}


@app.post("/tts")
async def speak(req: TtsRequest) -> Response:
    try:
        audio = await tts.synthesize(req.text, req.language)
    except Exception as exc:
        log.exception("TTS failed")
        return Response(content=json.dumps({"error": f"TTS failed: {exc.__class__.__name__}"}),
                        status_code=502, media_type="application/json")
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/translate")
async def translate(req: TranslateRequest) -> dict:
    res = await translation.translate(req.text, req.source, req.target, req.speaker, [])
    return asdict(res)


@app.websocket("/ws/stt")
async def stt_stream(ws: WebSocket, language: str = "hu") -> None:
    await ws.accept()

    async def send(kind: str, text: str) -> None:
        try:
            await ws.send_json({"type": kind, "text": text})
        except Exception:
            pass  # browser already gone

    async def on_partial(text: str) -> None:
        await send("partial", text)

    async def on_committed(text: str, detected: str | None = None) -> None:
        await send("committed", text)

    async def on_error(msg: str) -> None:
        await send("error", msg)

    stt = make_stt(language, on_partial, on_committed, on_error)
    try:
        await stt.start()
    except Exception as exc:
        await send("error", f"Could not start speech recognition: {exc}")
        await ws.close()
        return
    log.info("STT stream open (%s, %s)", language, settings.stt_effective)
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes"):
                await stt.send_audio(msg["bytes"])
            elif msg.get("text"):
                try:
                    if json.loads(msg["text"]).get("type") == "commit":
                        await stt.commit()
                except ValueError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        await stt.close()
        log.info("STT stream closed (%s)", language)
