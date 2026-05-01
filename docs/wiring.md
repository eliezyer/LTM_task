# Wiring and Pin Map

## UART (Teensy -> RPi5)

- Teensy TX -> RPi5 GPIO 15 (RX)
- Teensy RX <- RPi5 GPIO 14 (TX, optional)
- Shared GND required
- UART: 1,000,000 baud, 8N1

## Solenoids (via driver board)

- RPi5 GPIO 4 -> Water solenoid driver input
- RPi5 GPIO 5 -> Airpuff solenoid driver input

## WAV Trigger Pro

- RPi5 GPIO 6 -> WAV channel 1 trial-available trigger
- RPi5 GPIO 7 -> WAV channel 2 context 1 trigger
- RPi5 GPIO 8 -> WAV channel 3 context 2 trigger
- RPi5 GPIO 13 -> WAV channel 4 context 3 trigger

## Lick Detector

- AT42QT1011 OUT -> RPi5 GPIO 9

## NI TTL Event Lines

- GPIO 17 -> DI0 Trial start
- GPIO 18 -> DI1 Context identity pulse train
- GPIO 19 -> DI2 Context entry
- GPIO 20 -> DI3 Reward
- GPIO 21 -> DI4 Airpuff
- GPIO 22 -> DI5 Lick onset
- GPIO 23 -> DI6 ITI start
- GPIO 24 -> DI7 Outcome/reward-punishment zone active

## Notes

- Confirm BCM numbering is used in software.
- Keep grounds common across RPi, Teensy, and NI digital input reference.
