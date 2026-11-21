"""Offline tests for phone_agent/tools/time_window.py. Run from the repo root:

    python -m tests.test_time_window
"""

from datetime import date

from phone_agent.tools.time_window import _resolve, resolve_time_window

SATURDAY = date(2026, 11, 21)
WEDNESDAY = date(2026, 11, 25)


def test_next_week_afternoon_from_saturday():
    r = _resolve("next_week", "afternoon", SATURDAY)
    assert r["status"] == "ok", r
    assert [w["date"] for w in r["windows"]] == [
        "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"]
    assert r["windows"][0] == {"date": "2026-11-23", "weekday": "Monday",
                               "start": "2026-11-23T12:00", "end": "2026-11-23T17:00"}


def test_next_week_from_wednesday_starts_next_monday():
    r = _resolve("next_week", "morning", WEDNESDAY)
    assert r["windows"][0]["date"] == "2026-11-30", r


def test_this_week_from_wednesday_is_thu_fri():
    r = _resolve("this_week", "any", WEDNESDAY)
    assert [w["weekday"] for w in r["windows"]] == ["Thursday", "Friday"], r


def test_tomorrow_on_saturday_is_closed():
    r = _resolve("tomorrow", "afternoon", SATURDAY)
    assert r["status"] == "ok" and r["windows"] == [], r
    assert "weekend" in r["note"]


def test_input_is_case_and_space_insensitive():
    assert _resolve(" Next_Week ", "AFTERNOON", SATURDAY)["status"] == "ok"


def test_unknown_values_are_errors():
    assert _resolve("someday", "afternoon", SATURDAY)["status"] == "error"
    assert _resolve("next_week", "night", SATURDAY)["status"] == "error"


def test_real_tool_runs_with_todays_date():
    assert resolve_time_window("next_week", "any")["status"] == "ok"


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
