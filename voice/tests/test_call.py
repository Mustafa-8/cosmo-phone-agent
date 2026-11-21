"""Two-phone call rooms (voice/call.py) against a fake in-process agent: no keys or network."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voice import call
from voice.config import settings

SAY_RECEPTION = "Jó napot kívánok! Dr. Kovács Annához szeretnék időpontot kérni. Megfelel?"
runs: list[str] = []

fake_agent = FastAPI()


@fake_agent.post("/apps/phone_agent/users/{user}/sessions/{sid}")
async def create_session(user: str, sid: str):
    return {"id": sid}


@fake_agent.post("/run")
async def run(body: dict):
    runs.append(body["newMessage"]["parts"][0]["text"])
    return [{"content": {"parts": [
        {"functionResponse": {"name": "say", "response": {"status": "ok", "to": "patient", "text": "Calling the clinic."}}},
        {"functionResponse": {"name": "say", "response": {"status": "ok", "to": "receptionist", "text": SAY_RECEPTION}}},
    ]}}]


@pytest.fixture()
def client(monkeypatch):
    runs.clear()
    call.rooms.clear()
    monkeypatch.setattr(call, "AGENT_APP", fake_agent)  # in-process, like serve.py
    monkeypatch.setattr(call, "HOLD_SECS", 0.05)
    monkeypatch.setattr(settings, "translate_mode", "mock")
    with TestClient(call.app) as c:
        yield c


def agent_messages(ws, n):
    got = []
    while len(got) < n:
        m = ws.receive_json()
        if m["type"] == "message" and m["speaker"] == "agent":
            got.append(m)
    return got


def test_fragments_are_joined_and_both_phones_get_cosmo(client):
    with client.websocket_connect("/ws?room=T1&role=patient") as pat, \
            client.websocket_connect("/ws?room=T1&role=receptionist") as rec:
        pat.send_json({"type": "say", "text": "Hi, I'm Alex Smith."})
        pat.send_json({"type": "say", "text": "I need a dentist next week."})
        msgs = agent_messages(rec, 2)
    assert runs == ["[patient|en] Hi, I'm Alex Smith. I need a dentist next week."]  # one turn
    assert {(m["to"], m["language"]) for m in msgs} == {("patient", "en"), ("receptionist", "hu")}


def test_reception_buttons_send_fixed_hungarian(client):
    with client.websocket_connect("/ws?room=T2&role=receptionist") as rec:
        rec.send_json({"type": "decision", "value": "confirm"})
        agent_messages(rec, 2)
        rec.send_json({"type": "decision", "value": "bogus"})  # ignored
    assert runs == [f"[receptionist|hu] {call.DECISIONS['confirm']}"]


def test_patient_cannot_press_reception_buttons(client):
    with client.websocket_connect("/ws?room=T3&role=patient") as pat:
        pat.send_json({"type": "decision", "value": "confirm"})
        pat.send_json({"type": "say", "text": "Hello"})
        agent_messages(pat, 2)
    assert runs == ["[patient|en] Hello"]
