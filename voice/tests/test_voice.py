"""Voice layer tests in mock mode: no API keys or network needed.

    python -m pytest voice/tests
"""
import asyncio

import pytest

from voice import events, stt, translation, tts
from voice.config import settings


@pytest.fixture(autouse=True)
def mock_modes(monkeypatch):
    monkeypatch.setattr(settings, "stt_mode", "mock")
    monkeypatch.setattr(settings, "translate_mode", "mock")
    monkeypatch.setattr(settings, "tts_mode", "mock")


def run(coro):
    return asyncio.run(coro)


def test_tts_mock_and_empty_text_return_none():
    assert run(tts.synthesize("Jó napot!", "hu")) is None
    assert run(tts.synthesize("   ", "hu")) is None


def test_tts_never_calls_api_for_empty_text(monkeypatch):
    monkeypatch.setattr(settings, "tts_mode", "real")
    monkeypatch.setattr(settings, "elevenlabs_api_key", "dummy")
    assert run(tts.synthesize("", "hu")) is None


def test_make_stt_uses_mock_without_key():
    s = stt.make_stt("hu", None, None, None)
    assert isinstance(s, stt.MockSTT)


def test_translation_mock_keeps_dose_and_drug():
    text = "It started yesterday morning. I took two paracetamol, 500 milligrams each."
    r = run(translation.translate(text, "en", "hu", "patient", []))
    assert "500" in r.translated_text and "paracetamol" in r.translated_text


def test_translation_flags_urgent_even_in_mock():
    r = run(translation.translate("I have chest pain", "en", "hu", "patient", []))
    assert r.urgent


def test_transcript_event_matches_contract_and_keeps_text_exact():
    text = "Bevettem 500 mg paracetamolt."
    e = events.transcript_event("demo-001", "receptionist", "hu", text, committed=True)
    assert e == {"type": "transcript", "session_id": "demo-001", "speaker": "receptionist",
                 "source_language": "hu", "original_text": text, "status": "committed"}
    assert events.transcript_event("demo-001", "patient", "en", "I", committed=False)["status"] == "partial"


def test_speak_event_skips_non_agent_and_empty():
    human = events.transcript_event("s", "patient", "en", "Hello", committed=True)
    assert run(events.speak_event(human)) is None
    assert run(events.speak_event({"type": "transcript", "speaker": "agent", "original_text": " ",
                                   "source_language": "hu"})) is None


def test_speak_event_passes_text_unchanged(monkeypatch):
    seen = {}

    async def fake_synth(text, language):
        seen["args"] = (text, language)
        return b"mp3"

    monkeypatch.setattr(tts, "synthesize", fake_synth)
    agent = {"type": "transcript", "speaker": "agent", "to": "receptionist", "source_language": "hu",
             "original_text": "Jó napot! A COSMO MI asszisztense vagyok.", "status": "committed"}
    assert run(events.speak_event(agent)) == b"mp3"
    assert seen["args"] == ("Jó napot! A COSMO MI asszisztense vagyok.", "hu")
