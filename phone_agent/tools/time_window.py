"""Time window tool: Python turns 'next week, afternoon' into real dates, the model never guesses dates."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Budapest")
WHEN_OPTIONS = ("today", "tomorrow", "this_week", "next_week")
PART_OF_DAY_HOURS = {
    "morning": ("08:00", "12:00"),
    "afternoon": ("12:00", "17:00"),
    "evening": ("17:00", "20:00"),
    "any": ("08:00", "20:00"),
}


def _days_for(when: str, today: date) -> list:
    """Return the candidate dates for `when`, counted from `today`."""
    if when == "today":
        return [today]
    if when == "tomorrow":
        return [today + timedelta(days=1)]
    if when == "this_week":  # from tomorrow until Sunday of the current week
        return [today + timedelta(days=i) for i in range(1, 7 - today.weekday())]
    # next_week: Monday to Sunday of the following week
    next_monday = today + timedelta(days=7 - today.weekday())
    return [next_monday + timedelta(days=i) for i in range(7)]


def _resolve(when: str, part_of_day: str, today: date) -> dict:
    """Pure calculation behind resolve_time_window, with `today` injected for tests."""
    when = when.strip().lower()
    part = part_of_day.strip().lower()
    if when not in WHEN_OPTIONS:
        return {"status": "error", "error_message": f"Unknown when {when!r}. Use one of {WHEN_OPTIONS}."}
    if part not in PART_OF_DAY_HOURS:
        return {"status": "error",
                "error_message": f"Unknown part_of_day {part!r}. Use one of {tuple(PART_OF_DAY_HOURS)}."}

    start_hm, end_hm = PART_OF_DAY_HOURS[part]
    windows = []
    for d in _days_for(when, today):
        if d.weekday() >= 5:  # clinics are closed on Saturday and Sunday
            continue
        windows.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "start": f"{d.isoformat()}T{start_hm}",
            "end": f"{d.isoformat()}T{end_hm}",
        })

    if not windows:
        return {"status": "ok", "windows": [],
                "note": f"No working days for {when!r} (clinics are closed on weekends). "
                        "Ask the patient for another time."}
    return {
        "status": "ok",
        "today": today.isoformat(),
        "windows": windows,
        "note": f"{when} {part}: {windows[0]['weekday']} {windows[0]['date']} to "
                f"{windows[-1]['weekday']} {windows[-1]['date']}, {start_hm}-{end_hm} (Budapest time).",
    }


def resolve_time_window(when: str, part_of_day: str) -> dict:
    """Turn the patient's time wish into concrete dates and hours in Budapest.

    Call this as soon as the patient says when they want the appointment, and
    use ONLY the returned dates. Never calculate dates yourself.

    Args:
        when: Exactly one of "today", "tomorrow", "this_week" (the rest of the
            current week) or "next_week" (Monday to Friday of the following
            week).
        part_of_day: Exactly one of "morning" (08:00-12:00), "afternoon"
            (12:00-17:00), "evening" (17:00-20:00) or "any" if the patient has
            no preference.

    Returns:
        {"status": "ok", "today": "YYYY-MM-DD", "windows": [...], "note": "..."}
        where each window has date, weekday, start and end ("YYYY-MM-DDTHH:MM",
        Budapest time). Weekends are skipped. If "windows" is empty, ask the
        patient for another time.
        {"status": "error", "error_message": "..."} for an unknown value.
    """
    return _resolve(when, part_of_day, datetime.now(TIMEZONE).date())
