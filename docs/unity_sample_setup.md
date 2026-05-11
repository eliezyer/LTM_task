# Unity Sample Integration

Sample Unity receiver code is provided in:

- `/Users/elie/Documents/github/LTM_task/unity_receiver/Assets/Scripts/`

## Provided Components

- `VrUdpReceiver`: listens on UDP and stores latest packet
- `VrContextGenerator`: procedurally creates opening/context/outcome/ITI environments and connected habituation tracks
- `VrRenderController`: switches scenes and applies position updates

## Expected Runtime Behavior

- RPi5 remains source of truth for state and position.
- Unity only renders based on latest packet each frame.
- Teleports are applied immediately when flag bit0 is set.
- ITI scene is shown whenever flag bit1 is set.
- Outcome scene is shown whenever flag bit3 is set.
- Habituation tracks are shown whenever flag bit4 is set.
- Corridor lengths are read from the UDP packet fields that mirror the session
  JSON, so Unity does not need manual inspector edits for training-length
  changes.
