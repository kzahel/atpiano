# Changelog

## [0.1.3]

- Match the desktop application's default light palette to the public website's
  warm paper, ivory, near-black, and piano-felt red visual language.
- Add an explicit dark mode that persists across launches and keeps the native
  desktop window chrome synchronized with the application.

## [0.1.2]

- Sign the hardened macOS application with its required audio-input
  entitlement so the system microphone consent prompt can appear.
- Reject release configuration and signed artifacts that omit the macOS
  microphone usage description or application entitlement.

## [0.1.1]

- Add an unmistakable proof-of-concept update marker to the desktop release
  panel.
- Preserve the compatible user-acquired score runtime, acknowledgement,
  installation identity, and session data across the signed update.
- Publish coordinated signed updates for macOS Apple silicon and Windows
  x86_64 through the existing production updater channel.

## [0.1.0]

- First public proof-of-concept release for macOS Apple silicon and Windows
  x86_64.
- Local recording and import with CPU transcription, playback, export, and
  score generation.
- Optional MIDI-to-score support acquired directly from its upstream project
  only after acknowledging the education/research-only notice; the upstream
  repository and model checkpoint are not bundled in Atpiano.
- Signed desktop installers and update client with external workspace and
  acquired-model persistence.
