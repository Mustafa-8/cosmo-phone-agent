"""Cheap keyword safety net that runs even when Gemini is down or mocked.

Gemini also returns an `urgent` flag; either one marks the turn as urgent.
This is a demo heuristic, not a clinical triage tool.
"""
import re

URGENT_PATTERNS = [
    # English
    r"chest pain", r"can'?t breathe", r"cannot breathe", r"short(ness)? of breath", r"heart attack",
    r"stroke", r"unconscious", r"passed out", r"heavy bleeding", r"bleeding a lot", r"seizure",
    r"suicid", r"kill myself", r"overdose", r"anaphyla", r"throat (is )?swelling",
    # Hungarian
    r"mellkas\w* fáj", r"mellkasi fájdalom", r"nem kapok levegőt", r"fulladok", r"infarktus", r"stroke",
    r"eszméletlen", r"elájult", r"erős vérzés", r"vérzik", r"görcsroham", r"öngyilkos", r"túladagol",
]
_RX = re.compile("|".join(URGENT_PATTERNS), re.IGNORECASE)


def detect_urgent(text: str) -> bool:
    return bool(_RX.search(text or ""))
