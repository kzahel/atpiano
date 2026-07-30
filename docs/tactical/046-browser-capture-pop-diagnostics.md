# 046 — Browser Capture Pop Diagnostics

Topic: live-acoustic-transcription

Status: **complete, live, and physically reviewed on a Pixel 9 on
2026-07-30.** The old reduced user agent cannot prove that this was the exact
device that made the complaint recording.

## Motivation

A family microphone recording contained audible pops:
`20260727T185541-a2298f1afaaf`. The retained session could prove server-side
sample continuity, but its browser evidence contained only a reduced user
agent and aggregate WebSocket counts. It could not distinguish an audio-render
defect from main-thread delivery delay, missing worklet input, or a render
clock discontinuity.

## Incident Evidence

The session was captured at 48 kHz by mobile Chrome 150 on Android. Its
reduced user agent reports `Android 10; K`, which does not identify the device
model or actual OS version.

Capture and transport were complete:

- 4,550 ordered blocks and 9,316,608 frames were sent and durably accepted;
- the session manifest and pipeline status contain no source gaps;
- WebSocket buffered bytes reached only 4,704 at Stop;
- the verified MP3 decodes to exactly 9,316,608 frames without codec errors;
  and
- the decoded recording peaks at about 0.75 full scale and contains no
  clipping.

Waveform inspection found a different signature. All 49 adjacent-sample jumps
of at least 0.08 full scale occur exactly at a multiple of 128 frames. Of the
70 jumps at least 0.06, 65 occur on those boundaries. The largest boundary
jump is 0.351; the largest jump inside a render quantum is 0.077. Recent real
Mac microphone captures have no jumps of at least 0.06 on a 128-frame
boundary.

The default Web Audio render quantum is 128 frames. This alignment makes a
server receive gap, model stall, clipping, or ordinary MP3 artifact
implausible. It is evidence that adjacent quanta supplied through the Android
Web Audio input path were discontinuous. The retained compact session no
longer has its source WAV, so the exact pre-encode jump magnitudes cannot be
recovered. The evidence does not distinguish browser scheduling, OS audio
driver/resampler behavior, device load, or power management.

## Implemented Contract

New browser microphone sessions retain two compact records beside the
recording:

1. `client.json` receives versioned capture-start metadata:
   - application build and page execution context;
   - raw user agent plus User-Agent Client Hints when available, including
     full browser versions, OS version, architecture, bitness, form factor,
     and Android model;
   - hardware concurrency, approximate device memory, touch/display, locale,
     and network class;
   - requested microphone constraints and actual track settings,
     constraints, capabilities, and label; and
   - AudioContext sample rate, requested and granted latency, and capture
     processor identity.
2. `transport.json` receives versioned Stop diagnostics:
   - worklet render-quantum count and observed sizes;
   - captured, emitted, and missing-input frame counts;
   - render-clock missing or repeated frames;
   - maximum and thresholded absolute sample jumps separately at quantum
     boundaries and inside quanta;
   - main-thread chunk-message interval and worklet-to-main audio-clock delay;
     and
   - page visibility and AudioContext state at Stop.

Raw `deviceId` and `groupId` values are deliberately excluded. Their presence
is recorded, and the permission-revealed microphone label is retained because
wired, built-in, USB, and Bluetooth paths are diagnostically material.

The filesystem session remains the authoritative recording store. The SQLite
catalog owns identity and authorization, not immutable capture evidence, so
these records stay with the recording rather than becoming unrelated catalog
columns.

## Reliability Change

The capture-only `AudioContext` now requests the `playback` latency category
instead of the low-latency `interactive` default. Atpiano does not monitor the
captured sound locally, and its first useful transcription already has much
larger model look-ahead. The hint therefore prioritizes sustained,
uninterrupted rendering over a small browser-side latency reduction. Browsers
may ignore the hint; the granted `baseLatency` and `outputLatency` are
retained.

The worklet still performs only bounded copies and aggregate arithmetic. It
posts one transferable 2,048-frame block rather than messaging every
128-frame quantum. If a render callback has no input channel, it now emits
silence for that render quantum and records the missing input instead of
compressing the source timeline.

Slow main-thread JavaScript can delay MessagePort handling, PCM conversion,
and WebSocket send. It does not normally stop the separate audio rendering
thread, and MessagePort ordering means delayed chunks queue rather than splice
adjacent samples. Severe whole-device load can nevertheless starve the audio
thread or browser audio service; the new worklet and main-thread aggregates
separate those cases.

## Validation

- a VM-executed worklet test proves a missing input quantum preserves 128
  frames of source time and reports boundary jumps and a render-clock gap;
- frontend metadata coverage proves high-entropy browser/device fields,
  actual track/context settings, and omission of raw device identifiers;
- local runtime coverage proves versioned start metadata and Stop diagnostics
  cross the WebSocket control path;
- application coverage accepts the known diagnostic schema, persists it in
  `transport.json`, and rejects an unknown schema;
- 103 frontend tests, 12 TypeScript Node tests, 248 Python tests, TypeScript,
  JavaScript syntax, Ruff, the production build, and the full migration
  regression pass. The retained report is
  `results/migration-regression/20260730T114139Z/report.json`.

The already-active authenticated macOS service was restarted. The public
homepage returned HTTP 200 with the new `index-DNCdrALv.js`; the deployed
capture processor contains the worklet diagnostic schema; anonymous
capabilities remain protected with HTTP 401; and a passwordless operator check
read both the affected session's protected MP3 range and 701,346-byte
MusicXML, observed score capability, and verified operator-session revocation.
No microphone was activated automatically.

## Pixel 9 Physical Review

A USB-attached Pixel 9 ran the deployed application in Chrome
150.0.7871.186 on Android 17. User-Agent Client Hints correctly retained the
model and real OS/browser versions that the reduced user agent hid. Chrome
granted mono 48 kHz, 16-bit microphone input with echo cancellation, noise
suppression, automatic gain, and voice isolation all disabled. The track
reported 40 ms latency; the capture AudioContext reported 21.33 ms base
latency and retained the requested `playback` hint.

Three completed sessions preserve progressively cleaner evidence:

- `20260730T115457-c00162908e4b` recorded 6,792,192 frames over 141.504
  seconds while the room was uncontrolled. It had no missing input, no
  render-clock gap, a 161 ms maximum main-thread delivery interval, and two
  quantum-boundary jumps of at least 0.1, peaking at 0.122. The user reported
  possibly making noise, so this is not a controlled positive reproduction.
- `20260730T120018-5a2842a024fb` used the Pixel speaker to emit a smooth
  440 Hz tone. It preserved all 3,229,696 frames with no missing input or
  render-clock gap. Two candidate boundary discontinuities reached 0.053 and
  were exactly 1,920 frames, or 40 ms, apart; no jump reached 0.06. Android
  logged three Chrome input-FIFO underflows near startup, but none at the
  candidate jump times. Room noise was still possible during this run.
- `20260730T120342-b44bbdf3793c` repeated the smooth tone after the user left
  the room and deliberately blocked the page main thread for exactly three
  seconds during the tone. The block produced a 3.061-second chunk-delivery
  interval, 3.013 seconds of worklet-to-main delay, and a 290,080-byte socket
  high-water. Nevertheless all 3,124,224 frames arrived, missing-input and
  render-clock counters remained zero, and the raw PCM had no adjacent-sample
  jump of even 0.02. Its largest boundary and inside-quantum jumps were only
  0.00458 and 0.00513. Settlement committed the full source horizon without
  error.

The quiet-room stall is direct evidence that slow page JavaScript alone queues
worklet messages rather than splicing PCM. It does not prove that an
underpowered or thermally throttled device cannot starve Chrome's audio render
thread or Android audio service as well. The two smaller candidate
discontinuities in the earlier tone run also leave the underlying Android
input path intermittent rather than fully exonerated. A repeated quiet tone
on a genuinely older device, followed by the same device's native recorder,
would be the most useful next comparison.
