# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

The Product Brief is human-approved. The candidate-proposal acceptance/API contracts and ADR-0004 are now reviewable proposals: an authenticated organizer chooses a deterministic concept, compares its candidates on a Leaflet/OpenStreetMap map and cards, and re-proposes rather than using fixed-page additions. They remain unapproved; no implementation authorization is implied.

Hot Pepper Gourmet Web Service API is the sole initial provider. One private runtime-configured location is never accepted from or shown to the browser. Lunch is mandatory; cards and maps show only agreed provider reference fields. The map is derived only from returned shop locations and has no origin marker, routing, or current-location feature. ADR-0002's public-repository and provider-data boundary remains in effect.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses initially. Do not introduce durable provider IDs or HMAC-derived lookup data until current provider terms permit it.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Authentication, account lifecycle, HTTPS/cookie/CSRF/proxy/host deployment settings, rate limiting, and public deployment remain a separate slice. Candidate-search endpoints depend on an authenticated organizer but do not implement that boundary.

## Next work

1. Obtain human review of the revised candidate-search acceptance contract, API contract, and ADR-0004. Do not treat Product Brief approval as their approval.
2. After those contracts are approved, replace the stale review-only design brief and preview against the approved contract.
3. Draft and obtain approval for the separate authentication/public-deployment slice before candidate-search implementation.
4. Reconfirm current Hot Pepper and map-provider terms before implementation or public operation, especially credit, schema, caching, and long-term identifier handling.

## Open questions

- Whether the proposed relative range labels and the maximum-three concept response are acceptable contract choices.
- Provider-terms permission for durable provider identifiers or HMAC-derived lookup data.
- The concrete authentication/public-deployment boundary.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat). `contracts/candidate-search.feature`, `contracts/candidate-search-api.yaml`, and ADR-0004 are proposals awaiting human review. The current design brief and preview remain stale/non-authoritative until a later design slice replaces them.
