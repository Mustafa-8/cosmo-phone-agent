"""Languages offered in the UI. Scribe and Flash v2.5 both cover many more; add entries as needed."""

LANGUAGES = {
    "en": "English",
    "hu": "Hungarian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "ro": "Romanian",
    "uk": "Ukrainian",
    "ar": "Arabic",
    "zh": "Chinese",
}


def name_of(code: str) -> str:
    return LANGUAGES.get(code, code)


# Scribe may report ISO 639-3 codes; the rest of the app uses ISO 639-1.
_THREE_TO_TWO = {
    "eng": "en", "hun": "hu", "deu": "de", "ger": "de", "fra": "fr", "fre": "fr", "spa": "es",
    "ita": "it", "ron": "ro", "rum": "ro", "ukr": "uk", "ara": "ar", "zho": "zh", "chi": "zh", "cmn": "zh",
}


def normalize(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip().lower().replace("_", "-").split("-")[0]
    code = _THREE_TO_TWO.get(code, code)
    return code if len(code) == 2 else None
