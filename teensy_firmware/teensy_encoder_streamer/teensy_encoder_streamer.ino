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
constexpr uint32_t kLedBlinkMs = 50;

// Update pins to match your wiring.
constexpr int kEncoderPinA = 2;
constexpr int kEncoderPinB = 3;

Encoder wheelEncoder(kEncoderPinA, kEncoderPinB);
IntervalTimer txTimer;

uint8_t txPacket[8];
volatile bool encoderMovedSinceLastLoop = false;
volatile int32_t lastEncoderCount = 0;

void buildAndSendPacket() {
  int32_t count32 = wheelEncoder.read();
  int16_t count16 = static_cast<int16_t>(count32 & 0xFFFF);
  uint32_t tsMs = millis();

  if (count32 != lastEncoderCount) {
    encoderMovedSinceLastLoop = true;
    lastEncoderCount = count32;
  }

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

  Serial1.write(txPacket, sizeof(txPacket));
}

void txTimerISR() {
  buildAndSendPacket();
}
}  // namespace

void setup() {
  Serial1.begin(kBaud);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  txTimer.begin(txTimerISR, kSendPeriodUs);
}

void loop() {
  static uint32_t ledOffDeadlineMs = 0;

  bool encoderMoved = false;
  noInterrupts();
  if (encoderMovedSinceLastLoop) {
    encoderMovedSinceLastLoop = false;
    encoderMoved = true;
  }
  interrupts();

  if (encoderMoved) {
    digitalWrite(LED_BUILTIN, HIGH);
    ledOffDeadlineMs = millis() + kLedBlinkMs;
  }

  if (ledOffDeadlineMs != 0 &&
      static_cast<int32_t>(millis() - ledOffDeadlineMs) >= 0) {
    digitalWrite(LED_BUILTIN, LOW);
    ledOffDeadlineMs = 0;
  }
}
