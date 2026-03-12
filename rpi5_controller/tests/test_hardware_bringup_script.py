from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_hardware_bringup_script_mock_mode() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "hardware_bringup_check.py"
    config = repo_root / "configs" / "example_session.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--config",
            str(config),
            "--mock-hardware",
            "--yes",
            "--skip-lick",
            "--line-test-pulse-ms",
            "1",
            "--audio-test-seconds",
            "0.01",
        ],
        check=False,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "Summary" in completed.stdout
