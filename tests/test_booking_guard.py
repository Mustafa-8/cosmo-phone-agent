"""Offline tests for the Python-enforced booking order. Run from the repo root:

    python -m tests.test_booking_guard
"""

from phone_agent.tools.calendar_event import BOOKED_KEY, _booking_guard, create_calendar_event
from phone_agent.tools.slots import ACCEPTED_SLOT_KEY, check_slot


class FakeToolContext:
    """Just the two attributes the tools use: a session state dict and the turn id."""

    def __init__(self, state: dict, invocation_id: str):
        self.state = state
        self.invocation_id = invocation_id


ACCEPTED = {"clinic_id": "buda-smile-xi", "slot_start": "2026-11-24T15:00", "invocation_id": "turn-2"}


def test_no_accepted_slot_is_refused():
    r = _booking_guard({}, "turn-3", "buda-smile-xi", "2026-11-24T15:00")
    assert r["status"] == "error" and "check_slot" in r["error_message"], r


def test_same_turn_as_acceptance_is_refused():
    r = _booking_guard({ACCEPTED_SLOT_KEY: ACCEPTED}, "turn-2", "buda-smile-xi", "2026-11-24T15:00")
    assert r["status"] == "error" and "not confirmed yet" in r["error_message"], r


def test_later_turn_is_allowed():
    assert _booking_guard({ACCEPTED_SLOT_KEY: ACCEPTED}, "turn-3", "buda-smile-xi", "2026-11-24T15:00") == {"status": "ok"}


def test_different_slot_is_refused():
    r = _booking_guard({ACCEPTED_SLOT_KEY: ACCEPTED}, "turn-3", "buda-smile-xi", "2026-11-25T15:00")
    assert r["status"] == "error" and "book exactly that slot" in r["error_message"], r


def test_second_booking_is_refused():
    state = {ACCEPTED_SLOT_KEY: ACCEPTED, BOOKED_KEY: {"clinic_id": "buda-smile-xi"}}
    r = _booking_guard(state, "turn-4", "buda-smile-xi", "2026-11-24T15:00")
    assert r["status"] == "error" and "already booked" in r["error_message"], r


def test_check_slot_records_only_fitting_slots():
    state = {}
    # A Saturday never fits any window, so nothing is recorded.
    check_slot("buda-smile-xi", "2030-01-05T15:00", "next_week", "afternoon", FakeToolContext(state, "t1"))
    assert ACCEPTED_SLOT_KEY not in state


def test_tool_refuses_same_turn_without_writing_a_file():
    ctx = FakeToolContext({ACCEPTED_SLOT_KEY: ACCEPTED}, "turn-2")
    r = create_calendar_event("buda-smile-xi", "2026-11-24T15:00", 30, "Alex Morgan", "", ctx)
    assert r["status"] == "error" and "file" not in r, r
    assert BOOKED_KEY not in ctx.state


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
