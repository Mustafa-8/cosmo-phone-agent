"""Translation and call summaries with the Gemini API (REST generateContent, JSON output)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from .config import settings
from .languages import name_of, normalize
from .safety import detect_urgent

log = logging.getLogger("caller_ai.translation")

INTERPRETER_PROMPT = """You are Caller AI, a medical phone interpreter between a patient and hospital staff.
You receive one utterance spoken by the {speaker} in {source}. Translate it into {target} for the {listener}.

Rules:
- Translate faithfully. Never add, remove, soften or "improve" content. Never answer the question yourself.
- Never give medical advice, a diagnosis, or an opinion, even if asked. You only translate.
- Keep medication names, doses, units, numbers, dates, times, names and ID numbers exactly as spoken.
- Keep the speaker's register: polite forms stay polite (in Hungarian use the formal "Ön/maga" form toward patients).
- If the utterance is unclear, cut off, ambiguous, or a critical detail (drug name, dose, number, allergy,
  body part, time) cannot be translated with confidence, still give your best translation but set
  needs_clarification=true and explain why in clarification_reason (in English, one short sentence).
- Set detected_language to the ISO 639-1 code of the language the utterance is actually in.
- Set urgent=true only if the speaker describes a possible emergency (e.g. chest pain, trouble breathing,
  heavy bleeding, stroke signs, loss of consciousness, suicidal thoughts, severe allergic reaction).

Recent conversation for context (may be empty):
{context}
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "translated_text": {"type": "STRING"},
        "needs_clarification": {"type": "BOOLEAN"},
        "clarification_reason": {"type": "STRING"},
        "urgent": {"type": "BOOLEAN"},
        "detected_language": {"type": "STRING"},
    },
    "required": ["translated_text", "needs_clarification", "urgent", "detected_language"],
}

SUMMARY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary_patient_language": {"type": "STRING"},
        "summary_hospital_language": {"type": "STRING"},
        "follow_up_actions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "flags": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary_patient_language", "summary_hospital_language", "follow_up_actions", "flags"],
}


@dataclass
class TranslationResult:
    translated_text: str
    needs_clarification: bool = False
    clarification_reason: str = ""
    urgent: bool = False
    detected_language: str | None = None


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20)
    return _client


async def _gemini_json(system: str, user: str, schema: dict) -> dict:
    url = f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    r = await _http().post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key})
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


MOCK_PHRASES = {
    ("en", "hu"): {
        "Hello, I have had a bad headache since yesterday and I need an appointment.":
            "Jó napot! Tegnap óta erősen fáj a fejem, és időpontra lenne szükségem.",
        "It started yesterday morning. I took two paracetamol, 500 milligrams each.":
            "Tegnap reggel kezdődött. Bevettem két paracetamolt, egyenként 500 milligrammosat.",
        "Yes, tomorrow at 10 o'clock works for me. Thank you.":
            "Igen, a holnapi 10 óra megfelel. Köszönöm.",
    },
    ("hu", "en"): {
        "Jó napot kívánok! Mióta fáj a feje?": "Good afternoon! How long have you had the headache?",
        "Rendben. Holnap délelőtt 10 órakor tudok időpontot adni Dr. Kovácshoz.":
            "All right. I can give you an appointment with Dr. Kovács tomorrow at 10 a.m.",
        "Kérem, hozza magával a TAJ-kártyáját és a gyógyszerei listáját.":
            "Please bring your social security (TAJ) card and the list of your medications.",
    },
}


def _guess_language(text: str) -> str:
    hu_marks = set("őűŐŰ") | set("áéíóöúüÁÉÍÓÖÚÜ")
    hu_words = {"és", "nem", "igen", "kérem", "fáj", "jó", "napot", "orvos", "időpont", "köszönöm"}
    words = {w.strip(".,!?").lower() for w in text.split()}
    return "hu" if (set(text) & hu_marks or words & hu_words) else "en"


def _mock_translate(text: str, source: str, target: str) -> TranslationResult:
    if source == "auto":
        source = _guess_language(text)
    hit = MOCK_PHRASES.get((source, target), {}).get(text)
    translated = hit or f"[{target.upper()}] {text}"
    unclear = len(text.split()) <= 1 and not hit
    return TranslationResult(
        translated_text=translated,
        needs_clarification=unclear,
        clarification_reason="Very short utterance, please confirm." if unclear else "",
        urgent=detect_urgent(text),
        detected_language=source,
    )


async def translate(text: str, source: str, target: str, speaker: str, context: list[str]) -> TranslationResult:
    if settings.translate_effective == "mock":
        return _mock_translate(text, source, target)
    listener = "hospital staff member" if speaker == "patient" else "patient"
    system = INTERPRETER_PROMPT.format(
        speaker="patient" if speaker == "patient" else "hospital staff member",
        listener=listener,
        source="an unknown language (detect it)" if source == "auto" else name_of(source),
        target=name_of(target),
        context="\n".join(context[-6:]) or "(none)",
    )
    try:
        data = await _gemini_json(system, text, SCHEMA)
        return TranslationResult(
            translated_text=(data.get("translated_text") or "").strip(),
            needs_clarification=bool(data.get("needs_clarification")),
            clarification_reason=data.get("clarification_reason") or "",
            urgent=bool(data.get("urgent")) or detect_urgent(text),
            detected_language=normalize(data.get("detected_language")),
        )
    except Exception as exc:
        log.exception("Gemini translation failed")
        # Never pass silent garbage to the listener: flag it so a human repeats or escalates.
        return TranslationResult(
            translated_text="",
            needs_clarification=True,
            clarification_reason=f"Translation service error: {exc.__class__.__name__}",
            urgent=detect_urgent(text),
        )


SUMMARY_PROMPT = """Summarise this interpreted phone call between a patient and hospital staff for authorised staff.
Write one short summary in {pl} and the same summary in {hl}. Only state what was actually said.
Do not add medical advice. List concrete follow-up actions (appointments, documents to bring, callbacks)
and flags (urgent symptoms, unresolved clarifications, allergies, medications mentioned)."""


async def summarise(turns: list[dict], patient_lang: str, hospital_lang: str) -> dict:
    lines = [f"{t['speaker'].upper()} ({t['source_language']}): {t['original_text']}"
             f" || {t['target_language']}: {t['translated_text']}" for t in turns]
    if not lines:
        return {"summary_patient_language": "", "summary_hospital_language": "",
                "follow_up_actions": [], "flags": []}
    if settings.translate_effective == "mock":
        urgent = any(t.get("urgent") for t in turns)
        return {
            "summary_patient_language": f"(mock) Call with {len(turns)} interpreted turns.",
            "summary_hospital_language": f"(mock) {len(turns)} tolmácsolt megszólalás.",
            "follow_up_actions": ["Appointment: tomorrow 10:00 with Dr. Kovács (demo)"],
            "flags": ["Possible emergency mentioned"] if urgent else [],
        }
    system = SUMMARY_PROMPT.format(pl=name_of(patient_lang), hl=name_of(hospital_lang))
    try:
        return await _gemini_json(system, "\n".join(lines), SUMMARY_SCHEMA)
    except Exception as exc:
        log.exception("Gemini summary failed")
        return {"summary_patient_language": "", "summary_hospital_language": "",
                "follow_up_actions": [], "flags": [f"Summary failed: {exc.__class__.__name__}"]}
