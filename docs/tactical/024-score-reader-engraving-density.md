# 024 — Score Reader Engraving Density

Topic: performance-to-notation

Status: planned on 2026-07-26 from desktop review of retained session
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

No implementation commits yet.
