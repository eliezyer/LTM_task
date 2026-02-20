#include <Arduino.h>
#include <Encoder.h>
#include <IntervalTimer.h>

// Teensy 4.1 encoder streamer for RPi5 behavioral controller.
// Packet format (8 bytes):
// [0xAA][COUNT_L][COUNT_H][TS0][TS1][TS2][TS3][CHECKSUM_XOR_BYTES_1_TO_6]

namespace {
constexpr uint8_t kSync = 0xAA;
constexpr uint32_t kBaud = 1000000;
constexpr uint32_t kSendPeriodUs = 1000;  // 1 kHz

// Update pins to match your wiring.
constexpr int kEncoderPinA = 2;
constexpr int kEncoderPinB = 3;

Encoder wheelEncoder(kEncoderPinA, kEncoderPinB);
IntervalTimer txTimer;

volatile uint8_t txPacket[8];

void buildAndSendPacket() {
  int32_t count32 = wheelEncoder.read();
  int16_t count16 = static_cast<int16_t>(count32 & 0xFFFF);
  uint32_t tsMs = millis();

  txPacket[0] = kSync;
  txPacket[1] = static_cast<uint8_t>(count16 & 0xFF);
  txPacket[2] = static_cast<uint8_t>((count16 >> 8) & 0xFF);
  txPacket[3] = static_cast<uint8_t>(tsMs & 0xFF);
  txPacket[4] = static_cast<uint8_t>((tsMs >> 8) & 0xFF);
  txPacket[5] = static_cast<uint8_t>((tsMs >> 16) & 0xFF);
  txPacket[6] = static_cast<uint8_t>((tsMs >> 24) & 0xFF);

  uint8_t checksum = 0;
  for (int i = 1; i <= 6; ++i) {
    checksum ^= txPacket[i];
  }
  txPacket[7] = checksum;

  Serial1.write(reinterpret_cast<const uint8_t*>(txPacket), sizeof(txPacket));
}

void txTimerISR() {
  buildAndSendPacket();
}
}  // namespace

void setup() {
  Serial1.begin(kBaud);
  txTimer.begin(txTimerISR, kSendPeriodUs);
}

void loop() {
  // All work is performed in timer ISR to maintain 1 kHz packet cadence.
}
