from __future__ import annotations

import wave
from pathlib import Path

from tools.generate_audio.generate_context_audio import Config, generate_audio_files


def test_generator_defaults_to_wav_trigger_sample_rate() -> None:
    assert Config().sample_rate == 44_100


def test_generator_writes_named_and_wav_trigger_outputs(tmp_path: Path) -> None:
    cfg = Config(out_dir=str(tmp_path), duration_s=0.01)

    written_paths = {Path(path).name for path in generate_audio_files(cfg)}

    assert {
        "carrier_plain.wav",
        "context_1_AM_0p5Hz.wav",
        "context_2_AM_1p0Hz.wav",
        "context_3_AM_2p0Hz.wav",
        "context_white_noise.wav",
        "001.wav",
        "002.wav",
        "003.wav",
        "004.wav",
        "README_generated.txt",
    } <= written_paths

    for filename in (
        "carrier_plain.wav",
        "context_1_AM_0p5Hz.wav",
        "context_2_AM_1p0Hz.wav",
        "context_3_AM_2p0Hz.wav",
        "001.wav",
        "002.wav",
        "003.wav",
        "004.wav",
    ):
        with wave.open(str(tmp_path / filename), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 44_100
            assert wf.getnframes() > 0
