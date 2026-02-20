# Unity Integration Contract

RPi5 sends a fixed 16-byte UDP packet to Unity on every loop iteration.

## Packet

- Format: `<uint32 seq><float32 position_cm><uint8 scene_id><uint8 flags><6 byte padding>`
- Size: 16 bytes

## Fields

- `seq`: monotonic counter (wraps at 2^32)
- `position_cm`: virtual position inside current segment
- `scene_id`:
  - `0`: opening/black
  - `1,2,3`: context scene IDs
- `flags` bitmask:
  - bit0: teleport event this tick
  - bit1: ITI active
  - bit2: freeze

## Unity Receiver Behavior

- Listen on UDP port `5005`.
- At each render frame (60 Hz), consume only the latest packet.
- Do not queue gameplay state on Unity side; RPi5 remains source of truth.
