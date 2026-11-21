"""Clinic search tool: Python filters the mock clinic list, the model never invents a clinic."""

import json
from pathlib import Path

CLINICS_FILE = Path(__file__).resolve().parent.parent / "data" / "clinics.json"
SPECIALTIES = ("dentist", "general_practitioner", "dermatologist")
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
         "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII"]


def _normalize_district(district: str) -> str:
    """Turn '6', '6th', 'vi', 'VI.' into 'VI'. Returns '' if empty or unknown."""
    d = district.strip().upper().rstrip(".").removesuffix("TH").removesuffix("ST") \
        .removesuffix("ND").removesuffix("RD").strip()
    if d.isdigit() and 1 <= int(d) <= len(ROMAN):
        return ROMAN[int(d) - 1]
    return d if d in ROMAN else ""


def find_clinics(specialty: str, district: str = "") -> dict:
    """Find clinics in Budapest for one medical specialty.

    Call this BEFORE calling any clinic, and only call a clinic returned here.
    Never invent a clinic, address or phone number.

    Args:
        specialty: Exactly one of "dentist", "general_practitioner" (family
            doctor / GP) or "dermatologist" (skin doctor). Map the patient's
            words to one of these.
        district: Optional Budapest district the patient prefers, as a Roman
            or Arabic number (e.g. "VI" or "6"). Use "" if the patient did
            not say.

    Returns:
        {"status": "ok", "clinics": [...], "note": "..."} where each clinic has
        id, name, specialty, district, address, phone and opening_hours.
        If no clinic matches the district, clinics from other districts are
        returned and "note" says so.
        {"status": "error", "error_message": "..."} if the specialty is unknown
        or the clinic data cannot be read.
    """
    spec = specialty.strip().lower()
    if spec not in SPECIALTIES:
        return {"status": "error",
                "error_message": f"Unknown specialty {specialty!r}. Use one of {SPECIALTIES}."}
    try:
        clinics = json.loads(CLINICS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "error_message": f"Could not read clinic data: {exc}"}

    matches = [c for c in clinics if c["specialty"] == spec]
    if not matches:
        return {"status": "ok", "clinics": [], "note": f"No {spec} clinic in our list."}

    wanted = _normalize_district(district) if district else ""
    if wanted:
        in_district = [c for c in matches if c["district"] == wanted]
        if in_district:
            return {"status": "ok", "clinics": in_district, "note": f"Clinics in district {wanted}."}
        return {"status": "ok", "clinics": matches,
                "note": f"No {spec} in district {wanted}; showing other districts."}
    return {"status": "ok", "clinics": matches, "note": "All districts."}
