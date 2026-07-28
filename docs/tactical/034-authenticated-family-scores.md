# Authenticated Family Scores

Topic: home-hosted-family-sharing
Topic: performance-to-notation

Status: **implemented and live on 2026-07-28.**

## Outcome

Make committed score generation and rendering a default capability of the
authenticated home-hosted family application when the configured pinned
score runtime is valid.

The user considers the application unusable without scores. The earlier
Tactical 033 review build suppressed scoring as a provisional public-release
boundary. That suppression was appropriate before authentication, but it is
not the accepted product behavior for the private owner-authorized Mac/Pi
deployment.

This change does not publish a model pack, create a downloadable application,
open anonymous score routes, or resolve the upstream source/checkpoint
license. It accepts the already-installed internal runtime for private,
authenticated home use.

## Implementation

1. `family-server` accepts `--score-runtime`, defaulting to the existing
   ignored `results/midi2score-runtime`.
2. The FastAPI composition derives `score_available` from the configured
   runtime's pinned manifest and asset checks. A missing or invalid runtime
   still degrades to `score_available=false`.
3. Score jobs, variants, MusicXML, score-input MIDI, and alignment artifacts
   remain protected by the existing workspace membership and write-role
   checks.
4. The macOS launchd service carries and reports `ATPIANO_SCORE_RUNTIME`.
   Authenticated family mode uses it by default.
5. An explicit rollback to the unauthenticated legacy composition continues
   to use the deliberately absent `results/public-score-disabled` runtime
   unless an operator separately overrides that legacy-only setting.
6. `atpiano family-check --require-score` fails unless the selected session
   exposes a readable selected MusicXML artifact. It supports both in-process
   and live HTTPS verification with the bounded local-operator session.

## Validation

- The installed runtime manifest reports the pinned repository commit,
  checkpoint SHA-256, CPU execution, and `internal_use_only=true`.
- In-process authenticated validation over retained session
  `20260727T185541-a2298f1afaaf` reported `score_available=true`, ten visible
  artifacts, and a 701,346-byte partwise `score.musicxml`.
- The complete regression passed: 199 Python tests, 56 frontend tests,
  TypeScript, the production build, Ruff, Bash syntax, and Git whitespace.
- The active launchd service restarted with family authentication enabled and
  `Score runtime: results/midi2score-runtime`.
- The same operator check passed through
  `https://atpiano.graehlarts.com`, read the selected MusicXML and protected
  MP3, logged out, and verified session revocation.
- Anonymous requests still receive HTTP 401 from the capability endpoint.

## Commit

- `14cceb0` — enable scoring in the authenticated family service.

## Continuing Boundary

The configured runtime is a large isolated Python 3.11 research environment
with provisional upstream licensing. Private authenticated use is accepted;
ordinary desktop distribution, public model downloads, and a general hosted
score service remain blocked on license resolution or a licensed replacement.
Footprint reduction remains owned by
[`desktop-score-runtime-footprint.md`](../topics/desktop-score-runtime-footprint.md).
