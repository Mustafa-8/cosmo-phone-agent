"""Offline tests for phone_agent/tools/slots.py. Run from the repo root:

    python -m tests.test_slots
"""

from datetime import date

from phone_agent.tools.clinics import get_clinic
from phone_agent.tools.slots import _check

SATURDAY = date(2026, 11, 21)  # next week = Mon 23 .. Fri 27 Nov 2026


def check(slot, clinic="buda-smile-xi", when="next_week", part="afternoon"):
    return _check(clinic, slot, when, part, SATURDAY)


def test_tuesday_afternoon_fits():
    r = check("2026-11-24T15:00")
    assert r["status"] == "ok" and r["fits"] is True, r
    assert r["slot"] == {"date": "2026-11-24", "weekday": "Tuesday", "time": "15:00"}


def test_saturday_does_not_fit():
    r = check("2026-11-28T10:00")
    assert r["fits"] is False and "not one of the patient's days" in r["reason"], r


def test_morning_does_not_fit_afternoon_window():
    r = check("2026-11-24T09:30")
    assert r["fits"] is False and "outside the patient's hours" in r["reason"], r


def test_window_end_is_exclusive():
    assert check("2026-11-24T17:00")["fits"] is False


def test_clinic_closed_at_that_time():
    # Dental Plus closes at 14:00 on Fridays; 15:00 is inside the patient's afternoon.
    r = check("2026-11-27T15:00", clinic="dental-plus-vi")
    assert r["fits"] is False and "open 08:00-14:00" in r["reason"], r


def test_bad_format_is_error():
    assert check("next tuesday 3pm")["status"] == "error"


def test_unknown_clinic_is_error():
    assert check("2026-11-24T15:00", clinic="nope")["status"] == "error"


def test_get_clinic():
    assert get_clinic("buda-smile-xi")["clinic"]["district"] == "XI"
    assert get_clinic("nope")["status"] == "error"


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
