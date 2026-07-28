# 045 — Client Deployment Continuity

Topic: home-hosted-family-sharing

Status: **implemented and locally validated on 2026-07-28; live restart
pending.**

## Goal

Keep an open Atpiano tab understandable and recoverable when the on-demand
family service rebuilds its Vite frontend. A deployment must not turn a
missing old JavaScript chunk into a generic notation-rendering failure or
silently serve HTML as JavaScript.

Use four complementary layers:

1. exact static-asset routing and cache policy;
2. a direct update-and-reload notice when an old chunk cannot load;
3. lightweight client build polling; and
4. bounded retention of recent hashed assets.

This is a small-service continuity contract, not a general automatic-update
system or a service-worker cache.

## Observed Failure

An open production tab loaded one Vite entry bundle, then the launchd service
restarted and ran another `vite build`. Vite's `emptyOutDir: true` removed the
old hashed OpenSheetMusicDisplay chunk. When the old tab later opened a score,
its dynamic import requested the old filename.

The authenticated FastAPI catch-all did not return a missing-resource
response. It served the current `index.html` with HTTP 200 and
`Content-Type: text/html`. The browser rejected that response as JavaScript,
and the score component reduced the exception to `Notation rendering failed`.
The score and alignment artifacts were healthy.

## Layer 1: Exact Assets And Cache Policy

Requests below `/assets/` and requests for explicit root files must resolve to
real files. Missing files return HTTP 404 and must never fall through to the
SPA shell. Extensionless application routes may continue to receive
`index.html`.

Apply explicit cache policy:

- hashed `/assets/*` responses use
  `Cache-Control: public, max-age=31536000, immutable`;
- `index.html`, `/`, `/client-version.json`, and stable-name root assets use
  `Cache-Control: no-store`; and
- missing asset responses retain `nosniff` and return a non-HTML error body.

Tests must cover a current hashed asset, a missing hashed asset, the version
document, a stable root file, and an extensionless SPA route.

## Layer 2: Chunk-Failure Recovery

The OpenSheetMusicDisplay dynamic import must retain its exception long enough
to distinguish a deployment/chunk acquisition failure from invalid MusicXML
or an engraving exception.

A recognized chunk failure raises one application-level update notice:

```text
Atpiano was updated. Reload this page to continue.
```

The notice includes an explicit **Reload** action. It supersedes the generic
notation error for that failure, while genuine MusicXML or renderer failures
retain their existing score-local diagnostic.

The application never reloads automatically. Recording, upload settlement,
score generation, playback, reader position, and other in-memory activity
must not be interrupted without a person choosing the reload action.

## Layer 3: Build Polling

Each production build emits `/client-version.json` with:

- schema `atpiano.client-version.v1`;
- an opaque build ID; and
- the UTC build time.

The same build ID is embedded in that build's JavaScript. The update monitor
fetches the document with `cache: "no-store"`:

- once after application bootstrap;
- every 60 seconds while the tab remains open; and
- when the window regains focus or the document becomes visible.

A different valid build ID shows a non-blocking update notice with the same
explicit reload action. Network, sleep, shutdown, authentication, or malformed
response failures do not replace the application with an error; the next poll
may recover.

The version document is public because it contains no repository path,
credentials, user data, or source-control details.

## Layer 4: Bounded Hashed-Asset Retention

Vite no longer empties the output directory on each build. A build plugin
records the exact `/assets/` files emitted by each build and retains the
current generation plus the two preceding generations.

After a successful build:

1. append the current build and exact asset set to local build history;
2. retain the newest three complete generations;
3. remove hashed files referenced only by dropped generations;
4. remove untracked hashed files rather than allowing indefinite growth; and
5. atomically replace the local history document.

On the first continuity-aware build, existing hashed output is treated as one
legacy generation so tabs opened immediately before the upgrade receive a
grace period. Build history is local generated state and stays outside Git.

Retention lets an old entry bundle finish a later lazy import. It does not
promise that an arbitrary old client remains compatible with the current
`/api/v1` server. Polling and the reload notice remain the authoritative
convergence path.

## Out Of Scope

- automatic page reload;
- WebSocket deployment notifications;
- a service worker or offline application cache;
- long-term hosting of every historical bundle;
- signed releases or a desktop auto-updater;
- zero-downtime server-process replacement; and
- compatibility promises beyond the versioned application API.

## Implementation Sequence

1. Add the build ID, version document, and bounded Vite asset history.
2. Correct FastAPI exact-file routing and cache headers.
3. Add the update monitor and reload notice.
4. Classify dynamic-import acquisition failures without hiding real engraving
   failures.
5. Add build-history, server-route, polling, and component regressions.
6. Build twice and prove the prior generation remains while older generations
   are pruned in a synthetic build-history test.
7. Restart the already-active family service and verify the public shell,
   version document, cache headers, protected capabilities, and missing-asset
   404 behavior.

## Acceptance

- A missing `/assets/*.js` returns HTTP 404, never HTML with HTTP 200.
- Current hashed assets are immutable and shell/version resources are not
  stored.
- The JavaScript build ID matches `/client-version.json`.
- Focus, visibility, and interval polling detect a newer valid build.
- Poll failures leave the current application usable.
- No deployment state causes an automatic reload.
- A failed old OSMD import presents a direct reload action instead of generic
  notation failure.
- The newest three hashed generations survive and older unreferenced files
  are removed.
- Build history and browser credentials remain outside Git and reports.
- Frontend tests, TypeScript, Python server tests, the production build, and
  the migration regression gate remain green.

## Implementation Evidence

The Vite build now derives one deterministic client ID from its production
inputs, emits the matching version document, and coalesces repeated builds of
unchanged inputs instead of consuming retention generations. Its generated
history remains ignored beside the application and atomically retains exact
asset lists for three distinct client builds.

The shared client mounts one update monitor across authenticated, bypass, and
desktop bootstrap paths. It polls on startup, every 60 seconds, focus, and
visibility restoration. Poll failures are silent and no state causes an
automatic reload. A recognized OpenSheetMusicDisplay chunk acquisition
failure raises the urgent reload notice; other engraving exceptions retain
the existing notation diagnostic.

Local validation passed:

- 101 Vitest frontend tests;
- nine TypeScript node tests, including generation pruning and unchanged-build
  coalescing;
- TypeScript checking;
- 19 family-server and share-service Python tests;
- Ruff over the changed Python paths;
- Git whitespace;
- two consecutive production builds with the same client ID and asset names;
  and
- direct inspection proving that ID appears in the current entry JavaScript
  and matches `client-version.json`.
