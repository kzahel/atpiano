# Browser-Only WASM Deployment

Topic: browser-only-wasm-deployment

Status: **deprioritized optional executor, not the product architecture.** The
user clarified on 2026-07-25 that browser-only deployment was an appealing
idea rather than a constraint, and that any execution backend including
NVIDIA/CUDA is acceptable if it gives a clearly better result. On 2026-07-26,
the project accepted a shared hosted-web plus offline Tauri architecture in
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md).
That architecture may later use a WASM lane, but it does not depend on one.

A local ONNX Runtime Web WASM execution smoke test succeeded. Browser replay,
model-output parity, live microphone latency, storage behavior, and offline
installation are not validated. Do not describe this as an implemented
deployment.

**This topic must not constrain model selection.** Quality is chosen first, on
the evidence owned by
[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md);
deployment adapts to it. If a selected model cannot run in a browser, that is a
fact about this topic's feasibility, not an argument against the model. The
work below stays valid as a description of what a browser-only build would
require, should a small enough model lane ever be worth shipping that way.

## Scope And Relationship

This topic owns the option to deploy the useful atpiano experience as a static,
client-side web application:

- microphone capture and sample-clocked buffering in the browser;
- rolling and final transcription on the user's device;
- local event reconciliation, display, and artifact creation;
- browser-managed persistence and explicit downloads;
- installation and offline reuse as a progressive web application; and
- static hosting with no application server, accounts, or audio upload.

This is a deployment and execution-boundary concern. It does not select a new
acoustic model or change the transcription-quality standard.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
owns the selected hosted and desktop product topology, tenancy, persistence,
sync, and distribution path. This topic describes only an optional
browser-local runtime that could plug into the shared application.
[`live-acoustic-transcription.md`](live-acoustic-transcription.md) continues to
own the live event lifecycle, sample-clock timeline, windowing, gate,
reconciliation, and latency evidence.
[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md)
continues to own model quality and reproducible comparison. The paused
[`performance-to-notation.md`](performance-to-notation.md) topic owns score
semantics, whether or not its implementation runs in a browser.

The Python benchmark remains useful for research and regression testing. A
browser-only product does not require every research command or diagnostic
dependency to ship to users.

## What "No Server" Means

The target is **no application backend**:

- no Python process after the site is built;
- no WebSocket carrying microphone audio to a host;
- no upload or transcription API;
- no server-side model, queue, filesystem, or job database; and
- no network dependency during capture, inference, review, or export.

The browser still needs a secure web origin to grant microphone, service
worker, and durable-storage capabilities. The practical forms are:

1. a static site served over HTTPS;
2. the same static build served from `http://localhost` for development or
   private local use; or
3. an installed progressive web application that reuses cached assets while
   offline after its initial HTTPS or localhost load.

This is compatible with static self-hosting. It is not a promise that opening
`index.html` directly from an arbitrary `file://` path will provide identical
behavior in every browser. Microphone access and service workers are
secure-context features; browsers treat HTTPS and localhost as the dependable
paths. See the browser documentation for
[`getUserMedia`](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
and
[`ServiceWorker`](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API).

## Why This Is Credible

Most of the live user path is already browser-native:

- [`capture-processor.js`](../../src/atpiano/web/capture-processor.js) uses an
  `AudioWorklet` and supplies sample-indexed PCM;
- [`app.js`](../../src/atpiano/web/app.js) owns capture controls, visualization,
  live event consumption, WAV construction, and downloads;
- [`live-view.js`](../../src/atpiano/web/live-view.js) owns portable display
  settings and onset grouping; and
- the keyboard and sequential staff are ordinary HTML, CSS, SVG, and
  JavaScript.

The present server provides four functions that have browser equivalents:

| Present host responsibility | Browser-only equivalent |
|---|---|
| receive PCM over WebSocket | send worklet blocks to a dedicated worker |
| resample, window, and run Core ML | resample and run ONNX Runtime Web WASM in the worker |
| write job directories and reports | write OPFS/IndexedDB records and create explicit downloads |
| serve artifacts and APIs | read local records directly and render in the page |

Spotify also publishes
[`@spotify/basic-pitch`](https://github.com/spotify/basic-pitch-ts), a
TypeScript implementation intended to have feature parity with the Python
library. It accepts fixed audio windows, produces the native frame, onset, and
contour arrays, and includes a JavaScript decoder. It is useful implementation
evidence and a comparator even if atpiano uses the ONNX artifact and preserves
its own stricter decoder policy.

[ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/) provides a
browser WebAssembly execution provider. Its documentation states that the WASM
provider supports all ONNX operators and runs across the major desktop and
mobile browsers. WebGPU can be evaluated later, but is not required for a
portable first implementation.

## Local WASM Smoke Test

### Artifact And Environment

The repository's pinned `basic-pitch==0.4.0` installation includes four model
forms. The smoke test used the shipped ONNX form rather than converting a new
model:

```text
artifact: basic_pitch/saved_models/icassp_2022/nmp.onnx
size: 230,444 bytes
SHA-256:
2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec

host: Apple M4 Pro, arm64
macOS: 26.5.2
Node: v25.8.2
ONNX Runtime Web: 1.27.0
WASM threads: 1
input: 43,844 zero-valued float32 samples, shape [1, 43844, 1]
```

The test ran `onnxruntime-web`, not `onnxruntime-node`. ONNX Runtime documents
Node support for this WebAssembly provider as single-threaded; the result is a
useful execution-compatibility and throughput smoke test. It is not a browser
UI or microphone measurement.

### Execution Result

The session loaded the exact model successfully and exposed the names expected
by Basic Pitch's Python ONNX adapter:

```text
input:
  serving_default_input_2:0

outputs:
  StatefulPartitionedCall:2  [1, 172, 88]   onset
  StatefulPartitionedCall:1  [1, 172, 88]   note
  StatefulPartitionedCall:0  [1, 172, 264]  contour
```

Observed timings from the first smoke invocation were:

```text
session load:       135.6 ms
first inference:     55.9 ms
warm inference:      33.4 ms
```

The current rolling host runs one 43,844-sample model window every 250 ms. A
33.4 ms single-thread WASM observation on this host therefore supports the
throughput hypothesis. It does not establish capture-to-display latency, a
cross-browser guarantee, or performance on older and mobile hardware.

### Reproduction Shape

The essential test was:

```javascript
import * as ort from "onnxruntime-web";

ort.env.wasm.numThreads = 1;
const session = await ort.InferenceSession.create(modelPath, {
  executionProviders: ["wasm"],
});
const input = new ort.Tensor(
  "float32",
  new Float32Array(43844),
  [1, 43844, 1],
);
const output = await session.run({
  [session.inputNames[0]]: input,
});
```

The package was installed in a temporary directory and no repository files
were changed by the experiment.

### Parity Warning

The same zero-valued input was also sent through the current Basic Pitch Core
ML adapter:

```text
Core ML inference: 19.2 ms

Core ML note:
  min 0.055603, max 0.143915, mean 0.057150
Core ML onset:
  all zero
Core ML contour:
  all zero

ONNX Runtime Web WASM note:
  min 0.093614, max 0.160707, mean 0.099147
ONNX Runtime Web WASM onset:
  min 0.021489, max 0.168681, mean 0.104747
ONNX Runtime Web WASM contour:
  min 0.080705, max 0.214749, mean 0.098959
```

The serialized model variants therefore must not be assumed to be numerically
identical merely because they ship in one Basic Pitch release. An all-zero
window is also not sufficient to determine which behavior matters on real
audio. This result establishes only that the model loads and executes with the
right tensor contract.

The first implementation gate must replay the aligned fixture and retained
target-piano recordings through both backends, then compare:

- raw arrays with declared absolute and relative tolerances;
- strict-onset candidates and confidence values;
- normalized note identities and onset times;
- rolling revisions, commits, and retractions; and
- the untouched final-pass note set.

If the ONNX form differs materially, compare the official TensorFlow.js model
as a second browser lane before considering a new export. Do not tune decoder
thresholds to hide a model-conversion discrepancy.

## Proposed Browser Architecture

```text
static HTTPS / localhost origin
        |
        +---- service worker
        |       cache application, model, WASM, renderer, and fonts
        |
        v
AudioWorklet
  source sample + float PCM block
        |
        v
capture / inference Web Worker
  continuity check + source clock
        |
        +----> lossless session stream ----> OPFS
        |
        v
deterministic 22,050 Hz resampler
        |
        v
rolling 43,844-sample window scheduler
        |
        v
ONNX Runtime Web WASM
        |
        v
strict-onset decoder + room gate + reconciler
        |
        v
normalized lifecycle events ----> existing keyboard / staff UI
        |
        v
Stop: full-file inference + final reconciliation
        |
        v
local review + WAV / MIDI / JSON / evidence-bundle downloads
```

### Capture And Scheduling

Keep the `AudioWorklet` deliberately small. It should copy or transfer
sample-indexed audio blocks without running resampling, model inference,
decoding, storage, or UI work in the audio render callback.

A dedicated worker should own:

- continuity checks and the source-sample timeline;
- bounded capture and model queues;
- deterministic resampling to Basic Pitch's 22,050 Hz input;
- the rolling window and 250 ms scheduling policy;
- inference, decoding, gating, and reconciliation;
- source-onset-to-emission timing; and
- streaming session/evidence writes.

The existing loopback WebSocket protocol can disappear from the product, but
its useful invariants must remain. Gaps, duplicates, reordering, queue growth,
sample-rate changes, and a truncated Stop tail must still be explicit errors
or named recovery behavior.

Musical time must remain `source_sample / source_sample_rate`. Removing the
server removes browser-to-host clock fitting, but does not authorize deriving
event time from worker completion or paint time. Capture-to-paint latency can
use a browser monotonic clock observation attached to each sample-indexed
block.

### Model Runtime

Use ONNX Runtime Web's single-thread WASM execution provider for the first
portable baseline:

- it already loaded the exact checked-in dependency artifact;
- it does not require WebGPU;
- it can run in or be proxied to a worker; and
- it avoids making cross-origin isolation a prerequisite for correctness.

SIMD may be selected by runtime feature detection. WASM multithreading is an
optional optimization only after the single-thread result is correct.
ONNX Runtime's
[`numThreads` documentation](https://onnxruntime.ai/docs/tutorials/web/env-flags-and-session-options.html)
notes that browser multithreading requires a cross-origin-isolated page.
That normally requires `Cross-Origin-Opener-Policy` and
`Cross-Origin-Embedder-Policy` response headers. Static hosts can supply those
headers, but requiring them would make deployment less portable.

WebGPU may become an opt-in fast path after it reproduces the WASM output. It
must not be the only path because current browser coverage is narrower,
especially on Safari and iOS.

### Decoder, Gate, And Reconciliation

Do not use the official TypeScript decoder unchanged. Port the selected
atpiano behavior from:

- [`decoder.py`](../../src/atpiano/decoder.py);
- the rolling processor in [`live.py`](../../src/atpiano/live.py); and
- [`reconcile.py`](../../src/atpiano/reconcile.py).

The browser path must preserve:

- explicit learned-onset peaks at threshold 0.6;
- disabled frame-inferred onsets and melodia fallback;
- decoder-origin and native-confidence evidence;
- one-second room calibration and the current onset-energy gate;
- stable event identities and increasing revisions;
- provisional, committed, and retracted lifecycles;
- declared window guards and commit horizon; and
- a separately named final-pass reconciliation.

Array and signal operations are small enough to implement with typed arrays.
Compiling the Python application wholesale through Pyodide would retain large
scientific dependencies, still not make Core ML available, and obscure the
runtime boundary. It is not the recommended first path.

### Final Pass And Exports

On Stop, the worker should:

1. flush and hash the exact captured PCM;
2. close the lossless local recording;
3. run overlapping full-file inference with the selected browser model;
4. decode both the strict live interpretation and the named stock/full-file
   interpretation as required by the product contract;
5. reconcile rolling identities with final notes;
6. generate MIDI, normalized JSON, timing evidence, and a compact report; and
7. offer the recording and evidence bundle as explicit downloads.

Byte-for-byte MIDI parity with Python is not a useful requirement when a
different MIDI serializer is used. Require raw-model tolerances, normalized
note parity, sample/time parity, and a declared serialization version.

Spotify's TypeScript library already uses browser-compatible MIDI code and is
implementation evidence. Atpiano should still preserve its own normalized
note-event artifact as the canonical comparison boundary.

## Local Storage And Evidence

The browser
[`origin private file system`](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)
(OPFS) is the leading storage boundary. It supports worker access and
high-performance in-place writes, but it is private to one origin and subject
to quota and eviction. Clearing site data removes it.

The page should:

- report `navigator.storage.estimate()` before capture;
- request durable storage with
  [`navigator.storage.persist()`](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist);
- state whether the request was granted;
- never treat browser storage as the user's only durable copy;
- provide explicit export and delete controls; and
- make incomplete or evicted sessions visible rather than silently missing.

The current host retention policy cannot move unchanged. Two recent two-minute
jobs were about 274 MiB each, including roughly 117 MiB of overlapping native
windows. The raw output of one model window is approximately 302,720 bytes
before container overhead or compression:

```text
172 frames × (88 note + 88 onset + 264 contour) × 4 bytes
= 302,720 bytes
```

Retaining hundreds of overlapping windows is valuable research evidence but a
poor default product policy. Separate two modes:

- **ordinary local use**: retain the lossless PCM once, normalized events,
  timing summaries, gate decisions, final output, and enough provenance to
  reproduce the result; and
- **diagnostic capture**: opt in to raw per-window arrays, check available
  quota first, stream rather than accumulate in memory, and offer immediate
  evidence-bundle export.

Do not discard model-native arrays before the browser parity and decoder work
is complete. Choose compaction from measured redundancy and re-decode needs,
not only from file size.

## Static And Offline Packaging

The built site should vendor and version every required runtime asset:

- application HTML, CSS, and JavaScript;
- capture and inference workers;
- ONNX Runtime JavaScript and WASM files;
- the selected model artifact and its checksum;
- OpenSheetMusicDisplay and notation fonts if score rendering remains; and
- a manifest describing licenses and exact versions.

The current page loads OpenSheetMusicDisplay from a CDN. OSMD is itself a
browser TypeScript/JavaScript renderer and can be bundled locally; its
[project documentation](https://github.com/opensheetmusicdisplay/opensheetmusicdisplay)
describes direct browser MusicXML rendering. A service worker should pre-cache
the complete versioned application shell and runtime assets. The offline test
must disable the network rather than merely observe that a warm browser
usually uses its HTTP cache.

An update must be atomic from the application's perspective. Do not combine a
new decoder with an older cached model or WASM runtime. Retain the previous
cache until the new version has installed and its manifest has been verified.

## Notation Boundary

Rendering MusicXML is browser-native; generating a readable score from
performance timing is not yet solved by this project.

The current generator depends on Python, NumPy, Partitura, pretty_midi, lxml,
SciPy, and scikit-learn. Moving those dependencies through a Python WASM
runtime would add substantial size and complexity while preserving a
Partitura baseline that failed the first readability review.

Therefore:

- keep the accepted live onset staff in the first browser-only deployment;
- vendor OSMD only if there is useful MusicXML to render;
- retain MusicXML import and download as browser-native operations;
- do not block browser transcription on porting Partitura; and
- resume score-generation work under `performance-to-notation`, where a
  browser-native or separately justified converter can be evaluated on
  readability.

Ivory remains an optional external oracle. It is inherently outside a
no-network, fully local deployment and must never become a hidden dependency.

## Privacy And Security Properties

A browser-only deployment can make a strong and inspectable privacy claim:

- microphone PCM does not leave the device;
- the model and all inference execute locally;
- no recording, note, or telemetry endpoint is required; and
- users choose when to export an artifact.

The implementation should enforce the claim:

- vendor dependencies instead of fetching them at runtime;
- use a restrictive content security policy;
- avoid analytics and remote fonts;
- show network/offline state;
- enumerate every allowed external navigation, such as an optional Ivory link;
  and
- verify with browser developer tools that capture and transcription make no
  network requests.

The model, WASM runtime, and third-party JavaScript become client-delivered
supply-chain artifacts. Record their versions, licenses, hashes, and build
origin in the static manifest.

## Validation And Decision Gates

### Gate 1: Real Browser Model Parity

Build a minimal static replay page before moving live behavior. In current
Chrome, Safari, and Firefox on the target Mac:

- load the exact hashed ONNX artifact with single-thread WASM;
- replay the deterministic aligned fixture and retained piano recordings;
- preserve the raw outputs from every tested backend;
- compare raw arrays, strict candidates, normalized notes, and final output;
- report cold load, warm inference, memory, and queue high-water marks; and
- explain any backend-specific difference rather than retuning around it.

Also run at least one representative phone or lower-powered computer before
claiming broad client-side viability.

Continue if the browser lane reproduces acceptable note behavior and processes
the selected hop without sustained queue growth. A 33.4 ms host smoke result
is encouraging evidence, not this gate's completion.

### Gate 2: Rolling Live Port

Replace only the host execution boundary while preserving the current
contracts:

- identical sample-indexed capture input;
- identical scheduler, guards, decoder, gate, and reconciler policy;
- deterministic WAV replay before microphone use;
- source-onset-to-worker-emission and source-onset-to-paint timing;
- explicit gaps, queue overflow, Stop flush, and page-close behavior; and
- comparison with the current host on silence, noise, repeated notes, chords,
  pedal, bass, treble, and target-piano clips.

Continue if the live view remains useful, its quality does not regress beyond
a declared tolerance, and inference does not interfere with audio capture or
painting.

### Gate 3: Final Pass, Persistence, And Export

Require:

- exact captured PCM frame count and hash;
- browser final-pass parity against direct browser replay of the same WAV;
- named live-versus-final reconciliation;
- bounded memory during a two-minute capture;
- correct quota, denied-persistence, eviction, and partial-write behavior;
- valid WAV, MIDI, JSON, and evidence-bundle downloads; and
- recovery or an explicit loss report after reload during capture.

### Gate 4: Static Offline Deployment

Serve only versioned static assets and then:

- install the PWA;
- disable all network interfaces or block all requests;
- reload and complete capture, live inference, Stop, final pass, review, and
  export;
- verify that no CDN asset is required;
- test cache upgrade and rollback behavior; and
- repeat microphone permission denial and revocation.

Only after this gate may the project claim that the user-facing path works
offline with no application server.

## Recommended Direction

Hold. Do not open the browser WASM replay tactical yet.

The measured bottlenecks are context, score-inference quality, and beat
inference on rubato — none of which a browser runtime affects, and all of which
it constrains. The accepted transcription direction remains
[`009-three-phase-unbounded-sessions.md`](../tactical/009-three-phase-unbounded-sessions.md),
which is host-executed and free to select the best available model. The
accepted product architecture is the hosted service plus local/offline Tauri
runtime recorded in
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md).

This topic becomes relevant again under one of two conditions:

1. a model lane small enough for WASM is shown to be good enough for the
   provisional zone, making a browser-only build of Lane A worthwhile; or
2. a separately measured client-side executor would materially improve hosted
   cost, privacy, latency, or low-friction offline access beyond the accepted
   desktop path.

If it resumes, the earlier sequence still applies: one bounded tactical for
browser WASM replay and parity — a static page that runs retained PCM through
the exact ONNX artifact in real browsers and produces a machine-comparable raw
and decoded result — before any scheduler, storage, or packaging work.

### Execution backend is now open

With CUDA, ROCm, MPS, and remote hosts all acceptable, the existing guardrail
becomes more load-bearing rather than less: accelerator-specific code stays
behind the model-adapter boundary, and every backend must be validated against
a known-good CPU result. The MIDI2ScoreTransformer MPS failure recorded in
[`008-score-pipeline-bakeoff.md`](../tactical/008-score-pipeline-bakeoff.md) is
the reason — it produced an empty score and exited zero. The failure mode for a
bad backend is silence, not a crash.

A remote accelerator additionally reintroduces transport as a live-path
concern: raw LAN PCM is the measured control, and any codec is an experiment
against it, not a shortcut.

## Open Questions

- Which browsers and minimum devices are product requirements?
- Does the ONNX artifact reproduce acceptable real-audio output relative to
  Core ML, or should the official TensorFlow.js model be the browser baseline?
- Is single-thread WASM sufficient on the slowest target, avoiding
  cross-origin-isolation headers?
- Which deterministic resampler reproduces the current 22,050 Hz input closely
  enough across browsers?
- How much raw window evidence should ordinary users retain, and how is
  diagnostic mode communicated?
- Should local sessions survive browser data clearing only through explicit
  exported bundles?
- Is static HTTPS/PWA installation sufficient, or is a small desktop wrapper
  required for users who will not run or trust a local static origin?
- Does the first browser-only product omit score generation while retaining
  MusicXML import and rendering?
- How should browser lifecycle suspension, phone screen lock, thermal
  throttling, and memory pressure be reported?
