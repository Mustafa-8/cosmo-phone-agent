"""Slot check tool: Python decides whether an offered appointment time is acceptable."""

from datetime import date, datetime

from .clinics import get_clinic
from .time_window import TIMEZONE, _resolve

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _check(clinic_id: str, slot_start: str, when: str, part_of_day: str, today: date) -> dict:
    """Pure calculation behind check_slot, with `today` injected for tests."""
    try:
        slot = datetime.strptime(slot_start.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return {"status": "error",
                "error_message": f"slot_start {slot_start!r} must look like 'YYYY-MM-DDTHH:MM', e.g. '2026-11-24T15:00'."}

    found = get_clinic(clinic_id)
    if found["status"] != "ok":
        return found
    clinic = found["clinic"]

    windows = _resolve(when, part_of_day, today)
    if windows["status"] != "ok":
        return windows

    slot_info = {"date": slot.date().isoformat(), "weekday": slot.strftime("%A"),
                 "time": slot.strftime("%H:%M")}

    window = next((w for w in windows["windows"] if w["date"] == slot_info["date"]), None)
    if window is None:
        return {"status": "ok", "fits": False, "slot": slot_info,
                "reason": f"{slot_info['weekday']} {slot_info['date']} is not one of the patient's days "
                          f"({windows.get('note', '')})."}
    window_start, window_end = window["start"][-5:], window["end"][-5:]
    if not (window_start <= slot_info["time"] < window_end):
        return {"status": "ok", "fits": False, "slot": slot_info,
                "reason": f"{slot_info['time']} is outside the patient's hours {window_start}-{window_end}."}

    hours = clinic["opening_hours"].get(WEEKDAY_KEYS[slot.weekday()])
    if not hours:
        return {"status": "ok", "fits": False, "slot": slot_info,
                "reason": f"{clinic['name']} is closed on {slot_info['weekday']}."}
    open_at, close_at = hours.split("-")
    if not (open_at <= slot_info["time"] < close_at):
        return {"status": "ok", "fits": False, "slot": slot_info,
                "reason": f"{clinic['name']} is open {open_at}-{close_at} on {slot_info['weekday']}."}

    return {"status": "ok", "fits": True, "slot": slot_info,
            "reason": "Inside the patient's window and the clinic's opening hours."}


def check_slot(clinic_id: str, slot_start: str, when: str, part_of_day: str) -> dict:
    """Check whether a time slot offered by the receptionist is acceptable.

    Call this EVERY time the receptionist offers a time, before you accept or
    decline it. Accept only if "fits" is true.

    Args:
        clinic_id: The id of the clinic you are calling, from find_clinics.
        slot_start: The offered start time as "YYYY-MM-DDTHH:MM" (24-hour,
            Budapest time). Take the date from the windows returned by
            resolve_time_window, e.g. "next Tuesday" -> the Tuesday window's date.
        when: The same "when" value you passed to resolve_time_window.
        part_of_day: The same "part_of_day" value you passed to
            resolve_time_window.

    Returns:
        {"status": "ok", "fits": true | false, "slot": {date, weekday, time},
         "reason": "..."}. If "fits" is false, politely decline and use
        "reason" to ask for a better time.
        {"status": "error", "error_message": "..."} for a bad slot format,
        unknown clinic, or unknown when/part_of_day.
    """
    return _check(clinic_id, slot_start, when, part_of_day, datetime.now(TIMEZONE).date())
