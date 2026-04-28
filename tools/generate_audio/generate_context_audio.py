#!/usr/bin/env python3
"""
Generate AM audio stimuli for 3 contexts using only the Python standard library.

Why standard library only:
- The provided environment.yml lists Python plus a few utility/testing packages,
  but no numpy/scipy/audio DSP stack, so this script avoids external deps.

Outputs:
- 16-bit PCM mono WAV files
- one file per AM rate in AM mode
- optional plain carrier file
- optional unmodulated white-noise file matched in RMS level to the AM contexts
- optional WAV Trigger Pro track files (`001.wav`-`004.wav`)

Default use case:
- band-limited-ish carrier approximation via summed sine tones around a center frequency
- slow AM rates suitable for context cues
- level control via modulation trough in dB (e.g. 0 dB peak, -5 dB trough)
- generated files default to 44.1 kHz for WAV Trigger Pro compatibility
"""

from __future__ import annotations

import math
import os
import random
import struct
import wave
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # ---------- user-facing parameters ----------
    # WAV Trigger Pro accepts 16-bit 44.1 kHz mono/stereo WAV files.
    sample_rate: int = 44_100
    duration_s: float = 2.0

    # Carrier options:
    # mode = "tone"            -> single sine carrier at carrier_hz
    # mode = "tone_complex"    -> sum of nearby tones around carrier_hz
    mode: str = "tone"
    carrier_hz: float = 12_000.0

    # For tone_complex mode only. Frequencies are distributed inside this band.
    band_low_hz: float = 12_000.0
    band_high_hz: float = 18_000.0
    n_components: int = 24
    random_seed: int = 12345

    # AM context identifiers. One output file per entry.
    am_rates_hz: List[float] = field(default_factory=lambda: [0.5, 1.0, 2.0])

    # Envelope range in dB relative to the modulation peak.
    # Example: peak_db=0, trough_db=-20 gives a shallow AM.
    peak_db: float = 0.0
    trough_db: float = -20.0

    # Overall output headroom. Lower this if you increase n_components a lot.
    output_gain_db: float = -10.0

    # Optional leading/trailing ramp to avoid clicks.
    ramp_ms: float = 20.0

    # Whether to also write the plain unmodulated carrier.
    write_plain_carrier: bool = True

    # Whether to also write an unmodulated white-noise file matched in RMS
    # level to the AM contexts. A short edge ramp is still applied to avoid
    # clicks at onset/offset.
    write_white_noise_context: bool = True
    white_noise_filename: str = "context_white_noise.wav"

    # Whether to also write WAV Trigger Pro track-numbered files that match
    # the trigger-to-track mapping in generated_audio/set_0001.csv:
    # 001 = trial-available/plain carrier, 002-004 = contexts 1-3.
    write_wav_trigger_tracks: bool = True

    # Output directory.
    out_dir: str = "generated_audio"


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def linear_ramp_multiplier(i: int, n_samples: int, ramp_samples: int) -> float:
    if ramp_samples <= 0:
        return 1.0
    if i < ramp_samples:
        return i / ramp_samples
    tail_start = n_samples - ramp_samples
    if i >= tail_start:
        return max(0.0, (n_samples - 1 - i) / ramp_samples)
    return 1.0


def rms(samples: List[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(x * x for x in samples) / len(samples))


class CarrierSynth:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = random.Random(cfg.random_seed)
        if cfg.mode == "tone":
            self.freqs = [cfg.carrier_hz]
            self.phases = [self.rng.uniform(0.0, 2.0 * math.pi)]
            self.weights = [1.0]
        elif cfg.mode == "tone_complex":
            self.freqs = self._make_complex_freqs()
            self.phases = [self.rng.uniform(0.0, 2.0 * math.pi) for _ in self.freqs]
            # Equal weights. Could be randomized, but equal is more controlled.
            self.weights = [1.0 / len(self.freqs)] * len(self.freqs)
        else:
            raise ValueError("cfg.mode must be 'tone' or 'tone_complex'")

    def _make_complex_freqs(self) -> List[float]:
        low = self.cfg.band_low_hz
        high = self.cfg.band_high_hz
        n = self.cfg.n_components
        if not (0 < low < high):
            raise ValueError("Require 0 < band_low_hz < band_high_hz")
        if n < 1:
            raise ValueError("n_components must be >= 1")
        if n == 1:
            return [(low + high) / 2.0]
        # Even spread with mild jitter to reduce beating regularity.
        span = high - low
        freqs = []
        for k in range(n):
            base = low + span * k / (n - 1)
            step = span / max(1, n - 1)
            jitter = self.rng.uniform(-0.2 * step, 0.2 * step)
            f = clamp(base + jitter, low, high)
            freqs.append(f)
        return freqs

    def sample(self, t: float) -> float:
        s = 0.0
        for f, ph, w in zip(self.freqs, self.phases, self.weights):
            s += w * math.sin(2.0 * math.pi * f * t + ph)
        return s


def am_envelope(t: float, rate_hz: float, peak_db: float, trough_db: float) -> float:
    peak_amp = db_to_amp(peak_db)
    trough_amp = db_to_amp(trough_db)
    # cosine-shaped envelope in [0,1]
    x = 0.5 * (1.0 + math.sin(2.0 * math.pi * rate_hz * t - math.pi / 2.0))
    return trough_amp + (peak_amp - trough_amp) * x


def render_am_samples(cfg: Config, am_rate_hz: float | None) -> List[float]:
    n_samples = int(round(cfg.duration_s * cfg.sample_rate))
    ramp_samples = int(round(cfg.ramp_ms * 1e-3 * cfg.sample_rate))
    synth = CarrierSynth(cfg)
    master_gain = db_to_amp(cfg.output_gain_db)

    samples: List[float] = []
    for i in range(n_samples):
        t = i / cfg.sample_rate
        carrier = synth.sample(t)

        if am_rate_hz is None:
            env = 1.0
        else:
            env = am_envelope(t, am_rate_hz, cfg.peak_db, cfg.trough_db)

        ramp = linear_ramp_multiplier(i, n_samples, ramp_samples)
        y = carrier * env * master_gain * ramp
        samples.append(y)
    return samples


def render_white_noise_samples(cfg: Config, target_rms: float) -> List[float]:
    n_samples = int(round(cfg.duration_s * cfg.sample_rate))
    ramp_samples = int(round(cfg.ramp_ms * 1e-3 * cfg.sample_rate))
    rng = random.Random(cfg.random_seed + 1)

    samples = []
    for i in range(n_samples):
        ramp = linear_ramp_multiplier(i, n_samples, ramp_samples)
        samples.append(rng.uniform(-1.0, 1.0) * ramp)

    current_rms = rms(samples)
    scale = 0.0 if current_rms == 0.0 else target_rms / current_rms
    return [x * scale for x in samples]


def samples_to_pcm(samples: List[float]) -> bytes:
    pcm = bytearray()
    for y in samples:
        y = clamp(y, -0.999, 0.999)
        pcm.extend(struct.pack("<h", int(round(y * 32767.0))))
    return bytes(pcm)


def render_wave(cfg: Config, am_rate_hz: float | None) -> bytes:
    return samples_to_pcm(render_am_samples(cfg, am_rate_hz))


def write_wav(path: str, pcm_bytes: bytes, sample_rate: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def wav_trigger_track_filename(track_number: int) -> str:
    if track_number < 1:
        raise ValueError("track_number must be >= 1")
    return f"{track_number:03d}.wav"


def describe_config(cfg: Config) -> str:
    lines = [
        "Audio generation complete.",
        f"sample_rate={cfg.sample_rate}",
        f"duration_s={cfg.duration_s}",
        f"mode={cfg.mode}",
        f"carrier_hz={cfg.carrier_hz}",
        f"band_low_hz={cfg.band_low_hz}",
        f"band_high_hz={cfg.band_high_hz}",
        f"n_components={cfg.n_components}",
        f"am_rates_hz={cfg.am_rates_hz}",
        f"peak_db={cfg.peak_db}",
        f"trough_db={cfg.trough_db}",
        f"output_gain_db={cfg.output_gain_db}",
        f"ramp_ms={cfg.ramp_ms}",
        f"write_white_noise_context={cfg.write_white_noise_context}",
        f"white_noise_filename={cfg.white_noise_filename}",
        f"write_wav_trigger_tracks={cfg.write_wav_trigger_tracks}",
        f"out_dir={cfg.out_dir}",
    ]
    return "\n".join(lines)


def generate_audio_files(cfg: Config) -> list[str]:
    os.makedirs(cfg.out_dir, exist_ok=True)
    written_paths: list[str] = []

    if cfg.write_plain_carrier:
        pcm = render_wave(cfg, am_rate_hz=None)
        carrier_path = os.path.join(cfg.out_dir, "carrier_plain.wav")
        write_wav(carrier_path, pcm, cfg.sample_rate)
        written_paths.append(carrier_path)
        if cfg.write_wav_trigger_tracks:
            wav_trigger_path = os.path.join(
                cfg.out_dir, wav_trigger_track_filename(1)
            )
            write_wav(wav_trigger_path, pcm, cfg.sample_rate)
            written_paths.append(wav_trigger_path)

    reference_rate = cfg.am_rates_hz[0] if cfg.am_rates_hz else None
    reference_samples = render_am_samples(cfg, am_rate_hz=reference_rate)

    for idx, rate in enumerate(cfg.am_rates_hz, start=1):
        pcm = samples_to_pcm(render_am_samples(cfg, am_rate_hz=rate))
        fname = f"context_{idx}_AM_{str(rate).replace('.', 'p')}Hz.wav"
        context_path = os.path.join(cfg.out_dir, fname)
        write_wav(context_path, pcm, cfg.sample_rate)
        written_paths.append(context_path)
        if cfg.write_wav_trigger_tracks:
            wav_trigger_path = os.path.join(
                cfg.out_dir, wav_trigger_track_filename(idx + 1)
            )
            write_wav(wav_trigger_path, pcm, cfg.sample_rate)
            written_paths.append(wav_trigger_path)

    if cfg.write_white_noise_context:
        target_rms = rms(reference_samples)
        white_noise = render_white_noise_samples(cfg, target_rms=target_rms)
        white_noise_path = os.path.join(cfg.out_dir, cfg.white_noise_filename)
        write_wav(white_noise_path, samples_to_pcm(white_noise), cfg.sample_rate)
        written_paths.append(white_noise_path)

    readme_path = os.path.join(cfg.out_dir, "README_generated.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(describe_config(cfg) + "\n")
        f.write("\nNotes:\n")
        f.write("- Edit the Config dataclass at the top of the script to change parameters.\n")
        f.write("- This script uses only the Python standard library.\n")
        f.write("- tone_complex approximates a narrow-band carrier without numpy/scipy.\n")
        f.write("- White noise is not amplitude modulated; it is RMS-matched to the first AM context.\n")
        f.write("- Default sample rate is 44.1 kHz for WAV Trigger Pro compatibility.\n")
        f.write("- If write_wav_trigger_tracks is enabled, 001.wav is the plain carrier and 002-004.wav are contexts 1-3.\n")
        f.write("- Verify actual acoustic output in the chamber with your speaker/mic chain.\n")
    written_paths.append(readme_path)

    return written_paths


def main() -> None:
    cfg = Config()
    generate_audio_files(cfg)

    print(describe_config(cfg))


if __name__ == "__main__":
    main()
