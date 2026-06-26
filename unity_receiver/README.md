# Unity Receiver Sample

This folder contains sample Unity C# scripts for the rendering computer.

## Scripts

- `Assets/Scripts/VrUdpPacket.cs`: Parses 16-byte UDP packets from RPi5
- `Assets/Scripts/VrUdpReceiver.cs`: Background UDP listener (port 5005 by default)
- `Assets/Scripts/VrContextGenerator.cs`: Procedurally builds opening + 3 context scenes + outcome + ITI scene, plus connected habituation tracks, with blue-on-black inward-facing mesh walls
- `Assets/Scripts/VrRenderController.cs`: Activates scene + updates rig position from latest packet

## Packet Contract

- Size: 16 bytes
- Layout: `<uint32 seq><float32 position_cm><uint8 scene_id><uint8 flags><uint16 opening_len_cm><uint16 context_len_cm><uint16 outcome_len_cm>`
- `scene_id`: `0` opening, `1..3` context IDs, `4` outcome by default
- `flags` bitmask:
  - bit0: teleport event
  - bit1: ITI active
  - bit2: freeze
  - bit3: outcome zone active
  - bit4: habituation track active
- The three length fields are sent every packet from the RPi session JSON. Unity
  rebuilds the generated corridors only when a received length changes.

## Unity Setup

1. Create/open your Unity project on the rendering computer.
2. Copy `Assets/Scripts/*.cs` into your project's `Assets/Scripts/` folder.
3. Create an empty GameObject `VrRuntime` and attach:
   - `VrUdpReceiver`
   - `VrContextGenerator`
   - `VrRenderController`
4. In `VrRenderController`:
   - Set `Udp Receiver` reference
   - Set `Context Generator` reference
   - Set `Rig Transform` (camera or rig root that should move along the corridor)
5. Press Play and send UDP packets from RPi5.

## Notes

- The renderer uses only the newest packet and does not queue old packets.
- Scene 0 is used for the opening corridor; ITI uses a separate black scene when the ITI flag is set; outcome uses a separate scene when the outcome flag is set.
- In habituation mode, Unity shows a connected opening-plus-room track. The room
  is already visible at the end of the opening corridor, and `scene_id` selects
  which room/cue style is next. The room length follows `context_len_cm`, not
  `outcome_len_cm`.
- Corridor walls and floors are single-sided generated mesh planes facing into
  the corridor. Context floors reuse the wall pattern at lower brightness.
- Pattern UVs are based on physical centimeters, so increasing opening,
  context, or outcome corridor length adds repeated tiles instead of stretching
  the existing pattern.
- The context generator creates its own runtime materials and procedural textures. Leave `Material Template` empty and keep `Use Material Template Shader` off unless you have a known-good unlit shader for your render pipeline.
- Default scene cues are all blue on black: opening low-spatial smudges, context 1 vertical gratings, context 2 checkerboard, context 3 polka dots, and outcome arrowheads pointing down the corridor.
