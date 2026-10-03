"""Voice presets and input validation.

Pure data + validation only: this module must NOT import kokoro or torch, so it
imports in milliseconds and can be used by routers and tests without loading
the TTS model.
"""
from dataclasses import asdict, dataclass

KOKORO_REPO = "hexgrad/Kokoro-82M"  # the model and voice files on Hugging Face

MIN_SPEED = 0.5
MAX_SPEED = 2.0

# Kokoro voice ids start with <lang><gender>_ : a = American, b = British.
_LANG_CODES = {"a": "a", "b": "b"}


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    voice: str  # Kokoro voice id; never sent by the frontend, which only knows preset ids
    accent: str  # "US" | "UK"
    gender: str  # "female" | "male"
    default_speed: float
    use: str  # what it suits, shown in the voice picker
    description: str


_PRESET_LIST = [
    Preset("narrator", "Narrator", "af_heart", "US", "female", 1.0, "Everyday reading",
           "Warm, clear voice. The default for most documents."),
    Preset("storyteller", "Storyteller", "af_bella", "US", "female", 0.95, "Novels and stories",
           "Expressive voice for long-form reading."),
    Preset("calm", "Calm", "af_nicole", "US", "female", 0.85, "Dense or technical text",
           "Soft, relaxed voice at an unhurried pace."),
    Preset("presenter", "Presenter", "am_michael", "US", "male", 1.0, "Reports and articles",
           "Steady, neutral voice."),
    Preset("energetic", "Energetic", "am_fenrir", "US", "male", 1.1, "Skimming at speed",
           "Brighter voice at a slightly faster pace."),
    Preset("british_female", "Emma", "bf_emma", "UK", "female", 1.0, "Fiction and essays",
           "Clear British voice."),
    Preset("scholar", "Scholar", "bm_george", "UK", "male", 1.0, "Academic papers",
           "Measured British voice."),
]

DEFAULT_PRESET_ID = "presenter"

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
    """JSON-ready presets for GET /voices; is_default marks the fallback preset."""
    return [{**asdict(p), "is_default": p.id == DEFAULT_PRESET_ID} for p in PRESETS.values()]
