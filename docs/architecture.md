# Atpiano Architecture

This document describes the durable system boundary and the contracts shared
by the local web, desktop, and private family deployments. It is intentionally
independent of current model benchmarks and release status; those belong in
[topic documents](topics/README.md).

## Product Boundary

Atpiano owns:

- timestamped audio capture or ingestion from a local microphone, imported
  recording, or deterministic replay;
- acoustic-piano transcription;
- reconciliation of overlapping or revised model output;
- a normalized, timestamped note-event stream; and
- review, playback, export, and optional notation over a retained performance.

The musical views do not invoke inference implementations directly. They
consume an explicit runtime contract so the same React workspace can operate
against local Python services, a packaged desktop sidecar, or the
authenticated family service.

## Data Flow

```text
microphone / recording import / deterministic replay
                         |
                         v
             sample-indexed PCM and audio
                         |
             +-----------+-----------+
             |                       |
             v                       v
   provisional transcription   durable session storage
             |
             v
    bounded correction and reconciliation
             |
             v
 normalized timestamped note-event stream
             |
             v
         runtime contract
             |
      +------+------+---------+
      |             |         |
      v             v         v
 playback/roll   keyboard   optional score/export
```

## Timeline Contract

The audio sample clock is the authoritative source timeline. Event time is not
derived from packet arrival, inference completion, transport, or browser paint
time. Capture-to-event latency is reported separately from preprocessing,
scheduling, inference, post-processing, transport, and delivery.

Browser audio, native capture, imported recordings, and replay all enter the
same sample-indexed domain. That makes a retained event comparable with the
audio that caused it even when processing is delayed or repeated.

## Transcription And Reconciliation

The current engine may publish low-look-ahead notes as provisional and revise
settled spans with a higher-context model. Window edges are treated as
suspect: overlapping output is retained and reconciled under an explicit
commit policy rather than accepted as independent final predictions.

Model-native evidence and append-only revisions are preserved when practical
so decoder thresholds and correction behavior can be reevaluated without
rerunning capture. A committed event stream is the stable consumer boundary;
the frontend does not depend on Basic Pitch, Transkun, accelerator APIs, or a
particular scheduler.

## Sessions And Storage

A session gives one performance a stable identity across capture, settlement,
review, and export. Active capture and selected history are separate concepts:
reviewing an older performance does not redirect incoming audio or model
output.

Authoritative session manifests and checksummed artifacts remain on the local
filesystem. Long recordings use bounded segmented storage during capture and
retain a compact verified audio artifact after settlement. Append-only event
evidence can be indexed for range queries without making the index the source
of truth. Deletion is recoverable before permanent purge.

See [R4 Python Core and Storage Review](r4-python-core-storage-review.md) and
[Long-Session Storage Retention](topics/long-session-storage-retention.md) for
the detailed contracts and evidence.

## Optional Notation

Score generation consumes a frozen, committed note prefix. It is isolated from
capture: a slow or failed score job cannot block audio ingestion, note
settlement, playback, piano-roll, keyboard, or non-score exports.

Generated MusicXML is retained with its exact source horizon and provenance.
Alignment reconciles score attacks back to source events rather than assuming
that model token positions preserve source identity. The score runtime is an
optional execution boundary with separate distribution and licensing rules.

See [Performance to Notation](topics/performance-to-notation.md) and
[Desktop Score Runtime Footprint](topics/desktop-score-runtime-footprint.md).

## Runtime And Deployment Surfaces

- **Local web:** React uses the local Python application services and stores
  sessions below a selected workspace directory.
- **Desktop:** Tauri starts an authenticated local Python sidecar and presents
  the same React application without requiring a checkout or hosted login.
- **Private family service:** FastAPI, SQLite identity data, and the local
  workspace are shared through an on-demand Mac service and home reverse
  proxy.

Accelerator-specific code remains behind the model execution boundary. CPU,
Apple, CUDA, and future accelerator lanes must consume and produce the same
adapter contracts.

The desktop process boundary is reviewed in
[R5 Desktop Boundary Review](r5-desktop-boundary-review.md). The private
service topology and security boundary live in
[Home-Hosted Family Sharing](topics/home-hosted-family-sharing.md).

## Application Generations

- **V1** established browser capture, rolling recognition, retained evidence,
  and the first review surface.
- **V2** established bounded long sessions, provisional and corrected events,
  pedal data, indexed history, and committed score snapshots.
- **V3** is the authoritative product workspace. It places the retained engine
  behind explicit runtime and application-service boundaries and provides one
  shared React interface for local, desktop, and family deployments.

The accepted V3 interaction contract is recorded in
[R3 Interaction and Frontend Review](r3-interaction-review.md). Source setup,
validation, prototypes, and benchmarks are documented in the
[development guide](development.md).
