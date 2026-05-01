# Unity Receiver Sample

This folder contains sample Unity C# scripts for the rendering computer.

## Scripts

- `Assets/Scripts/VrUdpPacket.cs`: Parses 16-byte UDP packets from RPi5
- `Assets/Scripts/VrUdpReceiver.cs`: Background UDP listener (port 5005 by default)
- `Assets/Scripts/VrContextGenerator.cs`: Procedurally builds opening + 3 context scenes + outcome + ITI scene with blue-on-black wall textures
- `Assets/Scripts/VrRenderController.cs`: Activates scene + updates rig position from latest packet

## Packet Contract

- Size: 16 bytes
- Layout: `<uint32 seq><float32 position_cm><uint8 scene_id><uint8 flags><6 padding bytes>`
- `scene_id`: `0` opening, `1..3` context IDs, `4` outcome by default
- `flags` bitmask:
  - bit0: teleport event
  - bit1: ITI active
  - bit2: freeze
  - bit3: outcome zone active

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
- The context generator creates its own runtime materials and procedural textures. Leave `Material Template` empty and keep `Use Material Template Shader` off unless you have a known-good unlit shader for your render pipeline.
- Default scene cues are all blue on black: opening low-spatial smudges, context 1 vertical gratings, context 2 checkerboard, context 3 polka dots, and outcome arrowheads pointing down the corridor.
