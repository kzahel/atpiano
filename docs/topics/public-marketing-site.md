# Public Marketing Site

Topic: public-marketing-site

## Scope

This topic owns Atpiano's public product, download, hosted-interest, privacy,
and discovery surface. Desktop application behavior and release production
remain owned by [`public-desktop-release.md`](public-desktop-release.md).

## Current Status

The Astro site is published at [at-piano.com](https://at-piano.com) from a
Cloudflare Worker. `www.at-piano.com` redirects permanently to the apex. The
site uses the intended piano-derived red, ivory, white, and black visual
language; it is the reference direction for a later application-theme update,
but does not change the desktop application yet.

The current public surface includes:

- a product homepage with a real application screenshot and an honest
  proof-of-concept/transcription caveat;
- direct signed macOS Apple-silicon and Windows x64 downloads for desktop
  release `0.1.1`, plus GitHub release checksums and provenance;
- public source, contribution, feedback-email, privacy, and Graehl Arts links;
  and
- a hosted-product interest form which clearly states that the browser version
  is exploratory, unavailable today, and would be paid.

The bounded implementation and production evidence are recorded in
[`../tactical/054-public-marketing-site.md`](../tactical/054-public-marketing-site.md).

## Deployment Shape

The application lives under `site/` and uses Astro's Cloudflare adapter in
server mode. Cloudflare provides:

- one Worker named `atpiano-marketing` for pages and the signup endpoint;
- static Worker assets for CSS, screenshots, icons, and the social card;
- one EU-jurisdiction D1 database bound as `SIGNUPS`; and
- one managed Turnstile widget restricted to the apex and `www` hostnames.

No newsletter or transactional-email vendor is connected. The first version
deliberately collects signal without creating an account, sending an automated
message, or adding an unrelated operational dependency. This keeps the initial
surface small and inexpensive; Cloudflare plan and usage limits still need
ordinary account-level monitoring.

## Interest and Privacy Contract

The signup endpoint accepts same-origin form submissions, validates a managed
Turnstile token server-side, normalizes the address to lowercase, and upserts
one case-insensitive row per address. It stores only:

- email address;
- created and last-updated timestamps;
- homepage/download source;
- consent-copy version; and
- active or withdrawn status and an optional withdrawal timestamp.

The endpoint does not intentionally retain the request IP address, user agent,
or a browser fingerprint. Production exports and the Turnstile secret must
never enter Git. A deletion request removes the row; a simple unsubscribe may
mark it withdrawn. The operator commands and query examples live in
[`../../site/README.md`](../../site/README.md).

## Release and Content Contract

The download page currently pins explicit `0.1.1` GitHub assets so visitors get
the correct signed files without relying on user-agent detection. When a new
desktop release becomes current, update the displayed version, both artifact
URLs, and any changed platform or model caveats in the same release slice.

The marketing copy says that the source is public rather than calling the
project open source because the repository does not currently declare a source
license. It also keeps the optional score model's upstream licensing caveat.

## Recommended Direction

Keep the initial list manual until its size or outreach frequency justifies an
email provider. Before the first list email, establish an export audit,
unsubscribe handling, sender authentication, and a sent-message record. Before
building hosted Atpiano, use the list only as one signal alongside interviews,
retention evidence, and an explicit hosted-service cost model.
