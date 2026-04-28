Audio generation complete.
sample_rate=44100
duration_s=2.0
mode=tone
carrier_hz=12000.0
band_low_hz=12000.0
band_high_hz=18000.0
n_components=24
am_rates_hz=[0.5, 1.0, 2.0]
peak_db=0.0
trough_db=-20.0
output_gain_db=-10.0
ramp_ms=20.0
write_white_noise_context=True
white_noise_filename=context_white_noise.wav
write_wav_trigger_tracks=True
out_dir=generated_audio

Notes:
- Edit the Config dataclass at the top of the script to change parameters.
- This script uses only the Python standard library.
- tone_complex approximates a narrow-band carrier without numpy/scipy.
- White noise is not amplitude modulated; it is RMS-matched to the first AM context.
- Default sample rate is 44.1 kHz for WAV Trigger Pro compatibility.
- If write_wav_trigger_tracks is enabled, 001.wav is the plain carrier and 002-004.wav are contexts 1-3.
- Verify actual acoustic output in the chamber with your speaker/mic chain.
