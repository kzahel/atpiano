# Atpiano marketing site

This Astro application serves [at-piano.com](https://at-piano.com) from a
Cloudflare Worker. It includes the public product and download pages plus a
small hosted-product interest list backed by Cloudflare D1 and protected by
Cloudflare Turnstile.

## Local development

Install dependencies and create the local database once:

```sh
pnpm install
pnpm wrangler d1 migrations apply atpiano-marketing --local
```

The checked-in `.dev.vars.example` uses Cloudflare's public Turnstile test
keys. Copy it to `.dev.vars` if needed, then run:

```sh
pnpm dev
```

Build and type-check the Cloudflare boundary with:

```sh
pnpm generate-types
pnpm build
```

## Production resources

The Worker has a D1 binding named `SIGNUPS`, a public
`TURNSTILE_SITE_KEY` variable, and an encrypted `TURNSTILE_SECRET_KEY` secret.
Apply tracked migrations before deploying a schema change:

```sh
pnpm wrangler d1 migrations apply atpiano-marketing --remote
pnpm deploy
```

Never commit the Turnstile secret or a production signup export. To review or
export active interest records, use an authenticated Wrangler session and D1
queries. An ordinary unsubscribe can retain the record as withdrawn while
excluding it from outreach:

```sql
UPDATE hosted_interest
SET status = 'withdrawn', withdrawn_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE email = ?;
```

For a request to delete the stored address, remove the matching row instead:

```sql
DELETE FROM hosted_interest WHERE email = ?;
```

The form records only the email, timestamps, signup source, consent version,
and withdrawal state. It intentionally does not store request IP addresses or
browser fingerprints.
