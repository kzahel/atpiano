# 038 — WAV And MP3 Recording Import

Topic: session-workspace-management

Topic: live-acoustic-transcription

Topic: long-session-storage-retention

Status: **complete and live on 2026-07-28.** The user requested a real
recording import after an internal deterministic replay fixture leaked into
the normal capture UI. Fixture controls remain test-only; import is a separate
product source with its own transport, provenance, progress, and failure
contract.

## Motivation

`Run test recording` is useful only for deterministic development and must
never be presented as a way to add a pianist's recording. The usable product
needs an explicit way to choose a WAV or MP3 file, create a normal session,
transcribe it through the same sample-indexed pipeline, and revisit it in the
Sessions library.

## User-Visible Outcome

- New performance offers `Import recording` beside microphone capture when
  the active runtime advertises upload support.
- The picker accepts WAV and MP3 files and identifies the selected filename.
- Upload and processing are distinct states. Transfer progress appears at the
  import control; transcription progress follows the imported session's
  source-sample horizon.
- The newly created session is selected immediately and uses the source
  filename, without its extension, as its automatic display name.
- Upload, decode, and transcription failures appear at the import/capture
  surface with useful retry guidance. They do not enter a global notice pile.
- Deterministic replay remains available only in explicit fixture mode and is
  never labeled as upload or import.

## Contract And Pipeline

1. Add `upload` to the advertised capture sources only when the runtime has a
   configured import adapter.
2. Add one authenticated, workspace-addressed binary import operation. Require
   an exact content length, stream the request to bounded temporary storage,
   cap accepted bytes, validate filename/media type, and reject concurrent
   active capture through the existing writer lease.
3. Decode WAV and MP3 with the local FFmpeg boundary to mono PCM16 while
   retaining the decoded source sample rate. Feed sequential `PcmBlock`
   values through `CaptureApplicationService`; do not invent arrival-derived
   musical time.
4. Persist a compact application-owned `upload.json` record containing the
   original filename, declared and detected format, source byte count,
   SHA-256, decoded sample rate, channel/downmix information, and final decoded
   frame count. The imported bytes are temporary working data; the verified
   session recording and existing retention pipeline remain authoritative.
5. Delete a known upload spool after complete durable PCM acceptance or after
   a recorded failure. Clean stale known spools on startup. Never accumulate
   anonymous upload files.
6. Share the operation across local browser, authenticated family, and
   desktop runtimes. Apply the existing capture authorization and workspace
   target checks before accepting a body.

## Implementation Slices

1. Record this tactical and the continuing topic direction.
2. Add import metadata/contracts, a streaming FFmpeg upload adapter,
   application capture orchestration, local/family routes, authorization,
   cleanup, and backend tests.
3. Add runtime-provider upload transport plus the New-performance file picker,
   transfer/processing feedback, selection, and focused frontend tests.
4. Run focused and complete regression, production build, storage/error
   checks, and live-service refresh and verification when active.

Validated slices use:

```text
Topic: session-workspace-management
Topic: live-acoustic-transcription
Topic: long-session-storage-retention
```

## Invariants

- One local workspace still has at most one active capture/import session.
- Selection remains browser-local and cannot retarget an active import.
- Source time is decoded-frame/sample-rate time, never HTTP arrival time.
- Request bodies and temporary disk use have explicit limits and cleanup.
- Authentication and role checks occur before an upload body is consumed.
- A completed imported session follows ordinary event, score, playback,
  export, trash, and compact-recording behavior.
- Import provenance is application metadata; capture and model evidence remain
  immutable.
- Existing microphone sessions, historical sessions, fixtures, v1, and v2
  prototype commands remain readable and runnable.

## Validation

- WAV and MP3 fixtures produce upload sessions with contiguous source samples,
  accurate duration, preserved provenance, and ordinary artifacts.
- Stereo input is deterministically downmixed; malformed, unsupported,
  empty, oversized, truncated, and decode-failing input is rejected cleanly.
- Import cannot race microphone/replay or escape the workspace through a
  filename.
- Family routes reject anonymous/viewer writes before reading the upload and
  accept an authorized operator.
- Local HTTP, family HTTP, and desktop runtime providers use the same runtime
  behavior; generated contracts remain in sync.
- React tests cover file filtering, transfer progress, selected-session
  transition, processing state, contextual failure, retry, and fixture-action
  isolation.
- Python tests, Ruff, TypeScript, frontend tests, contract drift, production
  build, migration regression, and Git whitespace pass.
- If the shared macOS service is active, restart it and verify the public
  homepage, protected capability/import routes, and one bounded authenticated
  WAV import without retaining the verification session.

## Human Review Boundary

Implementation may proceed without an intermediate review. Pause only if:

- supporting MP3 requires a new licensed decoder or bundled binary;
- bounded streaming cannot be shared across the authenticated and local
  service paths;
- the existing compact recording cannot remain the authoritative retained
  audio; or
- import requires changing completed-session evidence or the
  selected-versus-active boundary.

## Execution Record

### Landed slices

- `177f0a9` recorded the accepted implementation boundary and continuing topic
  direction.
- `f3317b5` added the `upload` source contract, bounded known spools,
  free-space protection, FFmpeg/FFprobe WAV and MP3 validation, source-rate
  mono PCM16 decoding, compact provenance, ordinary capture orchestration,
  filename-derived automatic naming, local/desktop HTTP, authenticated family
  HTTP, and focused backend tests.
- `b52434d` added the shared runtime operation, New-performance file chooser,
  chosen-file and transfer feedback, imported-session selection and settlement
  tracking, source labels, fixture-runtime behavior, and focused frontend
  tests.

The import limit is 2 GiB. WAV/MP3 bytes are streamed to a mode-0600 known
spool and never buffered as one Python request body. The spool is removed
after the normal transcription pipeline settles or records a failure. The
decoded source sample rate and contiguous decoded frame count remain the
musical timeline. `upload.json` retains original filename, declared media
type, byte count, SHA-256, detected format/codec/sample rate/channel count,
downmix policy, and decoded frame/block counts.

### Validation and live evidence

The complete migration regression passed at
`results/migration-regression/20260728T114219Z/report.json`: 210 Python tests,
82 frontend tests, six TypeScript Node tests, generated-contract drift,
TypeScript, npm high-severity audit, Ruff, retained JavaScript syntax, and Git
whitespace all passed. The production Vite build also passed with only the
existing OpenSheetMusicDisplay chunk-size advisory.

Focused real-adapter tests decode both stereo WAV and MP3 to contiguous mono
PCM16 at the source rate. Application tests prove upload cannot displace an
active microphone lease. Local and family integration tests prove ordinary
completion and filename naming; family tests prove anonymous and viewer
requests are rejected before a spool is retained.

The already-active authenticated macOS share service was restarted. Its public
homepage returned HTTP 200 with `index-zEF2WWwz.js`; anonymous capabilities
remained protected with HTTP 401. A temporary authenticated operator observed
exactly `microphone` and `upload` live capture sources. A 530 KiB,
12.31-second WAV imported through the public HTTPS route as session
`20260728T114446-d33e169a31bd`, preserved 271,436 source frames at 22,050 Hz,
used `live-upload-check` as its automatic title, completed normal
transcription/retention, and was then recoverably deleted. The exact synthetic
trash directory was permanently removed after target validation, and the
temporary operator session was logged out and verified revoked.
