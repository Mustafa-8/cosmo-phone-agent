"""JSON contract between the voice pipeline (Dev 2) and the ADK agent (Dev 1).

Pure functions, standard library only: no network, no ADK. The voice side
imports these to talk to `adk api_server`:

    1. POST {base}/apps/phone_agent/users/{user_id}/sessions/{session_id}  body: {}
    2. For each transcript event:
         r = event_to_run_request(event, user_id)
         if r["status"] == "ok": POST {base}/run  json=r["request"]
    3. events_out = run_response_to_events(response_json, session_id)
"""

APP_NAME = "phone_agent"
HUMAN_SPEAKERS = ("patient", "receptionist")
LANGUAGE_OF_LISTENER = {"patient": "en", "receptionist": "hu"}


def event_to_run_request(event: dict, user_id: str) -> dict:
    """Convert one voice transcript event into a request body for ADK `/run`.

    Only final human speech reaches the agent. Partial transcripts would make
    the agent answer half sentences and waste Gemini quota. The agent's own
    voice (speaker "agent") is skipped so the agent never answers itself.

    Args:
        event: A transcript event from the voice pipeline, e.g.
            {"type": "transcript", "session_id": "demo-001",
             "speaker": "patient", "source_language": "en",
             "original_text": "I need to see a doctor.", "status": "committed"}
        user_id: The ADK user id the session was created under.

    Returns:
        {"status": "ok", "request": {...}} with the JSON body for POST /run,
        {"status": "skipped", "reason": "..."} when the event must not be sent,
        or {"status": "error", "error_message": "..."} when the event is invalid.
    """
    if event.get("type") != "transcript":
        return {"status": "skipped", "reason": f"type is {event.get('type')!r}, not 'transcript'"}
    if event.get("status") != "committed":
        return {"status": "skipped", "reason": "partial transcript (status is not 'committed')"}

    speaker = event.get("speaker")
    if speaker == "agent":
        return {"status": "skipped", "reason": "agent's own speech"}
    if speaker not in HUMAN_SPEAKERS:
        return {"status": "error", "error_message": f"unknown speaker {speaker!r}, expected one of {HUMAN_SPEAKERS}"}

    session_id = event.get("session_id")
    text = (event.get("original_text") or "").strip()
    if not session_id:
        return {"status": "error", "error_message": "missing session_id"}
    if not text:
        return {"status": "skipped", "reason": "empty original_text"}

    language = event.get("source_language") or LANGUAGE_OF_LISTENER[speaker]
    return {
        "status": "ok",
        "request": {
            "appName": APP_NAME,
            "userId": user_id,
            "sessionId": session_id,
            "newMessage": {"role": "user", "parts": [{"text": f"[{speaker}|{language}] {text}"}]},
        },
    }


def run_response_to_events(adk_events: list, session_id: str) -> list:
    """Convert the JSON list returned by ADK `/run` into outgoing events.

    Reads the `say` tool RESULTS (function responses), not the model's
    requests, so only messages that passed Python validation are spoken.

    Args:
        adk_events: The parsed JSON body returned by POST /run.
        session_id: The call's session id, copied into every event.

    Returns:
        A list of events in the voice pipeline's format. Spoken messages:
            {"type": "transcript", "session_id": ..., "speaker": "agent",
             "to": "receptionist" | "patient", "source_language": "hu" | "en",
             "target_language": "en" | "hu", "original_text": ...,
             "translated_text": None, "status": "committed"}
        Errors:
            {"type": "error", "session_id": ..., "status": "error", "message": ...}
    """
    if not isinstance(adk_events, list):
        return [{"type": "error", "session_id": session_id, "status": "error",
                 "message": f"unexpected /run response: {str(adk_events)[:200]}"}]

    out = []
    for adk_event in adk_events:
        if adk_event.get("errorCode"):
            out.append({"type": "error", "session_id": session_id, "status": "error",
                        "message": f"{adk_event['errorCode']}: {adk_event.get('errorMessage', '')}"})
            continue
        for part in (adk_event.get("content") or {}).get("parts") or []:
            fr = part.get("functionResponse")
            if not fr or fr.get("name") != "say":
                continue
            result = fr.get("response") or {}
            if result.get("status") != "ok":
                continue  # rejected by Python; the model gets the error and retries
            to = result["to"]
            spoken = LANGUAGE_OF_LISTENER[to]
            out.append({
                "type": "transcript",
                "session_id": session_id,
                "speaker": "agent",
                "to": to,
                "source_language": spoken,
                "target_language": "en" if spoken == "hu" else "hu",
                "original_text": result["text"],
                "translated_text": None,  # filled by translate() in step 5
                "status": "committed",
            })
    return out
