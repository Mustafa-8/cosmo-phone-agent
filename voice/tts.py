"""Text-to-speech with ElevenLabs (POST /v1/text-to-speech/{voice_id}, model eleven_flash_v2_5).

Returns MP3 bytes, or None in mock mode. With None the browser speaks the text with its own
speechSynthesis voice, so the full flow can be demoed without an ElevenLabs key.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .config import settings

log = logging.getLogger("caller_ai.tts")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30)
    return _client


async def synthesize(text: str, language: str) -> Optional[bytes]:
    if settings.tts_effective == "mock" or not text.strip():
        return None
    voice_id = settings.voice_for(language)
    url = f"{settings.tts_base_url}/v1/text-to-speech/{voice_id}"
    body: dict = {"text": text, "model_id": settings.tts_model_id}
    if settings.tts_send_language_code:
        body["language_code"] = language
    headers = {"xi-api-key": settings.elevenlabs_api_key, "accept": "audio/mpeg"}
    params = {"output_format": settings.tts_output_format}
    r = await _http().post(url, json=body, headers=headers, params=params)
    if r.status_code == 400 and "language_code" in body:
        # Some model/voice combos reject language_code; retry without it rather than fail the turn.
        log.warning("TTS rejected language_code, retrying without it: %s", r.text[:200])
        body.pop("language_code")
        r = await _http().post(url, json=body, headers=headers, params=params)
    r.raise_for_status()
    return r.content
