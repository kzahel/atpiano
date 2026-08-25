# Public Marketing Site

Topic: public-marketing-site

## Objective

Publish an honest, distinctive Atpiano product and download site on the newly
registered `at-piano.com` domain, collect narrow interest in a future paid
hosted version, and establish the public design direction without changing the
desktop application's theme.

## Implemented Slice

- Added an Astro 7 application under `site/` with product, download, privacy,
  and custom 404 pages.
- Established a responsive red, ivory, white, and black visual system inspired
  by piano keys and red key-bed felt.
- Added a real application screenshot, generated social preview, SVG favicon,
  direct desktop artifacts, source/contribution links, and feedback email.
- Added an Astro POST endpoint, case-insensitive D1 schema, duplicate upsert,
  honeypot, same-origin check, and managed Turnstile verification.
- Added restrictive response security headers and permanent `www`-to-apex
  canonicalization.
- Created the EU-jurisdiction production D1 database and domain-restricted
  Turnstile widget, stored the Turnstile secret as an encrypted Worker secret,
  applied the migration, and deployed the Worker to both hostnames.

## Validation Evidence

Completed on August 25, 2026:

- `pnpm generate-types` completed and generated Cloudflare binding types.
- `pnpm build` completed with Astro's Cloudflare adapter and compile-time image
  handling, with no provisioned Cloudflare Images or session KV dependency.
- The tracked D1 migration applied to a fresh local database.
- A local Turnstile test-key POST returned success and produced the expected
  consent-versioned D1 row.
- Browser visual inspection confirmed loaded styling, a 695-pixel desktop hero
  after correcting the screenshot aspect ratio, and the complete homepage.
- The production apex returned HTTP 200 with the intended content and security
  headers; the `www` download URL returned HTTP 308 to the apex path.
- A live managed-Turnstile submission completed through the no-JavaScript
  fallback, exposing an inline-script CSP issue that was corrected by moving
  the enhancement to a same-origin static script.
- A second live submission completed through the AJAX enhancement without a
  navigation, displayed its success state, and produced the expected D1 row.
- Both synthetic acceptance records were deleted afterward; the production
  list returned to zero active records.

## Operational Notes

The production resource identifiers and public Turnstile site key are tracked
in `site/wrangler.jsonc`. The Turnstile secret is present only in Cloudflare's
encrypted Worker-secret store. Local development uses Cloudflare's published
test keys through the ignored `.dev.vars` file.

The download page is intentionally pinned to desktop `0.1.1`; it must be
updated as part of the next desktop release. No email-sending provider is
connected, so an operator must query/export active records deliberately and
handle deletion or withdrawal through authenticated D1 commands.
