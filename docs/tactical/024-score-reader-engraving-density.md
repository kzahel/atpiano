# 024 — Score Reader Engraving Density

Topic: performance-to-notation

Status: implemented on 2026-07-26 from desktop review of retained session
`20260726T154200-f86498b7ed5b`.

## Observation

The responsive reader correctly fits pages and turns them, but a dense
generated piano score exposes two presentation defects:

1. adjacent grand-staff systems have too little vertical breathing room; and
2. **Large**, **Comfortable**, and **Compact** can appear identical on desktop.

The second defect is structural. The first implementation changes OSMD
`Zoom`, then deliberately fits every resulting SVG back to the same fixed
page width. That final fit cancels a pixel-only zoom difference. Density must
instead change the engraving geometry that decides system and page breaks.

## Bounded Implementation

- Keep the exact pinned MusicXML, route identity, and semantic anchor contract
  from Tactical 020.
- Define three explicit engraving profiles.
- Make every profile set OSMD inter-system collision clearance and minimum
  vertical system distance.
- Make profiles change the effective page-format capacity so notation size,
  measures per system, systems per page, or page count visibly differ.
- Preserve authored MusicXML system and page breaks.
- Keep paper aspect ratio and responsive one- or two-page presentation.
- Reflow from the pinned XML and restore the aligned source or measure anchor
  after a profile change.
- Keep **Comfortable** as the default, with substantially more system
  separation than OSMD's compact defaults.

## Acceptance

- The uploaded retained score has a clearly visible margin between each
  treble-plus-bass system at **Comfortable**.
- **Large** is visibly more spacious than **Comfortable**.
- **Compact** fits materially more music than **Comfortable**.
- Switching profiles on a later page retains the same musical position.
- Phone and landscape layouts remain free of application-level horizontal
  overflow.
- Authored `new-system` and `new-page` directives remain effective.
- Frontend tests, type checking, production build, and the migration
  regression pass.

## Execution Record

The implementation landed as:

- `a928af9` — plan the bounded density correction;
- `dfcd3e8` — replace pixel-only zoom with engraving profiles; and
- `59f81e8` — wait for the asynchronous renderer page map in the routing
  regression.

Each profile now changes both OSMD's pre-layout geometry and effective page
capacity:

| Profile | Page scale | Minimum system distance | Sky/bottom clearance |
|---|---:|---:|---:|
| Large | 1.16 | 16 | 12 |
| Comfortable | 1.00 | 12 | 9 |
| Compact | 0.86 | 6 | 4 |

The reader also gives every page explicit top and bottom engraving margins.
It no longer uses OSMD `Zoom`: fixed-width responsive SVG fitting had
cancelled that pixel-only distinction after layout. Changing profiles
re-renders the exact pinned MusicXML with a profile-specific custom page
format, then restores the source-sample or measure anchor.

### Browser evidence

The retained score named above was opened in the real reader with OSMD 1.9.9.
At a 1440-by-913 desktop viewport:

- **Large** produced six pages and two grand-staff systems on the first page,
  with about 146 pixels between the measured system extents.
- **Comfortable** produced four pages and three systems on the first page,
  with measured clearances of about 75–106 pixels.
- **Compact** fit four systems on the first page and advanced its page
  anchors farther through the score than **Comfortable**.

At a 390-by-844 emulated phone viewport, **Compact** presented one 366-by-717
paper page at a time with no document-level horizontal overflow. Switching
from page two in **Compact** to **Comfortable** retained the active measure,
even though the profile change altered pagination.

### Automated evidence

- The focused application test passed three consecutive runs.
- TypeScript checking and the Vite production build passed.
- The complete migration regression passed at
  `results/migration-regression/20260726T171157Z/report.json`: 120 Python
  tests, 6 legacy live-view tests, 5 TypeScript node tests, and 41 Vitest
  tests passed along with contract, audit, lint, syntax, and whitespace
  gates.

Physical piano-distance viewing and representative Bluetooth pedal behavior
remain subjective device checks owned by the continuing reader topic; they do
not block this spacing correction.
