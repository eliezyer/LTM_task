from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_play_context_audio_script_mock_mode() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "play_context_audio.py"
    config = repo_root / "configs" / "example_session.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "2",
            "--config",
            str(config),
            "--mock-hardware",
            "--seconds",
            "0.01",
        ],
        check=False,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "Playing context 2 on WAV channel 3" in completed.stdout
    assert "Audio trigger finished." in completed.stdout


def test_play_trial_available_audio_script_mock_mode() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "play_context_audio.py"
    config = repo_root / "configs" / "example_session.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--trial-available",
            "--config",
            str(config),
            "--mock-hardware",
            "--seconds",
            "0.01",
        ],
        check=False,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "Playing trial-available on WAV channel 1" in completed.stdout
    assert "Audio trigger finished." in completed.stdout
