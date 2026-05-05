# Teensy Firmware Build Notes

Firmware file: `teensy_firmware/teensy_encoder_streamer.ino`

## Behavior

- Reads quadrature encoder via Teensy `Encoder` library
- Emits fixed 8-byte packet at 1 kHz over `Serial1` at 1,000,000 baud
- Packet: `[0xAA][count_low][count_high][timestamp_ms_le32][xor_checksum]`

## Build and Flash

1. Open Arduino IDE with Teensyduino installed.
2. Select board: Teensy 4.1.
3. Open `teensy_firmware/teensy_encoder_streamer.ino`.
4. Confirm encoder pins match wiring (`kEncoderPinA`, `kEncoderPinB`).
5. Upload.

## Validation

- Connect Teensy `Serial1 TX` to RPi5 `GPIO15 (RX)` with shared ground.
- Verify 1 Mbaud stream with logic analyzer or serial sniffer on RPi.
- Run `python tools/calibrate_wheel.py --config configs/your_session.json` and
  use the reported count delta as `encoder_cpr` in the session config.
