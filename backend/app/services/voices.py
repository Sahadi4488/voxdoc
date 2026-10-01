"""Voice presets and input validation.

Pure data + validation only: this module must NOT import kokoro or torch, so it
imports in milliseconds and can be used by routers and tests without loading
the TTS model.
"""
from dataclasses import asdict, dataclass

MIN_SPEED = 0.5
MAX_SPEED = 2.0

# Kokoro voice ids start with <lang><gender>_ : a = American, b = British.
_LANG_CODES = {"a": "a", "b": "b"}


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    voice: str
    accent: str
    default_speed: float
    description: str


_PRESET_LIST = [
    Preset("narrator", "Narrator", "af_heart", "American", 1.0,
           "Warm, clear female voice. The default for most documents."),
    Preset("storyteller", "Storyteller", "af_bella", "American", 0.95,
           "Expressive female voice for long-form reading."),
    Preset("calm", "Calm", "af_nicole", "American", 0.9,
           "Soft, relaxed female voice for easy listening."),
    Preset("professional", "Professional", "am_michael", "American", 1.0,
           "Steady male voice for reports and papers."),
    Preset("energetic", "Energetic", "am_fenrir", "American", 1.1,
           "Brighter male voice at a slightly faster pace."),
    Preset("british_female", "British (F)", "bf_emma", "British", 1.0,
           "Clear British female voice."),
    Preset("british_male", "British (M)", "bm_george", "British", 1.0,
           "Measured British male voice."),
]

PRESETS: dict[str, Preset] = {p.id: p for p in _PRESET_LIST}


def get_preset(preset_id: str) -> Preset:
    try:
        return PRESETS[preset_id]
    except KeyError:
        raise ValueError(
            f"Unknown preset {preset_id!r}. Valid presets: {', '.join(PRESETS)}"
        ) from None


def lang_code_for(voice: str) -> str:
    """Return the Kokoro pipeline lang_code ('a' or 'b') for a voice id."""
    if not voice:
        raise ValueError("Voice id is empty.")
    code = voice[0].lower()
    if code not in _LANG_CODES:
        raise ValueError(
            f"Unsupported voice {voice!r}: id must start with 'a' (American) or 'b' (British)."
        )
    return _LANG_CODES[code]


def validate_speed(speed: float) -> float:
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        raise ValueError(f"Speed must be a number, got {speed!r}.") from None
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"Speed must be between {MIN_SPEED} and {MAX_SPEED}, got {speed}.")
    return speed


def list_presets() -> list[dict]:
    """JSON-ready presets for GET /voices."""
    return [asdict(p) for p in PRESETS.values()]
