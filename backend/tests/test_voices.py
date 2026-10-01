import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.voices import PRESETS, get_preset, lang_code_for, list_presets, validate_speed


def test_no_heavy_imports():
    # Fresh interpreter: other tests (spaCy in the splitter) import torch into this one
    code = "import sys, app.services.voices; print('kokoro' in sys.modules or 'torch' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=Path(__file__).resolve().parents[1], check=True).stdout
    assert out.strip() == "False"


def test_seven_presets_json_ready():
    presets = list_presets()
    assert len(presets) == 7
    assert all(isinstance(p, dict) and p["id"] in PRESETS for p in presets)


def test_presets_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PRESETS["narrator"].voice = "am_michael"


def test_get_preset():
    assert get_preset("narrator").voice == "af_heart"
    with pytest.raises(ValueError, match="Valid presets"):
        get_preset("nope")


@pytest.mark.parametrize("voice,code", [("af_heart", "a"), ("bm_george", "b")])
def test_lang_code_for(voice, code):
    assert lang_code_for(voice) == code


@pytest.mark.parametrize("voice", ["", "zf_xiaobei", "jf_alpha"])
def test_lang_code_for_rejects(voice):
    with pytest.raises(ValueError):
        lang_code_for(voice)


@pytest.mark.parametrize("speed", [0.5, 1, 2.0])
def test_validate_speed_ok(speed):
    assert validate_speed(speed) == speed


@pytest.mark.parametrize("speed", [0.49, 2.01, float("nan"), "fast", None])
def test_validate_speed_rejects(speed):
    with pytest.raises(ValueError):
        validate_speed(speed)
