# Unity Integration Contract

RPi5 sends a fixed 16-byte UDP packet to Unity on every loop iteration.

## Packet

- Format: `<uint32 seq><float32 position_cm><uint8 scene_id><uint8 flags><uint16 opening_len_cm><uint16 context_len_cm><uint16 outcome_len_cm>`
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
  - bit4: habituation track active
- `opening_len_cm`, `context_len_cm`, `outcome_len_cm`:
  - unsigned integer corridor lengths, rounded to centimeters from the session JSON
  - sent in every packet so Unity can recover if it starts after the RPi
  - `opening_len_cm` comes from `opening_corridor_length_cm`
  - `context_len_cm` comes from `context_zone_length_cm`
  - `outcome_len_cm` comes from `outcome_zone_length_cm`

## Unity Receiver Behavior

- Listen on UDP port `5005`.
- At each render frame (60 Hz), consume only the latest packet.
- Do not queue gameplay state on Unity side; RPi5 remains source of truth.
- Show the outcome scene whenever bit3 is set; show ITI whenever bit1 is set.
  ITI takes precedence if both flags are ever present.
- When bit4 is set, show a connected habituation track: opening corridor first,
  then the current room/cue corridor immediately after it. In habituation,
  `scene_id` identifies the currently scheduled room while the animal is still in
  the opening corridor, and the room uses `context_len_cm`.
- Apply corridor dimensions when the packet length fields are nonzero. The
  sample Unity renderer rebuilds procedural geometry only when those dimensions
  change.
