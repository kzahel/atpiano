# Desktop Score Runtime Footprint

Topic: desktop-score-runtime-footprint

Status: **measured optimization opportunity as of 2026-07-27.** The current
internal macOS arm64 score build is correct and reviewable, but deliberately
packages the complete proven research environment rather than an
inference-minimal runtime. R5 was accepted on 2026-07-28, but no reduction
tactical is open yet. The build remains internal-only under the provisional
MIDI2ScoreTransformer licensing assumption. The broader packaged-desktop and
managed-hosted programs are deferred; this optimization may proceed as an
independent local tactical when authorized.

## Scope And Relationship

This topic owns:

- installed and compressed size evidence for the desktop score runtime;
- the boundary between necessary inference code and training, evaluation,
  examples, corpora, download clients, and duplicated packages;
- dependency consolidation between the ordinary desktop runtime and the
  isolated score subprocess;
- inference-checkpoint reduction that preserves the exact FP32 weights; and
- validation gates for proving that size work does not change score behavior,
  source alignment, failure isolation, or bundle immutability.

[`performance-to-notation.md`](performance-to-notation.md) continues to own
score quality, semantics, MusicXML, and source alignment.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
continues to own the desktop process boundary, model-pack architecture,
distribution, and license gates. Tactical
[`031-internal-desktop-score-runtime.md`](../tactical/031-internal-desktop-score-runtime.md)
is the implemented baseline and execution record.

This topic does not authorize public distribution, quantization, a model
change, or resumption of the deferred packaged-desktop program.

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

An explicitly acquired, checksummed model pack could leave the base desktop
download near its score-free size and fetch the score artifact only when the
user enables scoring. This improves initial download size but does not reduce
total installed bytes. It also requires the model-pack acquisition, license
notice, recovery, update, and offline policies planned for later desktop work.

### 7. Treat quantization as a separate model experiment

FP16 or INT8 weights could reduce the remaining roughly 130 MB inference
state, but they may change CPU support, speed, and notation output. They
require a new model identity and quality evidence across the transcription
research guardrail cases. Quantization is not packaging cleanup.

## Recommended Sequence

1. Re-export the exact FP32 inference state and prove tensor/output identity.
2. Prove the score adapter under the existing bundled Python 3.10 and Torch
   stack while retaining a separate process.
3. Remove eager evaluation imports and build a minimal package overlay.
4. Prune music21 corpus data and unrelated Transformers payloads one group at
   a time.
5. Replace Lightning checkpoint loading only if the earlier steps leave
   meaningful residual cost.
6. Reconsider optional model acquisition and quantization as separate product
   decisions.

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

Byte-identical MusicXML is meaningful only for the same source event
identities. Cross-session hashes may differ because MusicXML note IDs encode
session-addressed source event IDs; semantic and alignment comparisons must
account for that contract.

## Open Questions

- Does the pinned source and custom music21 stack run unchanged on the bundled
  Python 3.10 interpreter?
- Which score-only package versions genuinely conflict with the main runtime,
  once evaluation and training imports are removed?
- Can the minimal RoFormer implementation remain sourced from upstream
  without broad Transformers packaging, or should that wait for a licensed
  replacement?
- Should the score checkpoint ship inside a future installer or be an
  explicitly acquired model pack?
- What installed/download target is worth the extra maintenance after the
  low-risk checkpoint and duplication reductions land?
- What source and checkpoint rights apply to a derived inference-only
  artifact? The current provisional internal acceptance does not answer that
  release question.

## Next Tactical

When authorized, open one bounded tactical for the first two proof steps:
derive an exact inference checkpoint, then run the unchanged score contract
against the existing Python 3.10/Torch runtime. Stop at a measured
human-review checkpoint before pruning general package payloads or changing
the model. This work is a local optimization and does not require or imply
resuming the deferred managed hosted-service plan.
