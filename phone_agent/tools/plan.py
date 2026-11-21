"""Plan tool: Python picks the clinic, the doctor and one concrete free slot, so the
receptionist only has to confirm. The model never invents a clinic, doctor, date or time."""

from datetime import date, datetime, timedelta

from google.adk.tools import ToolContext

from .clinics import find_clinics
from .slots import ACCEPTED_SLOT_KEY, WEEKDAY_KEYS
from .time_window import TIMEZONE, _resolve

APPOINTMENT_MIN = 30


def _first_slot(clinic: dict, windows: list) -> dict | None:
    """First half-hour start inside both the patient's window and the clinic's opening hours."""
    for w in windows:
        day = date.fromisoformat(w["date"])
        hours = clinic["opening_hours"].get(WEEKDAY_KEYS[day.weekday()])
        if not hours:
            continue
        open_at, close_at = hours.split("-")
        start = max(w["start"][-5:], open_at)
        end = min(w["end"][-5:], close_at)
        t = datetime.strptime(f"{w['date']} {start}", "%Y-%m-%d %H:%M")
        if t.minute not in (0, 30):  # round up to the next half hour
            t += timedelta(minutes=30 - t.minute % 30)
        if (t + timedelta(minutes=APPOINTMENT_MIN)).strftime("%H:%M") <= end:
            doctors = clinic.get("doctors") or []
            return {
                "slot_start": t.strftime("%Y-%m-%dT%H:%M"),
                "date": w["date"],
                "weekday": t.strftime("%A"),
                "time": t.strftime("%H:%M"),
                "duration_min": APPOINTMENT_MIN,
                "doctor": doctors[day.toordinal() % len(doctors)] if doctors else "",
            }
    return None


def _plan(specialty: str, district: str, when: str, part_of_day: str, today: date) -> dict:
    """Pure calculation behind plan_appointment, with `today` injected for tests."""
    found = find_clinics(specialty, district)
    if found.get("status") != "ok" or not found.get("clinics"):
        return found if found.get("status") != "ok" else {
            "status": "error", "error_message": f"No clinic found for {specialty!r}. Ask the patient."}
    windows = _resolve(when, part_of_day, today)
    if windows["status"] != "ok":
        return windows
    if not windows["windows"]:
        return {"status": "error", "error_message": "No days left in that time window. Ask the patient for another time."}
    for clinic in found["clinics"]:
        slot = _first_slot(clinic, windows["windows"])
        if slot:
            return {"status": "ok",
                    "clinic": {k: clinic[k] for k in ("id", "name", "address", "phone")},
                    "proposed_slot": slot, "windows": windows["windows"],
                    "when": when, "part_of_day": part_of_day}
    return {"status": "error",
            "error_message": "No clinic is open in the patient's time window. Ask the patient for another time."}


def plan_appointment(specialty: str, district: str, when: str, part_of_day: str,
                     tool_context: ToolContext) -> dict:
    """Find the clinic, the doctor and one concrete free slot for the patient's request.

    Call this ONCE, first, when the patient asks for an appointment (instead of
    find_clinics and resolve_time_window). Then propose exactly this slot and
    doctor to the receptionist so they only need to confirm.

    Args:
        specialty: One of "dentist", "general_practitioner", "dermatologist".
        district: Budapest district if the patient gave one (e.g. "XI"), else "".
        when: One of "today", "tomorrow", "this_week", "next_week".
        part_of_day: One of "morning", "afternoon", "evening", "any".

    Returns:
        {"status": "ok", "clinic": {id, name, address, phone},
         "proposed_slot": {slot_start, date, weekday, time, duration_min, doctor},
         "windows": [...], "when": ..., "part_of_day": ...}
        or {"status": "error", "error_message": "..."}: then ask the patient.
    """
    result = _plan(specialty, district, when, part_of_day, datetime.now(TIMEZONE).date())
    if result.get("status") == "ok":
        # The proposed slot counts as accepted on our side; create_calendar_event still refuses
        # to book it until the receptionist confirms in a later turn.
        tool_context.state[ACCEPTED_SLOT_KEY] = {
            "clinic_id": result["clinic"]["id"],
            "slot_start": result["proposed_slot"]["slot_start"],
            "invocation_id": tool_context.invocation_id,
        }
    return result
