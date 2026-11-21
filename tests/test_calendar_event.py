"""Offline tests for phone_agent/tools/calendar_event.py. Run from the repo root:

    python -m tests.test_calendar_event
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from phone_agent.tools.calendar_event import _create, _escape, _fold

NOW = datetime(2026, 11, 21, 13, 0, tzinfo=timezone.utc)


def make(**overrides):
    args = dict(clinic_id="buda-smile-xi", slot_start="2026-11-24T15:00", duration_min=30,
                patient_name="Mustafa Albusultan", notes="Bring your TAJ card")
    args.update(overrides)
    out_dir = Path(tempfile.mkdtemp())
    return _create(**args, out_dir=out_dir, now=NOW), out_dir


def test_ics_file_is_written_with_utc_times():
    r, out_dir = make()
    assert r["status"] == "ok", r
    path = Path(r["file"])
    assert path.parent == out_dir and path.name == "20261124-1500-buda-smile-xi-mustafa-albusultan.ics"
    ics = path.read_bytes().decode("utf-8")  # raw bytes: read_text() would turn \r\n into \n
    assert ics == r["ics"]
    assert "\r\n" in ics and "\n" not in ics.replace("\r\n", "")
    # 15:00 Budapest (UTC+1 in November) = 14:00 UTC
    assert "DTSTART:20261124T140000Z" in ics and "DTEND:20261124T143000Z" in ics
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "LOCATION:1117 Budapest\\, Bartók Béla út 45." in ics


def test_summary_has_long_date():
    r, _ = make()
    assert r["summary"]["date_long"] == "Tuesday 24 November 2026"
    assert r["summary"]["time"] == "15:00-15:30"
    assert r["summary"]["clinic"] == "Buda Smile Dental"


def test_summer_time_uses_utc_plus_2():
    r, _ = make(slot_start="2027-06-15T10:00")
    assert "DTSTART:20270615T080000Z" in r["ics"]


def test_invalid_inputs_are_errors():
    assert make(slot_start="Tuesday 3pm")[0]["status"] == "error"
    assert make(duration_min=5)[0]["status"] == "error"
    assert make(patient_name="  ")[0]["status"] == "error"
    assert make(clinic_id="nope")[0]["status"] == "error"


def test_escape_and_fold():
    assert _escape("a,b;c\nd") == "a\\,b\\;c\\nd"
    folded = _fold("DESCRIPTION:" + "x" * 100)
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert folded.split("\r\n")[1].startswith(" ")


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
