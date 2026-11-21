"""Offline tests for plan_appointment: Python picks clinic, doctor and one concrete slot."""
from datetime import date

from phone_agent.tools.calendar_event import _booking_guard
from phone_agent.tools.plan import _plan, plan_appointment
from phone_agent.tools.slots import ACCEPTED_SLOT_KEY

SATURDAY = date(2026, 11, 21)  # next week = Mon 23 .. Sun 29 November


class FakeToolContext:
    def __init__(self, state: dict, invocation_id: str):
        self.state = state
        self.invocation_id = invocation_id


def test_dentist_next_week_afternoon_gets_first_open_slot_with_doctor():
    r = _plan("dentist", "", "next_week", "afternoon", SATURDAY)
    assert r["status"] == "ok", r
    assert r["clinic"]["id"] == "dental-plus-vi"
    slot = r["proposed_slot"]
    assert slot["slot_start"] == "2026-11-23T12:00" and slot["weekday"] == "Monday"
    assert slot["doctor"] in ("Dr. Kovács Anna", "Dr. Szabó Péter")


def test_slot_respects_clinic_opening_hours():
    # Buda Smile opens at 10:00, so "morning" starts there, not at 08:00.
    r = _plan("dentist", "XI", "next_week", "morning", SATURDAY)
    assert r["clinic"]["id"] == "buda-smile-xi"
    assert r["proposed_slot"]["time"] == "10:00"


def test_skips_days_when_closed():
    # Pest Health is open only in the morning on Mon/Wed/Fri and afternoon on Tue/Thu.
    r = _plan("general_practitioner", "", "next_week", "afternoon", SATURDAY)
    assert r["proposed_slot"]["weekday"] == "Tuesday" and r["proposed_slot"]["time"] == "14:00"


def test_unknown_specialty_is_an_error():
    assert _plan("astronaut", "", "next_week", "any", SATURDAY)["status"] == "error"


def test_proposed_slot_is_booked_only_after_confirmation_turn():
    ctx = FakeToolContext({}, "turn-1")
    r = plan_appointment("dentist", "", "next_week", "afternoon", ctx)
    slot = r["proposed_slot"]["slot_start"]
    assert ctx.state[ACCEPTED_SLOT_KEY]["slot_start"] == slot
    # same turn: refused; next turn (receptionist confirmed): allowed
    assert _booking_guard(ctx.state, "turn-1", "dental-plus-vi", slot)["status"] == "error"
    assert _booking_guard(ctx.state, "turn-2", "dental-plus-vi", slot)["status"] == "ok"


def test_after_declined_slot_proposes_the_next_one():
    first = _plan("dentist", "", "next_week", "afternoon", SATURDAY)["proposed_slot"]["slot_start"]
    nxt = _plan("dentist", "", "next_week", "afternoon", SATURDAY, after_slot=first)["proposed_slot"]
    assert first == "2026-11-23T12:00" and nxt["slot_start"] == "2026-11-23T12:30"


def test_after_last_slot_of_day_moves_to_next_open_day():
    # Dental Plus closes at 18:00 but the afternoon window ends at 17:00, so 16:30 is Monday's last slot.
    nxt = _plan("dentist", "", "next_week", "afternoon", SATURDAY, after_slot="2026-11-23T16:30")["proposed_slot"]
    assert nxt["slot_start"] == "2026-11-24T12:00" and nxt["weekday"] == "Tuesday"
