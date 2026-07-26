# 025 — Public Live Caddy Proxy

Topic: multi-tenant-hybrid-service-architecture

Status: **implemented on 2026-07-26.**

## Outcome

Temporarily publish the real local model-backed React workspace at
`https://atpiano.graehlarts.com`. The Pi's existing public Caddy service
proxies to the Mac over their LAN.

## Boundaries

- The Python application, live PCM WebSocket, model workers, sessions, and
  artifacts remain on the Mac.
- The Mac listener binds only to its selected LAN address, not every network
  interface.
- The server admits the exact configured HTTPS Host and Origin in addition to
  its existing loopback addresses. Other Host and Origin values remain
  forbidden.
- This is an intentionally temporary public trial, not authenticated
  multi-tenant hosting. Stop the Mac process when the review is finished.

## Implementation

- Add explicit `workbench-v3 --bind` and `--public-origin` options.
- Add exact Host and Origin checks for the configured public hostname,
  including browser mutation and WebSocket paths.
- Add the public DNS record to the Pi's existing Name.com DDNS state.
- Add the proxy to the tracked and live Pi Caddyfiles.
- Provide one repository command that starts the real Mac application with
  the established address, port, and origin.

## Validation

- Exercise trusted and foreign Host/Origin requests in automated tests.
- Verify the Pi can reach the Mac listener over the LAN.
- Validate and reload the live Caddy configuration.
- Verify the API and WebSocket path through the public HTTPS hostname.
- Perform a real microphone Start, PCM acknowledgement, Stop, and session
  settlement through the public proxy.
