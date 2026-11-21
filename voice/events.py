"""Glue between the voice layer and the agent contract (phone_agent/contract.py).

Speech in:  STT callbacks -> transcript_event(...) -> contract.event_to_run_request(...) -> POST /run
Speech out: contract.run_response_to_events(...) -> speak_event(...) -> MP3 bytes for the browser

Standard library plus voice.tts only, so it can be tested without ADK.
"""
from __future__ import annotations

from typing import Optional

from . import tts


def transcript_event(session_id: str, speaker: str, language: str, text: str, committed: bool) -> dict:
    """Build one transcript event in the contract format from an STT result.

    Args:
        session_id: The call's session id.
        speaker: "patient" or "receptionist" (whose microphone it came from).
        language: ISO 639-1 code the speaker talks in ("en" or "hu").
        text: The transcript exactly as Scribe returned it. Never edited here.
        committed: True for committed_transcript, False for partial_transcript.
            Only committed events are forwarded to the agent; partials are UI preview only.
    """
    return {
        "type": "transcript",
        "session_id": session_id,
        "speaker": speaker,
        "source_language": language,
        "original_text": text,
        "status": "committed" if committed else "partial",
    }


async def speak_event(event: dict) -> Optional[bytes]:
    """Turn one outgoing agent event (from run_response_to_events) into MP3 audio.

    Speaks `original_text` word for word in `source_language`, the language of the listener.
    Returns None for non-speech events, empty text, or TTS mock mode (the browser then
    falls back to its own speechSynthesis).
    """
    if event.get("type") != "transcript" or event.get("speaker") != "agent":
        return None
    text = (event.get("original_text") or "").strip()
    if not text:
        return None
    return await tts.synthesize(text, event["source_language"])
