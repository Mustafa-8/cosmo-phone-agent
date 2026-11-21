"""Standalone smoke test for the voice layer, one API at a time.

    python -m voice.check_voice        (run from the repo root)

1. Gemini translates an English sentence to Hungarian.
2. ElevenLabs TTS speaks the Hungarian (saved to out_hu.mp3) and also renders 16 kHz PCM.
3. That PCM is streamed into Scribe realtime STT and the transcript is printed.
If step 3 prints the Hungarian sentence back, the whole voice pipeline works.
Synthetic patient data only.
"""
import asyncio
import base64
import json
from pathlib import Path
from urllib.parse import urlencode

import httpx
import websockets

from .config import settings
from . import translation

SENTENCE = "I have had a headache since yesterday and I took 500 milligrams of paracetamol."
FALLBACK_HU = "Tegnap óta fáj a fejem, és bevettem 500 milligramm paracetamolt."


async def check_gemini() -> str:
    if not settings.gemini_api_key:
        print("[skip] GOOGLE_API_KEY / GEMINI_API_KEY missing, using a fixed Hungarian sentence")
        return FALLBACK_HU
    res = await translation.translate(SENTENCE, "en", "hu", "patient", [])
    print(f"[gemini] {settings.gemini_model}: {res}")
    return res.translated_text


async def tts(text: str, lang: str, fmt: str) -> bytes:
    url = f"{settings.tts_base_url}/v1/text-to-speech/{settings.voice_for(lang)}"
    body = {"text": text, "model_id": settings.tts_model_id, "language_code": lang}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, params={"output_format": fmt}, json=body,
                         headers={"xi-api-key": settings.elevenlabs_api_key})
        if r.status_code == 400:
            body.pop("language_code")
            r = await c.post(url, params={"output_format": fmt}, json=body,
                             headers={"xi-api-key": settings.elevenlabs_api_key})
        if r.status_code >= 400:
            print(f"[tts] HTTP {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
        return r.content


async def check_stt(pcm: bytes, lang: str) -> None:
    params = urlencode({"model_id": settings.stt_model_id, "language_code": lang,
                        "audio_format": "pcm_16000", "commit_strategy": "manual"})
    url = f"{settings.stt_base_url}/v1/speech-to-text/realtime?{params}"
    async with websockets.connect(url, additional_headers={"xi-api-key": settings.elevenlabs_api_key}) as ws:
        chunk = 3200  # 100 ms of 16 kHz 16-bit mono
        for i in range(0, len(pcm), chunk):
            await ws.send(json.dumps({"message_type": "input_audio_chunk", "sample_rate": 16000, "commit": False,
                                      "audio_base_64": base64.b64encode(pcm[i:i + chunk]).decode()}))
            await asyncio.sleep(0.02)
        await ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": "", "commit": True,
                                  "sample_rate": 16000}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            print(f"[stt] {msg.get('message_type')}: {msg.get('text') or msg.get('error') or ''}")
            if msg.get("message_type") == "committed_transcript" or "error" in msg:
                break


async def main():
    hu = await check_gemini()
    if not hu.strip():
        print("[stop] Gemini returned no translation; fix that before testing TTS/STT.")
        return
    if not settings.elevenlabs_api_key:
        print("[skip] ELEVENLABS_API_KEY missing")
        return
    mp3 = await tts(hu, "hu", "mp3_44100_128")
    Path("out_hu.mp3").write_bytes(mp3)
    print(f"[tts] {settings.tts_model_id}: wrote out_hu.mp3 ({len(mp3)} bytes), play it and check pronunciation")
    pcm = await tts(hu, "hu", "pcm_16000")
    await check_stt(pcm, "hu")


if __name__ == "__main__":
    asyncio.run(main())
