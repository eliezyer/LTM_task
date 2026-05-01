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
  - context scene IDs come from each context's `scene_id` in the session config
  - outcome scene ID comes from `outcome_scene_id` and defaults to `4`
- `flags` bitmask:
  - bit0: teleport event this tick
  - bit1: ITI active
  - bit2: freeze
  - bit3: outcome zone active

## Unity Receiver Behavior

- Listen on UDP port `5005`.
- At each render frame (60 Hz), consume only the latest packet.
- Do not queue gameplay state on Unity side; RPi5 remains source of truth.
- Show the outcome scene whenever bit3 is set; show ITI whenever bit1 is set.
  ITI takes precedence if both flags are ever present.
