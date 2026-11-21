"""Local HTTP/WebSocket gateway connecting the browser, voice layer, and ADK."""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
import uuid
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import websockets

from phone_agent import contract
from voice import events, stt, translation
from voice.config import settings as voice_settings

log = logging.getLogger("cosmo.integration")

ADK_BASE_URL = os.getenv("ADK_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADK_USER_ID = "cosmo-demo"
ADK_TIMEOUT_SECONDS = 60.0
CALL_LIFETIME_SECONDS = 600.0
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.getenv(
        "COSMO_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
}

app = FastAPI(title="COSMO local integration gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class StartCallRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    request: str = Field(min_length=1, max_length=2000)


@dataclass
class CallContext:
    session_id: str
    user_id: str
    active: bool = False
    history: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)


_calls: dict[str, CallContext] = {}


def _language_name(code: str) -> str:
    return {"en": "English", "hu": "Hungarian"}.get(code, code)


async def _post_adk(path: str, payload: dict) -> list | None:
    try:
        async with httpx.AsyncClient(timeout=ADK_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{ADK_BASE_URL}{path}", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("ADK request failed (%s)", exc.__class__.__name__)
        raise HTTPException(
            status_code=502,
            detail="The agent service is unavailable. Check that the ADK API server is running.",
        ) from exc
    if path == "/run":
        try:
            data = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="The agent returned invalid JSON.") from exc
        if not isinstance(data, list):
            raise HTTPException(status_code=502, detail="The agent returned an unexpected response.")
        return data
    return None


async def _prepare_call(session_id: str, full_name: str, request_text: str) -> list[dict]:
    await _post_adk(
        f"/apps/{contract.APP_NAME}/users/{ADK_USER_ID}/sessions/{session_id}",
        {},
    )
    event = events.transcript_event(
        session_id,
        "patient",
        "en",
        f"My full name is {full_name}. Appointment request: {request_text}",
        committed=True,
    )
    result = contract.event_to_run_request(event, user_id=ADK_USER_ID)
    if result["status"] != "ok":
        raise HTTPException(status_code=400, detail=result.get("error_message", "Invalid patient request."))
    response = await _post_adk("/run", result["request"])
    agent_events = contract.run_response_to_events(response or [], session_id)
    errors = [event["message"] for event in agent_events if event.get("type") == "error"]
    if errors:
        raise HTTPException(status_code=502, detail=errors[0])
    return agent_events


async def _with_audio(event: dict) -> dict:
    result = dict(event)
    result["language"] = _language_name(event.get("source_language", ""))
    try:
        audio = await events.speak_event(event)
    except httpx.HTTPError as exc:
        log.warning("TTS request failed (%s)", exc.__class__.__name__)
        result["audio_error"] = "Text-to-speech is unavailable; browser speech may be used instead."
        return result
    if audio:
        result["audio_b64"] = base64.b64encode(audio).decode("ascii")
        result["audio_mime"] = "audio/mpeg"
    return result


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "agent_configured": bool(voice_settings.gemini_api_key),
        "stt_mode": voice_settings.stt_effective,
        "translation_mode": voice_settings.translate_effective,
        "tts_mode": voice_settings.tts_effective,
    }


@app.post("/api/calls")
async def start_call(body: StartCallRequest) -> dict:
    full_name = body.full_name.strip()
    request_text = body.request.strip()
    if not full_name or not request_text:
        raise HTTPException(status_code=422, detail="Enter your full name and appointment request.")

    now = time.monotonic()
    expired = [
        call_id for call_id, call in _calls.items()
        if not call.active and now - call.created_at > CALL_LIFETIME_SECONDS
    ]
    for call_id in expired:
        _calls.pop(call_id, None)

    session_id = uuid.uuid4().hex
    agent_events = await _prepare_call(session_id, full_name, request_text)
    patient_event = {
        "type": "transcript",
        "session_id": session_id,
        "speaker": "patient",
        "source_language": "en",
        "target_language": "hu",
        "language": "English",
        "original_text": request_text,
        "translated_text": "",
        "full_name": full_name,
        "status": "committed",
    }
    messages = [patient_event]
    for event in agent_events:
        if event.get("type") == "transcript":
            messages.append(await _with_audio(event))
    _calls[session_id] = CallContext(session_id=session_id, user_id=ADK_USER_ID)
    return {"call_id": session_id, "messages": messages}


@app.websocket("/ws/calls/{call_id}")
async def call_audio(websocket: WebSocket, call_id: str) -> None:
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008, reason="Origin is not allowed.")
        return
    call = _calls.get(call_id)
    if not call or call.active:
        await websocket.close(code=1008, reason="Call is unavailable.")
        return
    if time.monotonic() - call.created_at > CALL_LIFETIME_SECONDS:
        _calls.pop(call_id, None)
        await websocket.close(code=1008, reason="Call is unavailable.")
        return

    call.active = True
    try:
        await websocket.accept()
    except WebSocketDisconnect:
        call.active = False
        return
    outgoing: asyncio.Queue[dict] = asyncio.Queue()
    incoming: asyncio.Queue[dict] = asyncio.Queue()
    call.history.clear()

    async def on_partial(text: str) -> None:
        await outgoing.put({
            "type": "transcript",
            "event": {
                "type": "transcript",
                "session_id": call.session_id,
                "speaker": "receptionist",
                "source_language": "hu",
                "original_text": text,
                "translated_text": "",
                "status": "partial",
            },
        })

    async def on_committed(text: str, detected_language: str | None = None) -> None:
        event = events.transcript_event(
            call.session_id,
            "receptionist",
            detected_language or "hu",
            text,
            committed=True,
        )
        await incoming.put(event)

    async def on_error(message: str) -> None:
        await outgoing.put({"type": "error", "message": message})

    async def send_messages() -> None:
        while True:
            await websocket.send_json(await outgoing.get())

    async def process_transcripts() -> None:
        while True:
            event = await incoming.get()
            try:
                source = event["source_language"]
                translated = await translation.translate(
                    event["original_text"],
                    source,
                    "en",
                    "receptionist",
                    call.history,
                )
                event.update({
                    "translated_text": translated.translated_text,
                    "urgent": translated.urgent,
                    "needs_clarification": translated.needs_clarification,
                })
                if translated.clarification_reason:
                    event["clarification_reason"] = translated.clarification_reason
                call.history.append(
                    f"receptionist ({source}): {event['original_text']} || patient (en): {translated.translated_text}"
                )
                await outgoing.put({"type": "transcript", "event": event})
                result = contract.event_to_run_request(event, user_id=call.user_id)
                if result["status"] != "ok":
                    if result["status"] == "error":
                        await outgoing.put({"type": "error", "message": result["error_message"]})
                    continue
                response = await _post_adk("/run", result["request"])
                for agent_event in contract.run_response_to_events(response or [], call.session_id):
                    if agent_event.get("type") == "error":
                        await outgoing.put({"type": "error", "message": agent_event["message"]})
                    else:
                        await outgoing.put({"type": "transcript", "event": await _with_audio(agent_event)})
            except HTTPException as exc:
                await outgoing.put({"type": "error", "message": exc.detail})

    sender = asyncio.create_task(send_messages())
    processor = asyncio.create_task(process_transcripts())
    recognizer = stt.make_stt("hu", on_partial, on_committed, on_error)
    try:
        await recognizer.start()
        await websocket.send_json({
            "type": "ready",
            "stt_mode": voice_settings.stt_effective,
            "translation_mode": voice_settings.translate_effective,
        })
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                await recognizer.send_audio(message["bytes"])
            elif message.get("text") == "commit":
                await recognizer.commit()
    except WebSocketDisconnect:
        pass
    except (httpx.HTTPError, HTTPException, OSError, TimeoutError, websockets.exceptions.WebSocketException) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else "The voice or agent service is unavailable."
        log.warning("Call connection failed (%s)", exc.__class__.__name__)
        await websocket.send_json({"type": "error", "message": detail})
    finally:
        await recognizer.close()
        sender.cancel()
        processor.cancel()
        await asyncio.gather(sender, processor, return_exceptions=True)
        call.active = False
        _calls.pop(call_id, None)
