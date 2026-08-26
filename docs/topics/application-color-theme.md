# Application Color Theme

Topic: application-color-theme

## Scope

This topic owns the shared React application's color tokens, explicit color
preference, native desktop-window theme, and visual relationship to the public
site. The marketing site's own layout and deployment remain owned by
[`public-marketing-site.md`](public-marketing-site.md).

## Current Status

The shared application now defaults to the public site's warm paper, ivory,
near-black, and piano-felt red palette. It also provides an explicit dark mode
using the same red/black visual language. The source change is prepared for
signed desktop release `0.1.3`; publication evidence is still pending.

The control is available in the normal workspace, authenticated login, and
full-screen score reader. A choice is stored under
`atpiano:color-theme`, applied before React starts to prevent an incorrect
startup flash, and forwarded to Tauri so native window chrome follows the web
content. When storage or the native theme command is unavailable, the current
web session still remains usable and defaults to light.

The main token contract is:

| Role | Light direction | Dark direction |
| --- | --- | --- |
| Page and surfaces | warm paper and ivory | warm near-black layers |
| Primary text | near-black | warm ivory |
| Brand/action | deep felt red | brighter accessible red |
| Score paper | ivory with fixed dark notation | ivory with fixed dark notation |
| Piano roll | intentionally dark for note contrast | intentionally dark |

The implementation and validation record is
[`../tactical/056-website-aligned-application-theme.md`](../tactical/056-website-aligned-application-theme.md).

## Accepted Decisions

- Light is the product default rather than silently following the OS. Dark is
  a durable, explicit user choice.
- Semantic CSS tokens own ordinary surfaces, text, borders, actions, warnings,
  and errors. Visualization-specific colors remain distinct where they encode
  musical state, such as inferred sustain versus soft pedal.
- Engraved score paper and physical piano-key colors keep their real-world
  light/dark meaning in both application themes.
- The Tauri capability exposes only `core:window:allow-set-theme` for this
  preference; no broader window mutation permission is needed.

## Recommended Direction

New shared-application UI should use the semantic tokens in `app/src/styles.css`
instead of adding mode-specific literals. When the marketing palette changes,
review the application tokens deliberately rather than assuming every site
color transfers to dense musical visualizations. Include both themes in future
desktop release screenshots and acceptance checks.
