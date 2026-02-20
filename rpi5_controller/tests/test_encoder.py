from __future__ import annotations

from rpi5_controller.core.encoder import EncoderPacketParser, build_teensy_packet


def test_encoder_parser_decodes_valid_packet() -> None:
    parser = EncoderPacketParser()
    data = build_teensy_packet(encoder_count=1234, timestamp_ms=5678)

    packets = parser.feed(data)

    assert len(packets) == 1
    assert packets[0].encoder_count == 1234
    assert packets[0].timestamp_ms == 5678


def test_encoder_parser_ignores_bad_checksum() -> None:
    parser = EncoderPacketParser()
    packet = bytearray(build_teensy_packet(encoder_count=-10, timestamp_ms=99))
    packet[-1] ^= 0xFF

    packets = parser.feed(bytes(packet))

    assert packets == []
