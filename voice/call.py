"""Two-phone call rooms: a patient phone and a receptionist phone talk through the COSMO agent.

Mounted at /call by serve.py.   WS /call/ws?room=ABCD&role=patient|receptionist

Phone -> server
  {"type": "start", "name": "...", "request": "..."}   patient only: starts the booking call (typed)
  {"type": "reset"}                                      patient only: clear the room for a new call
  {"type": "say", "text": "..."}                         a finished sentence (committed STT) or typed text
  {"type": "playing", "on": true|false}                  this phone started/stopped playing COSMO audio
Server -> phones
  {"type": "message", "id", "speaker", "to", "language", "text", "translation"}   (history is replayed on join)
  {"type": "translation", "id", "text"}                  English subtitle for a Hungarian message
  {"type": "state", "started", "thinking", "roles": {"patient": n, "receptionist": n}}
  {"type": "playing", "on"}                              some phone is playing COSMO audio: pause your mic
  {"type": "error", "message"}

The patient's first spoken sentence (name + request) starts the call. Each human sentence is sent to the agent exactly as heard, one agent turn at a time per room.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from phone_agent import contract

from . import translation

log = logging.getLogger("cosmo.call")
AGENT_URL = os.getenv("AGENT_URL", f"http://127.0.0.1:{os.getenv('PORT', '8080')}")
USER_ID = "two-phone-demo"
LANG = {"patient": "en", "receptionist": "hu"}

app = FastAPI(title="COSMO two-phone call rooms")


class Room:
    def __init__(self, code: str):
        self.code = code
        self.clients: dict[WebSocket, str] = {}
        self.session_id: str | None = None
        self.history: list[dict] = []
        self.lock = asyncio.Lock()
        self.thinking = False
        self.playing: set[WebSocket] = set()
        self.next_id = 1

    def state(self) -> dict:
        roles = {r: sum(1 for v in self.clients.values() if v == r) for r in LANG}
        return {"type": "state", "started": self.session_id is not None, "thinking": self.thinking, "roles": roles}

    async def send(self, ws: WebSocket, msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            pass

    async def broadcast(self, msg: dict, skip: WebSocket | None = None) -> None:
        for ws in list(self.clients):
            if ws is not skip:
                await self.send(ws, msg)

    async def add_message(self, speaker: str, text: str, language: str, to: str | None = None) -> dict:
        msg = {"type": "message", "id": self.next_id, "speaker": speaker, "to": to,
               "language": language, "text": text, "translation": None}
        self.next_id += 1
        self.history.append(msg)
        await self.broadcast(msg)
        if language == "hu":
            asyncio.create_task(self.translate(msg))
        return msg

    async def translate(self, msg: dict) -> None:
        res = await translation.translate(msg["text"], "hu", "en", msg["speaker"], [])
        if res.translated_text:
            msg["translation"] = res.translated_text
            await self.broadcast({"type": "translation", "id": msg["id"], "text": res.translated_text})

    async def agent_turn(self, speaker: str, text: str) -> None:
        async with self.lock:
            self.thinking = True
            await self.broadcast(self.state())
            try:
                async with httpx.AsyncClient(base_url=AGENT_URL, timeout=120) as c:
                    if self.session_id is None:
                        sid = f"room-{self.code}-{uuid.uuid4().hex[:6]}"
                        r = await c.post(f"/apps/{contract.APP_NAME}/users/{USER_ID}/sessions/{sid}", json={})
                        r.raise_for_status()
                        self.session_id = sid
                    event = {"type": "transcript", "session_id": self.session_id, "speaker": speaker,
                             "source_language": LANG[speaker], "original_text": text, "status": "committed"}
                    req = contract.event_to_run_request(event, USER_ID)
                    if req["status"] != "ok":
                        return
                    r = await c.post("/run", json=req["request"])
                    if r.status_code != 200:
                        hint = " (often the Gemini free-tier limit; wait a minute)" if r.status_code in (429, 500) else ""
                        await self.broadcast({"type": "error", "message": f"Agent error: HTTP {r.status_code}{hint}"})
                        return
                    for ev in contract.run_response_to_events(r.json(), self.session_id):
                        if ev["type"] == "error":
                            await self.broadcast({"type": "error", "message": ev["message"]})
                        else:
                            await self.add_message("agent", ev["original_text"], ev["source_language"], ev["to"])
            except Exception as exc:
                log.exception("agent turn failed")
                await self.broadcast({"type": "error", "message": f"Agent unreachable: {exc.__class__.__name__}"})
            finally:
                self.thinking = False
                await self.broadcast(self.state())


rooms: dict[str, Room] = {}


@app.websocket("/ws")
async def call_ws(ws: WebSocket, room: str, role: str) -> None:
    code = "".join(ch for ch in room.upper() if ch.isalnum())[:12]
    if role not in LANG or not code:
        await ws.close(code=4400)
        return
    await ws.accept()
    r = rooms.setdefault(code, Room(code))
    r.clients[ws] = role
    for msg in r.history:
        await r.send(ws, msg)
    await r.broadcast(r.state())
    try:
        while True:
            data = await ws.receive_json()
            kind = data.get("type")
            if kind == "start" and role == "patient":
                name = (data.get("name") or "").strip()
                request = (data.get("request") or "").strip()
                if not request:
                    continue
                if r.session_id is not None:  # a new start resets the room
                    r.session_id, r.history = None, []
                    await r.broadcast({"type": "reset"})
                await r.add_message("patient", request, "en")
                spoken = f"My name is {name}. {request}" if name else request
                asyncio.create_task(r.agent_turn("patient", spoken))
            elif kind == "reset" and role == "patient":
                r.session_id, r.history = None, []
                await r.broadcast({"type": "reset"})
                await r.broadcast(r.state())
            elif kind == "say":
                text = (data.get("text") or "").strip()
                if text:
                    await r.add_message(role, text, LANG[role])
                    asyncio.create_task(r.agent_turn(role, text))
            elif kind == "playing":
                if data.get("on"):
                    r.playing.add(ws)
                else:
                    r.playing.discard(ws)
                await r.broadcast({"type": "playing", "on": bool(r.playing)}, skip=ws)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        r.clients.pop(ws, None)
        r.playing.discard(ws)
        await r.broadcast({"type": "playing", "on": bool(r.playing)})
        await r.broadcast(r.state())
