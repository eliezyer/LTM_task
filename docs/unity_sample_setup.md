# Unity Sample Integration

Sample Unity receiver code is provided in:

- `/Users/elie/Documents/github/LTM_task/unity_receiver/Assets/Scripts/`

## Provided Components

- `VrUdpReceiver`: listens on UDP and stores latest packet
- `VrContextGenerator`: procedurally creates opening/context/ITI environments
- `VrRenderController`: switches scenes and applies position updates

## Expected Runtime Behavior

- RPi5 remains source of truth for state and position.
- Unity only renders based on latest packet each frame.
- Teleports are applied immediately when flag bit0 is set.
- ITI scene is shown whenever flag bit1 is set.
