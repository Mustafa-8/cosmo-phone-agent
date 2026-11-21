"""Offline tests for phone_agent/contract.py. Run from the repo root:

    python -m tests.test_contract
"""

from phone_agent.contract import event_to_run_request, run_response_to_events

NOUR_SAMPLE = {
    "type": "transcript",
    "session_id": "demo-001",
    "speaker": "patient",
    "source_language": "en",
    "target_language": "hu",
    "original_text": "I need to see a doctor.",
    "translated_text": "Orvoshoz kell mennem.",
    "status": "committed",
}


def test_committed_patient_event_becomes_run_request():
    r = event_to_run_request(NOUR_SAMPLE, user_id="student-1")
    assert r["status"] == "ok", r
    req = r["request"]
    assert req["appName"] == "phone_agent"
    assert req["userId"] == "student-1"
    assert req["sessionId"] == "demo-001"
    assert req["newMessage"]["parts"][0]["text"] == "[patient|en] I need to see a doctor."


def test_partial_event_is_skipped():
    r = event_to_run_request({**NOUR_SAMPLE, "status": "partial"}, user_id="u")
    assert r["status"] == "skipped", r


def test_agent_own_speech_is_skipped():
    r = event_to_run_request({**NOUR_SAMPLE, "speaker": "agent"}, user_id="u")
    assert r["status"] == "skipped", r


def test_unknown_speaker_is_error():
    r = event_to_run_request({**NOUR_SAMPLE, "speaker": "doctor"}, user_id="u")
    assert r["status"] == "error", r


def test_say_results_become_agent_events():
    # Shape copied from a real /run response.
    adk_events = [
        {"author": "cosmo_phone_agent", "content": {"parts": [
            {"functionCall": {"name": "say", "args": {"to": "receptionist", "text": "Jó napot!"}}}]}},
        {"author": "cosmo_phone_agent", "content": {"parts": [
            {"functionResponse": {"name": "say", "response": {"status": "ok", "to": "receptionist", "text": "Jó napot!"}}},
            {"functionResponse": {"name": "say", "response": {"status": "error", "error_message": "bad"}}}]}},
    ]
    out = run_response_to_events(adk_events, "demo-001")
    assert len(out) == 1, out  # the call itself and the rejected message are not spoken
    ev = out[0]
    assert ev["speaker"] == "agent" and ev["to"] == "receptionist"
    assert ev["source_language"] == "hu" and ev["target_language"] == "en"
    assert ev["original_text"] == "Jó napot!" and ev["status"] == "committed"


def test_adk_error_becomes_error_event():
    out = run_response_to_events([{"errorCode": "MODEL_RETURNED_NO_CONTENT", "errorMessage": "empty"}], "s")
    assert out == [{"type": "error", "session_id": "s", "status": "error",
                    "message": "MODEL_RETURNED_NO_CONTENT: empty"}], out


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
