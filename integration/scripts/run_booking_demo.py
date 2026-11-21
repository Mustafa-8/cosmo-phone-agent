"""Run the COSMO booking demo against the live agent and check each step.

    adk api_server --allow_origins http://localhost:5173     (repo root, port 8000)
    python integration/scripts/run_booking_demo.py

This is the scenario we show on stage. One run uses about 10 Gemini requests,
so on the free tier (15 per minute) wait about a minute between runs.
Fictional patient data only.
"""
import os
import sys
import time

import requests

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8000")
APP = "phone_agent"
USER = "dev4-check"
AI_DISCLOSURE = "mesterséges intelligencia"

# Each turn: who speaks, what they say, and what must (or must not) happen in the agent's reply.
TURNS = [
    {"speaker": "patient", "lang": "en",
     "text": "My name is Alex Morgan. I need a dentist appointment next week, in the afternoon.",
     # plan_appointment (since #16) does the clinic + time-window work in one step; the older
     # flow used find_clinics + resolve_time_window. Either is fine.
     "expect": {"tools_any": [["plan_appointment"], ["find_clinics", "resolve_time_window"]],
                "say_to": ["patient", "receptionist"],
                "receptionist_contains": AI_DISCLOSURE, "no_booking": True}},
    {"speaker": "receptionist", "lang": "hu",
     "text": "Jó napot! Jövő kedden reggel 9-kor tudnék adni időpontot.",
     "expect": {"slot_fits": False, "say_to": ["receptionist"], "no_booking": True}},
    {"speaker": "receptionist", "lang": "hu",
     "text": "Akkor jövő kedden 15 órakor megfelel? Mi a beteg neve?",
     "expect": {"slot_fits": True, "say_to": ["receptionist"], "no_booking": True}},
    {"speaker": "receptionist", "lang": "hu",
     "text": "Rendben, rögzítettem, fél órás vizsgálat lesz. Viszonthallásra!",
     "expect": {"booking_ok": True, "say_to": ["receptionist", "patient"]}},
]


def run_turn(session_id, turn):
    """Send one message to the agent and return the parsed ADK events."""
    body = {"appName": APP, "userId": USER, "sessionId": session_id,
            "newMessage": {"role": "user", "parts": [{"text": f"[{turn['speaker']}|{turn['lang']}] {turn['text']}"}]}}
    response = requests.post(f"{AGENT_URL}/run", json=body, timeout=90)
    response.raise_for_status()
    return response.json()


def summarize(events):
    """Pull out what matters from the ADK events: tools called, their results, spoken messages, errors."""
    out = {"tools": [], "results": {}, "said": [], "errors": []}
    for event in events:
        if event.get("errorCode"):
            out["errors"].append(f"{event['errorCode']}: {event.get('errorMessage', '')}")
        for part in (event.get("content") or {}).get("parts") or []:
            call, result = part.get("functionCall"), part.get("functionResponse")
            if call and call["name"] != "say":
                out["tools"].append(call["name"])
            if result:
                response = result.get("response") or {}
                if result["name"] == "say" and response.get("status") == "ok":
                    out["said"].append((response["to"], response["text"]))
                elif result["name"] != "say":
                    out["results"][result["name"]] = response
    return out


def check(turn, got):
    """Return a list of problems for this turn (empty list = pass)."""
    expect, problems = turn["expect"], []
    problems += got["errors"]
    for tool in expect.get("tools", []):
        if tool not in got["tools"]:
            problems.append(f"expected the agent to call {tool}")
    options = expect.get("tools_any")
    if options and not any(all(t in got["tools"] for t in option) for option in options):
        problems.append("expected " + " or ".join(" + ".join(option) for option in options))
    spoken_to = {to for to, _ in got["said"]}
    for listener in expect.get("say_to", []):
        if listener not in spoken_to:
            problems.append(f"expected a message to the {listener}")
    if "receptionist_contains" in expect:
        first = next((text for to, text in got["said"] if to == "receptionist"), "")
        if expect["receptionist_contains"] not in first.lower():
            problems.append("first Hungarian sentence is missing the AI disclosure")
    if "slot_fits" in expect:
        slot = got["results"].get("check_slot")
        if slot is None:
            problems.append("expected the agent to call check_slot")
        elif slot.get("fits") is not expect["slot_fits"]:
            problems.append(f"check_slot fits={slot.get('fits')}, expected {expect['slot_fits']}")
    booking = got["results"].get("create_calendar_event")
    if expect.get("no_booking") and booking and booking.get("status") == "ok":
        problems.append("booked before the receptionist confirmed")
    if expect.get("booking_ok") and not (booking and booking.get("status") == "ok"):
        problems.append(f"expected a booking, got {booking}")
    return problems


def main():
    print("=== COSMO booking demo check ===")
    print(f"Agent: {AGENT_URL}\n")
    session_id = f"dev4-{int(time.time())}"
    try:
        requests.post(f"{AGENT_URL}/apps/{APP}/users/{USER}/sessions/{session_id}", json={}, timeout=10).raise_for_status()
    except requests.RequestException as error:
        print(f"Cannot create a session: {error}\nIs adk api_server running on port 8000?")
        sys.exit(1)

    passed = 0
    for number, turn in enumerate(TURNS, start=1):
        start = time.time()
        try:
            got = summarize(run_turn(session_id, turn))
        except requests.RequestException as error:
            hint = " (often the free-tier limit: wait a minute)" if "500" in str(error) else ""
            print(f"Turn {number} FAIL: request error: {error}{hint}\n")
            break
        problems = check(turn, got)
        passed += not problems
        print(f"Turn {number} [{turn['speaker']}] {'PASS' if not problems else 'FAIL'}  ({time.time() - start:.1f}s)")
        print(f"  {turn['speaker']:>12}: {turn['text']}")
        for to, text in got["said"]:
            print(f"  COSMO → {to:>12}: {text}")
        for problem in problems:
            print(f"  !! {problem}")
        print()

    print(f"=== {passed}/{len(TURNS)} turns passed ===")
    sys.exit(0 if passed == len(TURNS) else 1)


if __name__ == "__main__":
    main()
