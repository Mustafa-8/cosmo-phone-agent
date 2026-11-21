"""Voice bridge endpoints in mock mode: no API keys or network needed."""
import math
import struct

import pytest
from fastapi.testclient import TestClient

from voice import server
from voice.config import settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "stt_mode", "mock")
    monkeypatch.setattr(settings, "translate_mode", "mock")
    monkeypatch.setattr(settings, "tts_mode", "mock")
    with TestClient(server.app) as c:
        yield c


def tone(secs: float, amplitude: int = 8000) -> bytes:
    n = int(16000 * secs)
    return struct.pack(f"<{n}h", *(int(amplitude * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(n)))


def test_health_reports_modes(client):
    assert client.get("/health").json()["stt"] == "mock"


def test_tts_mock_returns_204_so_browser_speaks(client):
    assert client.post("/tts", json={"text": "Jó napot!", "language": "hu"}).status_code == 204


def test_translate_mock_known_phrase(client):
    r = client.post("/translate", json={"text": "Jó napot kívánok! Mióta fáj a feje?", "source": "hu", "target": "en"})
    assert r.json()["translated_text"] == "Good afternoon! How long have you had the headache?"


def test_stt_websocket_commits_after_speech(client):
    with client.websocket_connect("/ws/stt?language=hu") as ws:
        audio = tone(1.0)
        for i in range(0, len(audio), 3200):
            ws.send_bytes(audio[i:i + 3200])
        ws.send_text('{"type": "commit"}')
        msgs = []
        while True:
            m = ws.receive_json()
            msgs.append(m)
            if m["type"] == "committed":
                break
    assert msgs[-1]["text"]  # MockSTT returns the next demo line
    assert all(m["type"] in ("partial", "committed") for m in msgs)
