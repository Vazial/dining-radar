# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

The Product Brief, candidate-proposal acceptance/API contracts, and ADR-0004 are human-approved and durable: PR #65 merged on 2026-08-01. An authenticated organizer chooses a deterministic concept, compares its candidates on a Leaflet/OpenStreetMap map and cards, and re-proposes rather than using fixed-page additions. No implementation authorization is implied.

Hot Pepper Gourmet Web Service API is the sole initial provider. One private runtime-configured location is never accepted from or shown to the browser. Lunch is mandatory; cards and maps show only agreed provider reference fields. The map is derived only from returned shop locations and has no origin marker, routing, or current-location feature. ADR-0002's public-repository and provider-data boundary remains in effect.

The candidate-search design slice now has an isolated Codex-authored review receiver. Its screen direction was human-approved in chat on 2026-08-01, including a follow-up to reduce promotional copy for an everyday organizer tool. The receiver remains review-only and becomes durable only through its design PR merge; it does not authorize production implementation.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses initially. Do not introduce durable provider IDs or HMAC-derived lookup data until current provider terms permit it.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Authentication, account lifecycle, HTTPS/cookie/CSRF/proxy/host deployment settings, rate limiting, and public deployment remain a separate slice. Candidate-search endpoints depend on an authenticated organizer but do not implement that boundary.

## Next work

1. Complete verification and PR review for the approved-direction candidate-search receiver and ADR-0003.
2. In a separately coordinated shared-meta slice, record the runtime-specific Designer route: Claude commissions Gemini; Codex designs directly under the shared role contract.
3. Draft and obtain approval for the separate authentication/public-deployment slice before candidate-search implementation.
4. Reconfirm current Hot Pepper and map-provider terms before implementation or public operation, especially credit, schema, caching, and long-term identifier handling.

## Open questions

- Provider-terms permission for durable provider identifiers or HMAC-derived lookup data.
- The concrete authentication/public-deployment boundary.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat). The candidate-search contracts and ADR-0004 are approved through PR #65's merge. The Codex-authored candidate-search screen direction and reduced-copy adjustment were human-approved in chat on 2026-08-01. The receiver and ADR-0003 become durable through the active design PR merge under ADR-0035 approval mode (i).
