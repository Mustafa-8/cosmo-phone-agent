from types import SimpleNamespace

from fastapi.testclient import TestClient

from phone_agent import integration


def _say_event(to="receptionist", text="Jó napot kívánok!"):
    return [{
        "content": {
            "parts": [{
                "functionResponse": {
                    "name": "say",
                    "response": {"status": "ok", "to": to, "text": text},
                },
            }],
        },
    }]


def test_health_does_not_expose_provider_keys():
    response = TestClient(integration.app).get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "GOOGLE_API_KEY" not in data and "ELEVENLABS_API_KEY" not in data


def test_start_call_creates_session_and_sends_name_to_agent(monkeypatch):
    seen = []

    async def fake_post(path, payload):
        seen.append((path, payload))
        return None if path != "/run" else _say_event()

    async def fake_speak(_event):
        return None

    monkeypatch.setattr(integration, "_post_adk", fake_post)
    monkeypatch.setattr(integration.events, "speak_event", fake_speak)

    response = TestClient(integration.app).post(
        "/api/calls",
        json={"full_name": "Alex Morgan", "request": "I need a dentist next week."},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["call_id"]
    assert body["messages"][0]["speaker"] == "patient"
    assert body["messages"][0]["full_name"] == "Alex Morgan"
    assert body["messages"][1]["speaker"] == "agent"
    assert body["messages"][1]["to"] == "receptionist"
    assert seen[0][0].endswith(f"/sessions/{body['call_id']}")
    assert "[patient|en] My full name is Alex Morgan." in seen[1][1]["newMessage"]["parts"][0]["text"]


def test_start_call_rejects_blank_details_without_calling_agent(monkeypatch):
    async def unexpected_call(*_args):
        raise AssertionError("ADK should not be called for blank input")

    monkeypatch.setattr(integration, "_post_adk", unexpected_call)
    response = TestClient(integration.app).post(
        "/api/calls",
        json={"full_name": "  ", "request": "  "},
    )
    assert response.status_code == 422


def test_receptionist_committed_audio_is_translated_and_forwarded(monkeypatch):
    calls = []

    async def fake_post(path, payload):
        calls.append((path, payload))
        return None if path != "/run" else _say_event(text="A beteg neve?")

    async def fake_translate(*_args):
        return SimpleNamespace(
            translated_text="What is the patient's name?",
            urgent=False,
            needs_clarification=False,
            clarification_reason="",
        )

    async def fake_speak(_event):
        return None

    class FakeSTT:
        def __init__(self, _language, _partial, committed, _error):
            self.committed = committed
            self.sent = False

        async def start(self):
            return None

        async def send_audio(self, _audio):
            if not self.sent:
                self.sent = True
                await self.committed("Mi a beteg neve?", None)

        async def commit(self):
            return None

        async def close(self):
            return None

    monkeypatch.setattr(integration, "_post_adk", fake_post)
    monkeypatch.setattr(integration.translation, "translate", fake_translate)
    monkeypatch.setattr(integration.events, "speak_event", fake_speak)
    monkeypatch.setattr(integration.stt, "make_stt", lambda *args: FakeSTT(*args))

    with TestClient(integration.app) as client:
        started = client.post(
            "/api/calls",
            json={"full_name": "Alex Morgan", "request": "I need a dentist next week."},
        ).json()
        with client.websocket_connect(f"/ws/calls/{started['call_id']}") as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_bytes(b"\x00\x00")
            transcript = websocket.receive_json()
            agent = websocket.receive_json()

    assert transcript["type"] == "transcript"
    assert transcript["event"]["speaker"] == "receptionist"
    assert transcript["event"]["translated_text"] == "What is the patient's name?"
    assert agent["event"]["speaker"] == "agent"
    assert agent["event"]["to"] == "receptionist"
    agent_request = [payload for path, payload in calls if path == "/run"][-1]
    assert "[receptionist|hu] Mi a beteg neve?" in agent_request["newMessage"]["parts"][0]["text"]
