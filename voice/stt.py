"""Realtime speech-to-text, one stream per participant.

Real mode talks to the ElevenLabs realtime STT WebSocket:
  wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v3_live&...
  auth header: xi-api-key
  client -> server: {"message_type": "input_audio_chunk", "audio_base_64": ..., "commit": bool, "sample_rate": 16000}
  server -> client: session_started, partial_transcript, committed_transcript, plus error types.

Mock mode cannot understand audio, so it watches loudness instead: after a stretch of speech
followed by silence it "hears" the next line of a demo script. Typed text works in both modes.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import struct
from typing import Awaitable, Callable, Optional
from urllib.parse import urlencode

import websockets

from .config import settings

log = logging.getLogger("caller_ai.stt")

SAMPLE_RATE = 16000
OnPartial = Callable[[str], Awaitable[None]]
OnCommitted = Callable[[str, Optional[str]], Awaitable[None]]  # (text, detected language or None)
OnError = Callable[[str], Awaitable[None]]

ERROR_TYPES = {
    "error", "auth_error", "quota_exceeded", "commit_throttled", "unaccepted_terms", "rate_limited",
    "queue_overflow", "resource_exhausted", "session_time_limit_exceeded", "input_error",
    "invalid_request", "chunk_size_exceeded", "insufficient_audio_activity", "transcriber_error",
}


class BaseSTT:
    """language is an ISO 639-1 code, or "auto" to let Scribe detect it."""

    def __init__(self, language: str, on_partial: OnPartial, on_committed: OnCommitted, on_error: OnError):
        self.language = language
        self.on_partial = on_partial
        self.on_committed = on_committed
        self.on_error = on_error

    async def start(self) -> None: ...
    async def send_audio(self, pcm16: bytes) -> None: ...
    async def commit(self) -> None: ...
    async def close(self) -> None: ...


class ElevenLabsSTT(BaseSTT):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ws: Optional[websockets.ClientConnection] = None
        self.reader: Optional[asyncio.Task] = None
        self.closed = False

    def _url(self) -> str:
        params: list[tuple[str, str]] = [
            ("model_id", settings.stt_model_id),
            ("audio_format", "pcm_16000"),
            ("commit_strategy", settings.stt_commit_strategy),
        ]
        if self.language == "auto":
            # No language_code: Scribe detects it and reports it on committed_transcript_with_timestamps.
            params.append(("include_language_detection", "true"))
        else:
            params.append(("language_code", self.language))
        if settings.stt_commit_strategy == "vad":
            params.append(("vad_silence_threshold_secs", str(settings.stt_vad_silence_secs)))
        for term in [t.strip() for t in settings.stt_keyterms.split(",") if t.strip()]:
            params.append(("keyterms", term))
        return f"{settings.stt_base_url}/v1/speech-to-text/realtime?{urlencode(params)}"

    async def start(self) -> None:
        self.ws = await websockets.connect(
            self._url(),
            additional_headers={"xi-api-key": settings.elevenlabs_api_key},
            max_size=None,
        )
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        assert self.ws
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                kind = msg.get("message_type")
                if kind == "partial_transcript":
                    text = (msg.get("text") or "").strip()
                    if text:
                        await self.on_partial(text)
                elif kind == "committed_transcript" and self.language != "auto":
                    text = (msg.get("text") or "").strip()
                    if text:
                        await self.on_committed(text, None)
                elif kind == "committed_transcript_with_timestamps" and self.language == "auto":
                    # In auto mode this message follows committed_transcript and carries the language.
                    text = (msg.get("text") or "").strip()
                    if text:
                        await self.on_committed(text, msg.get("language_code"))
                elif kind == "session_started":
                    log.info("STT session %s started (%s)", msg.get("session_id"), self.language)
                elif kind in ERROR_TYPES:
                    await self.on_error(f"{kind}: {msg.get('error')}")
                elif kind == "warning":
                    log.warning("STT warning: %s", msg.get("warning"))
        except websockets.ConnectionClosed as exc:
            if not self.closed:
                await self.on_error(f"Speech recognition disconnected ({exc.code})")
        except Exception as exc:  # keep the call alive even if one stream dies
            log.exception("STT reader crashed")
            await self.on_error(f"Speech recognition failed: {exc}")

    async def _send(self, audio: bytes, commit: bool) -> None:
        if not self.ws or self.closed:
            return
        await self.ws.send(json.dumps({
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(audio).decode(),
            "commit": commit,
            "sample_rate": SAMPLE_RATE,
        }))

    async def send_audio(self, pcm16: bytes) -> None:
        await self._send(pcm16, False)

    async def commit(self) -> None:
        await self._send(b"", True)

    async def close(self) -> None:
        self.closed = True
        if self.ws:
            await self.ws.close()
        if self.reader:
            self.reader.cancel()


DEMO_SCRIPT = {
    "en": [
        "Hello, I have had a bad headache since yesterday and I need an appointment.",
        "It started yesterday morning. I took two paracetamol, 500 milligrams each.",
        "Yes, tomorrow at 10 o'clock works for me. Thank you.",
    ],
    "hu": [
        "Jó napot kívánok! Mióta fáj a feje?",
        "Rendben. Holnap délelőtt 10 órakor tudok időpontot adni Dr. Kovácshoz.",
        "Kérem, hozza magával a TAJ-kártyáját és a gyógyszerei listáját.",
    ],
}


class MockSTT(BaseSTT):
    """Energy-based fake recogniser: speak for ~0.6s, pause ~1s, and the next script line is committed."""

    SPEECH_RMS = 700
    MIN_SPEECH_SECS = 0.6
    SILENCE_SECS = 1.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.idx = 0
        self.speech_secs = 0.0
        self.silence_secs = 0.0
        self.partial_sent = False

    def _next_line(self) -> str:
        lang = "en" if self.language == "auto" else self.language
        lines = DEMO_SCRIPT.get(lang) or [f"(mock speech in {lang})"]
        line = lines[self.idx % len(lines)]
        self.idx += 1
        return line

    async def send_audio(self, pcm16: bytes) -> None:
        n = len(pcm16) // 2
        if n == 0:
            return
        samples = struct.unpack(f"<{n}h", pcm16[: n * 2])
        rms = math.sqrt(sum(s * s for s in samples) / n)
        secs = n / SAMPLE_RATE
        if rms > self.SPEECH_RMS:
            self.speech_secs += secs
            self.silence_secs = 0.0
            if self.speech_secs > 0.3 and not self.partial_sent:
                self.partial_sent = True
                await self.on_partial("…")
        elif self.speech_secs > 0:
            self.silence_secs += secs
            if self.silence_secs >= self.SILENCE_SECS:
                if self.speech_secs >= self.MIN_SPEECH_SECS:
                    await self.on_committed(self._next_line(), None)
                self.speech_secs = self.silence_secs = 0.0
                self.partial_sent = False

    async def commit(self) -> None:
        if self.speech_secs > 0.2:
            await self.on_committed(self._next_line(), None)
        self.speech_secs = self.silence_secs = 0.0
        self.partial_sent = False


def make_stt(language: str, on_partial: OnPartial, on_committed: OnCommitted, on_error: OnError) -> BaseSTT:
    cls = ElevenLabsSTT if settings.stt_effective == "real" else MockSTT
    return cls(language, on_partial, on_committed, on_error)
