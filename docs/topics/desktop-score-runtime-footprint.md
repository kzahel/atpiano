# Desktop Score Runtime Footprint

Topic: desktop-score-runtime-footprint

Status: **a user-acquired score runtime is now planned for the first public
macOS arm64 and Windows x86_64 desktop builds as of 2026-08-23.** The published
applications and GitHub Release must still exclude the MIDI2ScoreTransformer
repository and checkpoint. Each application may include a pinned
platform-specific support environment with best-effort dependency provenance,
plus a shared acquisition controller that downloads the exact model source and
checkpoint only after an explicit education/research-use acknowledgement.
Tactical
[`052-user-acquired-score-runtime.md`](../tactical/052-user-acquired-score-runtime.md)
owns that implementation, and tactical
[`053-windows-desktop-release-lane.md`](../tactical/053-windows-desktop-release-lane.md)
owns Windows staging and installed acceptance. The complete ignored internal
runtime remains the behavioral baseline, not a distributable artifact.

## Scope And Relationship

This topic owns:

- installed and compressed size evidence for the desktop score runtime;
- the boundary between necessary inference code and training, evaluation,
  examples, corpora, download clients, and duplicated packages;
- dependency consolidation between the ordinary desktop runtime and the
  isolated score subprocess;
- inference-checkpoint reduction that preserves the exact FP32 weights;
- user-initiated acquisition, installation, compatibility, provenance, and
  removal of score assets outside the signed App; and
- validation gates for proving that size work does not change score behavior,
  source alignment, failure isolation, or bundle immutability.

[`performance-to-notation.md`](performance-to-notation.md) continues to own
score quality, semantics, MusicXML, and source alignment.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
continues to own the desktop process boundary, model-pack architecture,
distribution, and license gates. Tactical
[`031-internal-desktop-score-runtime.md`](../tactical/031-internal-desktop-score-runtime.md)
is the implemented baseline and execution record. The public release boundary
and installed update campaign remain owned by
[`public-desktop-release.md`](public-desktop-release.md) and tactical
[`051-signed-macos-update-lane.md`](../tactical/051-signed-macos-update-lane.md),
with the Windows half in tactical 053.

This direction authorizes planning and implementation of acquisition support;
it does not authorize Atpiano to distribute or mirror the
MIDI2ScoreTransformer repository or checkpoint, claim upstream permission,
quantize or derive a new model artifact, or publish a desktop binary before the
separate release hold is approved. For this noncommercial proof of concept,
removing evaluation-only `ScoreTransformer` and MUSTER dependencies is a later
optimization rather than a publication prerequisite.

## Measured Baseline

The final ignored internal application is:

```text
results/desktop-internal-score/Atpiano-Internal-Score.app
```

| Item | Bytes | Approximate size |
|---|---:|---:|
| Complete internal score application | 2,361,066,073 | 2.36 GB / 2.20 GiB |
| Score runtime addition | 1,316,271,921 | 1.32 GB |
| Installed score packages | 884,944,009 | 884.9 MB |
| Released checkpoint | 389,829,880 | 389.8 MB / 371.8 MiB |
| Score Python, source, and manifests outside those two groups | 41,498,032 | 41.5 MB |
| Score-free R5 application | 1,044,680,287 | 1.04 GB |
| Score-free R5 ZIP | 345,419,478 | 345.4 MB |

A read-only file-by-file gzip level-6 simulation measured 949,554,141 bytes
for the internal application payload. That is a useful download-size estimate,
not a created or approved distribution archive. ZIP or DMG metadata and
compression details would move the final value.

The score runtime is large primarily because it is a second standalone Python
environment. Package-name intersection with the normal desktop runtime totals
721,513,819 score-runtime bytes. The largest duplicates are:

| Package | Score-runtime bytes | Normal runtime |
|---|---:|---|
| Torch 2.13.0 | 431,859,085 | same version already present |
| llvmlite 0.48.0 | 129,778,302 | same version already present |
| NumPy 1.26.4 | 40,201,999 | same version already present |
| pandas 3.0.5 | 25,588,044 | pandas 2.3.3 already present |
| Matplotlib 3.11.1 | 21,366,572 | Matplotlib 3.10.9 already present |
| SymPy 1.14.0 | 17,118,720 | same version already present |
| Pillow 12.3.0 | 13,266,148 | same version already present |
| FontTools 4.63.0 | 11,367,928 | same version already present |
| Numba 0.66.0 | 7,510,528 | same version already present |
| Pretty MIDI 0.2.11 | 6,127,765 | same version already present |

Some version differences are harmless only if the packages are absent from
the inference path. Consolidation must prove compatibility; matching a
distribution name is evidence of duplication, not permission to delete it.

## Checkpoint Evidence

The released `.ckpt` is a stored PyTorch ZIP containing a full Lightning
training checkpoint. Inspection with the pinned runtime found:

| Payload | Tensor bytes |
|---|---:|
| `state_dict` model weights | 130,382,056 |
| `optimizer_states` | 259,192,044 |

It also contains epoch, global-step, loop, callback, scheduler, Lightning
version, and hyperparameter metadata. The optimizer state accounts for nearly
all bytes beyond the model.

The first reduction candidate is therefore an inference-only artifact
containing the exact FP32 state dictionary and the minimal configuration
required to reconstruct the model. It should be roughly 130–135 MB without
quantization. This is artifact repackaging, not a model-quality change, but it
must still prove:

- every parameter key, dtype, shape, and tensor value is identical;
- the same input tensors produce identical model outputs;
- the pinned replay produces equivalent MusicXML and v2 alignment; and
- provenance retains the original release URL and SHA-256 plus the derivation
  command and derived-artifact SHA-256.

## Actual Inference Imports

An instrumented run of the final committed-score snapshot completed
successfully while recording imported distributions. The packaged environment
contains 62 distributions; that run loaded 45. A loaded-module trace is
directional evidence, not proof that an omitted package is safe for every
input or lazy branch.

The trace and source inspection expose several avoidable import edges:

- upstream `utils.py` eagerly imports `muster` and
  `score_transformer.score_similarity` even though score inference only calls
  `infer`;
- `score_transformer` imports Numba, which pulls in the 129.8 MB llvmlite
  library for an evaluation metric not used by inference;
- the model base class inherits from PyTorch Lightning and the adapter uses
  `load_from_checkpoint`, pulling training-framework and TorchMetrics code
  into inference;
- TorchMetrics imports Matplotlib plotting support even though the score path
  emits MusicXML rather than plots;
- the upstream requirements install pandas and joblib for dataset and
  evaluation utilities that the measured inference run did not load; and
- Hugging Face download and Xet clients are unnecessary when the model code
  and checkpoint are pinned local assets.

This suggests an inference-specific adapter should import only tokenizer,
model, decode, post-processing, and MusicXML code rather than importing the
research package's general training/evaluation utility surface.

## Candidate Reductions

Savings below overlap and must not be summed blindly.

### 1. Derive an inference-only checkpoint

Remove optimizer and trainer state while retaining exact FP32 weights and
configuration.

- Expected saving: about 259 MB installed and nearly the same in the download
  because the released tensor archive uses stored entries.
- Risk: low if tensor identity and full output parity are checked.
- Recommended first step.

### 2. Reuse the normal desktop Python runtime

Keep score generation in its own subprocess, but execute it with the bundled
Python 3.10 runtime and a small score-specific package overlay. Process
isolation does not require a second interpreter and second Torch installation.

- Measured duplicated package opportunity: 721.5 MB installed.
- Risk: medium until the custom music21, Transformers/RoFormer code, and
  derived checkpoint execute under Python 3.10.
- pandas, Matplotlib, and NetworkX version differences should disappear from
  the score contract by removing their unnecessary inference imports rather
  than forcing upgrades into the main runtime.
- The score subprocess must retain its explicit CPU, cache, capability,
  timeout, and failure-isolation boundaries.

### 3. Separate inference from research utilities

Copy or adapt the minimal pinned inference functions behind Atpiano's existing
score adapter instead of importing upstream evaluation modules.

Likely removable from the separate score environment:

- pandas and joblib dataset paths;
- `muster` and `score_transformer` evaluation metrics;
- Numba and llvmlite when they are no longer reached by evaluation imports;
- the `lightning` metapackage; and
- source evaluation, dataset, chunking, and command-line utilities.

If the main runtime is reused, Numba and llvmlite remain installed for the
transcription stack but cease to be incremental score cost.

### 4. Load the model without Lightning

Reconstruct the pinned RoFormer as a plain `torch.nn.Module`, apply the
derived state dictionary, and retain only the inference methods.

This may remove PyTorch Lightning, Lightning, TorchMetrics, plotting imports,
and associated optional packages. It is a moderate code change because
checkpoint configuration and state-key mapping become Atpiano-owned
compatibility code. Exact tensor and output parity are mandatory.

### 5. Prune data and general-purpose model code

Current high-value payloads include:

- approximately 69,860 KiB allocated under `music21/corpus`; and
- approximately 37,876 KiB under `transformers/models`, while only RoFormer
  is used.

The custom music21 parser, stream, MIDI, MusicXML, pitch, duration, meter,
clef, key, expression, and metadata paths remain required. Corpora, examples,
OMR, IPython integration, alternate renderers, and unrelated model families
are candidates only after import and multi-fixture validation.

A stronger later option is to vendor the small pinned RoFormer subset rather
than ship general Transformers. That increases maintenance and license-review
responsibility and should follow, not precede, the simpler reductions.

### 6. Keep the model outside the initial installer

This is now the accepted first-public-release direction. The base desktop
download remains free of MIDI2ScoreTransformer source and weights. It offers
an explicitly acquired, checksummed runtime only when a person enables score
generation. This improves initial download size but does not by itself reduce
total installed bytes. The exact support-layer footprint remains subject to
the dependency preflight and measurement in tactical 052.

### 7. Treat quantization as a separate model experiment

FP16 or INT8 weights could reduce the remaining roughly 130 MB inference
state, but they may change CPU support, speed, and notation output. They
require a new model identity and quality evidence across the transcription
research guardrail cases. Quantization is not packaging cleanup.

## Public User-Acquired Runtime Contract

The acquisition feature is desktop-only and must ship in both macOS arm64 and
Windows x86_64 CPU applications for the first release. Hosted web compositions
continue to report only the server's operator-installed score capability and
must not expose the desktop download dialog.

### Disclosure And Acknowledgement

The unavailable score view offers **Enable score generation**. It opens a
modal dialog before any network request or directory creation. The release
candidate should use this substance, with final copy reviewed in the rendered
application:

> MIDI2ScoreTransformer is an optional research model. Its upstream source and
> checkpoint do not currently include an explicit license. Atpiano does not
> include or license those assets. If you have the right to use them, Atpiano
> can download the exact upstream files for education or research use only and
> run them locally on this device. Do not use them commercially or redistribute
> them. The download is about 390 MB before supporting files and needs
> additional installed space.

The dialog links to the user-acquired MIDI2ScoreTransformer repository, the
checkpoint release, paper record, and Atpiano's tracked acquisition contract.
It states that downloaded Python source will execute locally. The primary
action remains disabled until the person checks **I understand this notice and
want to download the optional research model**. Cancel performs no network or
filesystem mutation.

The acknowledgement is an informed-use record, not an upstream license grant.
It is retained only on the device and is never attached to update checks or
other requests. Its receipt records the notice version, acquisition-contract
ID, App version, accepted UTC time, exact upstream URLs, and expected hashes;
it contains no user, document, hostname, or installation identity. Any change
to the notice or asset contract requires acknowledgement again.

### Asset And Storage Boundary

One tracked `atpiano.score-acquisition.v1` document in each signed App owns:

- an immutable acquisition-contract ID and notice version;
- the exact HTTPS MIDI2ScoreTransformer repository, commit, source-archive URL,
  SHA-256, byte expectation, checkpoint release, and allowed redirect hosts;
- archive entry, extracted-tree, symlink, file-count, and expanded-byte bounds;
- the compatible Atpiano score-pipeline revision and signed support-layer ID;
- the minimum free-space requirement; and
- the manifest fields required before the sidecar may report score capability.

GitHub-generated source archives must be downloaded and hashed during the
implementation preflight. If the same commit URL later yields different bytes,
installation fails closed until a signed Atpiano release deliberately updates
the contract. Atpiano does not proxy the source or checkpoint through
`graehlarts.com`, GitHub Releases, or the updater service.

Mutable score assets live outside `Atpiano.app` under:

```text
app_data_dir()/score-runtimes/
  .staging/<operation-id>/
  <acquisition-contract-id>/
app_config_dir()/score-runtime.json
```

The active manifest is published only after complete download, bounded
extraction, checksum, structure, import, and score-smoke validation. A failed,
cancelled, or interrupted acquisition leaves no active pointer and cannot make
the ordinary application unavailable. Stale staging data is recoverably
cleaned on the next launch.

Each signed application may contain a platform-specific pinned Python 3.11
score-support environment after removing the MIDI2ScoreTransformer repository
and checkpoint and recording exact package provenance and known license status.
The already-proven macOS environment is the first reference; the Windows x64
environment must independently prove dependency resolution and identical
retained outputs. This is a deliberate, limited proof-of-concept risk
acceptance for the currently unlicensed `ScoreTransformer` and MUSTER helper
packages; Atpiano makes no license claim for them. The App must not run `uv`,
`pip`, or `git` on the user's machine. The published package audit continues to
reject the main model repository, checkpoint, and internal manifests that
would imply the model itself was bundled.

### Lifecycle And Updates

Acquisition has explicit `unavailable`, `disclosure`, `checking-space`,
`downloading`, `verifying`, `installing`, `ready`, `error`, and `removing`
states. Progress distinguishes source, checkpoint, and local validation.
Errors are bounded, credential-free, and actionable; retry reuses only fully
verified immutable inputs.

Download, activation, and removal use the desktop composition rather than the
authenticated Python API. The sidecar receives no general network-acquisition
authority. Acquisition cannot begin while capture is requesting, warming,
recording, or stopping, while settlement/import is active, while a score job
is active, or while a desktop update is installing.

Because the current desktop runtime fixes its loopback address, credential,
and score capability at launch, successful installation does not hot-swap the
sidecar. The UI offers **Relaunch to enable scores** after validation. Relaunch
uses the existing install blockers and graceful sidecar shutdown. Startup
selects only a compatible external runtime and otherwise degrades to
`score_available=false` with an explanation and recovery action.

Signed App updates never silently acquire, modify, or delete the external
runtime. A compatible `0.1.0 -> 0.1.1` update preserves its active manifest and
acknowledgement. An incompatible update leaves the application usable, disables
score generation, and offers a deliberate reacquisition or removal path.
Removal stops using the runtime before deleting its versioned directory and
does not delete sessions, source MIDI, MusicXML, alignments, or exports.

## Recommended Sequence

1. Record a time-boxed exact inventory of the already-proven Python 3.11 score
   environment, including known absent licenses, without making cleanup a
   publication blocker.
2. Stage that support environment without the MIDI2ScoreTransformer repository
   or checkpoint and prove it can consume those assets from an external root.
3. Freeze the acquisition document, disclosure version, exact source archive,
   hashes, redirect policy, size bounds, and external-runtime manifest.
4. Implement transactional desktop acquisition, on-device acknowledgement,
   validation, relaunch activation, removal, and safe degradation.
5. Add the rendered dialog and stateful score-unavailable/ready management UI.
6. Build and audit the exact signed macOS arm64 and Windows x86_64 applications,
   then prove clean acquisition and matching score output on both.
7. Prove external-runtime preservation through the real signed
   `0.1.0 -> 0.1.1` updater campaign on both operating systems.

Python 3.10 consolidation, removal of eager ScoreTransformer/MUSTER imports,
checkpoint derivation, broader dependency pruning, and quantization remain
later optimizations. The first public flow must acquire the exact released
checkpoint rather than an Atpiano-derived weight artifact.

The preliminary, non-accepted projection is approximately 1.25–1.4 GB
installed for the complete application and roughly 500–650 MB compressed
without quantization. A bounded tactical must replace that estimate with
measured artifacts.

## Validation Contract

Every reduction step must:

- start from the same pinned upstream commit, released checkpoint, and
  committed source-note fixture;
- report exact installed and simulated or real compressed component sizes;
- preserve CPU-only execution with no CUDA, NVIDIA, ROCm, or accelerator
  payload;
- validate exact checkpoint tensors unless the step explicitly declares a new
  model;
- compare model-native token outputs before MusicXML post-processing;
- validate MusicXML structure, pitch preservation, and v2 source alignment;
- exercise repeated notes, dense chords, sustain pedal, low bass, and high
  treble in addition to the golden replay;
- run with networking unavailable and caches redirected outside the bundle;
- retain score failure isolation from capture, review, playback, and export;
- pass native architecture, dependency, symlink, cache, provenance, and
  post-launch immutability audits; and
- leave the ordinary score-free build and archive independently
  reproducible.

The public acquisition slice additionally must:

- prove from clean macOS and Windows application data that no upstream request
  occurs before acknowledgement;
- capture request destinations showing direct upstream acquisition only;
- reject corrupt bytes, oversized or traversal archives, unexpected redirects,
  stale manifests, incompatible pipelines, concurrent acquisition, and
  insufficient disk;
- survive cancellation, process termination, network loss, and App relaunch
  without selecting a partial runtime;
- prove the published DMG, Windows installer, both updater artifacts,
  corresponding-source archives, checksums, and attestations contain no
  MIDI2ScoreTransformer source or checkpoint;
- produce equivalent model tokens, MusicXML, alignment, and provenance on the
  retained score fixtures; and
- exercise install, relaunch, score generation, signed App update, retained
  capability, removal, and score-free degradation in the visible desktop App.

Byte-identical MusicXML is meaningful only for the same source event
identities. Cross-session hashes may differ because MusicXML note IDs encode
session-addressed source event IDs; semantic and alignment comparisons must
account for that contract.

## Open Questions

- Can a later release run the pinned source and custom music21 stack on the
  bundled Python 3.10 interpreter and remove the separate Python 3.11 support
  environment?
- Which score-only packages can be removed once evaluation and training imports
  are separated from inference?
- Can the minimal RoFormer implementation remain sourced from upstream
  without broad Transformers packaging, or should that wait for a licensed
  replacement?
- Can `ScoreTransformer` and MUSTER be removed from inference entirely, and do
  their maintainers later publish explicit license terms?
- What installed/download target is worth the extra maintenance after the
  low-risk checkpoint and duplication reductions land?
- Should an upstream license later appear, and how should a signed release
  change the notice without weakening existing receipt/provenance evidence?
- What source and checkpoint rights apply to any future derived inference-only
  artifact? The current education/research acknowledgement does not answer
  that release question.

## Later Todo — Evaluation Dependency Cleanup

After the proof-of-concept release, separate MIDI2ScoreTransformer inference
from its eager evaluation imports. Atpiano calls `infer()` but not the upstream
`eval()` path that uses `score_similarity` and MUSTER. Prove identical model
tokens, MusicXML, and alignment after lazy-loading or otherwise isolating those
metrics, then remove `ScoreTransformer`, MUSTER/amtevaluation, and dependencies
reachable only through them from the support environment. Measure the size
saving and re-run packaged score parity. If either package remains necessary,
ask its maintainer for explicit license terms. This cleanup is desirable but is
not a prerequisite for the noncommercial proof-of-concept release.

## Next Tactical

Implement
[`052-user-acquired-score-runtime.md`](../tactical/052-user-acquired-score-runtime.md)
and
[`053-windows-desktop-release-lane.md`](../tactical/053-windows-desktop-release-lane.md)
as prerequisites of the first public desktop tag. Stop at the dependency and
support-layout checkpoint only for an explicit upstream prohibition, a direct
maintainer objection, or a technical/security failure. Known missing license
metadata for the evaluation helpers is recorded risk, not a reason to delay the
proof of concept. Do not substitute a derived checkpoint or mirror the main
model content to keep the release schedule.
