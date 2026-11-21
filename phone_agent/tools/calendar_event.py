"""Calendar tool: Python writes the confirmed appointment as a standard .ics file."""

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .clinics import get_clinic
from .time_window import TIMEZONE

BOOKINGS_DIR = Path(__file__).resolve().parents[2] / "bookings"  # repo root; ignored by git


def _escape(text: str) -> str:
    """Escape text for an iCalendar value (RFC 5545 section 3.3.11)."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Fold lines longer than 75 bytes, as iCalendar requires (RFC 5545 section 3.1)."""
    out, current = [], ""
    for ch in line:
        if len((current + ch).encode("utf-8")) > 75:
            out.append(current)
            current = " " + ch
        else:
            current += ch
    out.append(current)
    return "\r\n".join(out)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _create(clinic_id: str, slot_start: str, duration_min: int, patient_name: str,
            notes: str, out_dir: Path, now: datetime) -> dict:
    """Pure-ish implementation behind create_calendar_event, with output folder and clock injected."""
    try:
        local_start = datetime.strptime(slot_start.strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=TIMEZONE)
    except ValueError:
        return {"status": "error",
                "error_message": f"slot_start {slot_start!r} must look like 'YYYY-MM-DDTHH:MM', e.g. '2026-11-24T15:00'."}
    if not 10 <= duration_min <= 180:
        return {"status": "error", "error_message": "duration_min must be between 10 and 180."}
    if not patient_name.strip():
        return {"status": "error", "error_message": "patient_name must not be empty."}

    found = get_clinic(clinic_id)
    if found["status"] != "ok":
        return found
    clinic = found["clinic"]
    local_end = local_start + timedelta(minutes=duration_min)

    description = f"Booked by COSMO for {patient_name.strip()}. Clinic phone: {clinic['phone']}."
    if notes.strip():
        description += f" Notes: {notes.strip()}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Team COSMO//Hungarian Phone Agent//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@cosmo-phone-agent",
        f"DTSTAMP:{_utc(now)}",
        f"DTSTART:{_utc(local_start)}",
        f"DTEND:{_utc(local_end)}",
        f"SUMMARY:{_escape(clinic['name'] + ' appointment')}",
        f"LOCATION:{_escape(clinic['address'])}",
        f"DESCRIPTION:{_escape(description)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    ics = "\r\n".join(_fold(line) for line in lines) + "\r\n"

    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", patient_name.strip()).strip("-").lower() or "patient"
    path = out_dir / f"{local_start:%Y%m%d-%H%M}-{clinic_id}-{safe_name}.ics"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(ics, encoding="utf-8", newline="")
    except OSError as exc:
        return {"status": "error", "error_message": f"Could not write the calendar file: {exc}"}

    return {
        "status": "ok",
        "file": str(path),
        "ics": ics,
        "summary": {
            "clinic": clinic["name"],
            "address": clinic["address"],
            "phone": clinic["phone"],
            "date_long": local_start.strftime("%A %-d %B %Y"),
            "time": f"{local_start:%H:%M}-{local_end:%H:%M}",
        },
    }


def create_calendar_event(clinic_id: str, slot_start: str, duration_min: int,
                          patient_name: str, notes: str = "") -> dict:
    """Add the confirmed appointment to the patient's calendar as an .ics file.

    Call this ONCE, only after `check_slot` returned fits=true AND the
    receptionist confirmed the booking. Then use the returned "summary" in
    your English message to the patient (copy date_long and time exactly).

    Args:
        clinic_id: The id of the clinic you called, from find_clinics.
        slot_start: The confirmed start as "YYYY-MM-DDTHH:MM" (Budapest time),
            the same value you passed to check_slot.
        duration_min: Appointment length in minutes (10-180). Use what the
            receptionist said, or 30 if they did not say.
        patient_name: The patient's full name, as the patient gave it.
        notes: Short English notes for the patient, e.g. "Bring your TAJ card".
            Use "" if there is nothing to add.

    Returns:
        {"status": "ok", "file": "...", "ics": "...", "summary": {clinic,
         address, phone, date_long, time}}.
        {"status": "error", "error_message": "..."} for a bad time format,
        duration, empty name, unknown clinic, or if the file cannot be written.
    """
    return _create(clinic_id, slot_start, duration_min, patient_name, notes,
                   BOOKINGS_DIR, datetime.now(timezone.utc))
