# Website-Aligned Application Theme

Topic: application-color-theme

Status: **Complete in source; prepared for signed desktop release `0.1.3`.**

## Objective

Bring the desktop application's color language into line with the public
website while retaining a deliberate, accessible dark option that users can
select and keep across launches.

## Implemented Slice

- Replaced the green/mint application palette with semantic light and dark
  tokens derived from the site's paper, ivory, ink, and piano-felt red system.
- Applied the tokens across the session rail, library, capture and performance
  workspace, score controls, piano roll, keyboard, exports, dialogs, login,
  updater, errors, and responsive score reader.
- Added a labeled theme control to the workspace and login plus a compact
  score-reader control.
- Persisted the explicit preference in local storage and initialized it in the
  document head before application code runs.
- Forwarded each initial and changed preference to Tauri's native window-theme
  command under one narrow capability permission.
- Preserved fixed ivory score paper, black notation and piano keys, and the
  distinct pedal-state colors in both themes.

## Validation Evidence

Completed on August 26, 2026:

- `npm run typecheck --prefix app` passed.
- `npm test --prefix app` passed all 111 tests, including light default, dark
  persistence, and the native Tauri theme invocation.
- `npm run build --prefix app` produced the production client successfully.
- `cargo check --manifest-path app/src-tauri/Cargo.toml` accepted the added
  narrow capability and desktop source.
- `node --test scripts/validate-desktop-release.test.mjs` passed all nine
  desktop release-contract checks.
- `uv run atpiano migration-regression` passed its complete unattended gate;
  the report is
  `results/migration-regression/20260826T054723Z/report.json`.
- Headless Chromium rendered the fixture library, detailed performance, and
  score reader in both themes at desktop size without horizontal overflow.
- A 390-by-844 score-reader pass had no page-level horizontal overflow.
- A toggle followed by reload retained dark mode; the score reader inherited
  the same preference.
- Light and dark desktop-size screenshots were visually reviewed. They remain
  ignored review artifacts rather than tracked product media.

Playwright WebKit was not available in the local browser cache. The shared CSS
and TypeScript gates passed, while real packaged macOS and Windows acceptance
remains part of the next desktop release rather than this source-only slice.
The on-demand shared service reported `stopped`, so it was not started or
restarted solely for this change.
