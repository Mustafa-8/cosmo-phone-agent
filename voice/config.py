"""Voice layer settings, read from the repo-root .env (see .env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


@dataclass
class Settings:
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    # The agent uses GOOGLE_API_KEY; GEMINI_API_KEY is accepted too.
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    )

    # "auto" means: real if the key exists, mock otherwise. Force with "real" / "mock".
    stt_mode: str = field(default_factory=lambda: os.getenv("STT_MODE", "auto"))
    translate_mode: str = field(default_factory=lambda: os.getenv("TRANSLATE_MODE", "auto"))
    tts_mode: str = field(default_factory=lambda: os.getenv("TTS_MODE", "auto"))

    # ElevenLabs realtime speech-to-text (Scribe)
    stt_model_id: str = field(default_factory=lambda: os.getenv("STT_MODEL_ID", "scribe_v3_live"))
    stt_base_url: str = field(default_factory=lambda: os.getenv("STT_BASE_URL", "wss://api.elevenlabs.io"))
    stt_commit_strategy: str = field(default_factory=lambda: os.getenv("STT_COMMIT_STRATEGY", "vad"))
    stt_vad_silence_secs: float = field(default_factory=lambda: _float("STT_VAD_SILENCE_SECS", 0.9))
    stt_keyterms: str = field(default_factory=lambda: os.getenv("STT_KEYTERMS", ""))

    # ElevenLabs text-to-speech
    tts_model_id: str = field(default_factory=lambda: os.getenv("TTS_MODEL_ID", "eleven_flash_v2_5"))
    tts_base_url: str = field(default_factory=lambda: os.getenv("TTS_BASE_URL", "https://api.elevenlabs.io"))
    tts_output_format: str = field(default_factory=lambda: os.getenv("TTS_OUTPUT_FORMAT", "mp3_44100_128"))
    tts_send_language_code: bool = field(default_factory=lambda: _bool("TTS_SEND_LANGUAGE_CODE", True))
    voice_id_en: str = field(default_factory=lambda: os.getenv("VOICE_ID_EN", "JBFqnCBsd6RMkjVDRZzb"))
    voice_id_hu: str = field(default_factory=lambda: os.getenv("VOICE_ID_HU", "21m00Tcm4TlvDq8ikWAM"))
    voice_id_default: str = field(default_factory=lambda: os.getenv("VOICE_ID_DEFAULT", "JBFqnCBsd6RMkjVDRZzb"))

    # Gemini translation. gemini-2.5-flash is closed to new users; flash-lite answers in about 1 s.
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    gemini_base_url: str = field(
        default_factory=lambda: os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    )

    def resolved(self, mode: str, key: str) -> str:
        if mode in ("real", "mock"):
            return mode
        return "real" if key else "mock"

    @property
    def stt_effective(self) -> str:
        return self.resolved(self.stt_mode, self.elevenlabs_api_key)

    @property
    def translate_effective(self) -> str:
        return self.resolved(self.translate_mode, self.gemini_api_key)

    @property
    def tts_effective(self) -> str:
        return self.resolved(self.tts_mode, self.elevenlabs_api_key)

    def voice_for(self, lang: str) -> str:
        override = os.getenv(f"VOICE_ID_{lang.upper()}")
        if override:
            return override
        return {"en": self.voice_id_en, "hu": self.voice_id_hu}.get(lang, self.voice_id_default)


settings = Settings()
