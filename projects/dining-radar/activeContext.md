# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

The Product Brief and the initial candidate-proposal contract became durable through PR #65. Human screen review then approved ADR-0005 and API v0.4 for PR #66: an authenticated organizer sees one deterministic initial proposal immediately, compares its candidates on a Leaflet/OpenStreetMap map and cards, and chooses a different lens from a re-proposal modal only when needed. Re-proposal replaces the displayed cards and map rather than adding a page. No implementation authorization is implied.

Hot Pepper Gourmet Web Service API is the sole initial provider. One private runtime-configured location is never accepted from or shown to the browser. Lunch is mandatory; cards and maps show only agreed provider reference fields. The map is derived only from returned shop locations and has no origin marker, routing, or current-location feature. ADR-0002's public-repository and provider-data boundary remains in effect.

The candidate-search design slice now has an isolated Codex-authored review receiver in PR #66. Human review on 2026-08-01 changed the intended interaction: after sign-in, the first candidate set and its map appear without secondary conditions or an initial concept-selection step; requesting another lens opens a concept-selection modal, and selecting a concept replaces the displayed proposal. ADR-0005 and candidate-search API v0.4 record the approved change, and the receiver has been revised to match. The receiver remains review-only and does not authorize production implementation.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses initially. Do not introduce durable provider IDs or HMAC-derived lookup data until current provider terms permit it.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Authentication, account lifecycle, HTTPS/cookie/CSRF/proxy/host deployment settings, rate limiting, and public deployment remain a separate slice. Candidate-search endpoints depend on an authenticated organizer but do not implement that boundary.

## Next work

1. Complete visual and machine verification of the ADR-0005-aligned receiver, update PR #66, and obtain its merge approval.
2. In a separately coordinated shared-meta slice, record the runtime-specific Designer route: Claude commissions Gemini; Codex designs directly under the shared role contract.
3. Draft and obtain approval for the separate authentication/public-deployment slice before candidate-search implementation.
4. Reconfirm current Hot Pepper and map-provider terms before implementation or public operation, especially credit, schema, caching, and long-term identifier handling.

## Open questions

- Provider-terms permission for durable provider identifiers or HMAC-derived lookup data.
- The concrete authentication/public-deployment boundary.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat). The candidate-search interaction revision, ADR-0005, and API v0.4 were human-approved in chat on 2026-08-01 and become durable through PR #66's merge under ADR-0035 approval mode (i). The Codex-authored receiver direction and reduced-copy adjustment are also human-approved; the revised modal layout remains available for visual confirmation before merge.
