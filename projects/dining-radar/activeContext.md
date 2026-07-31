# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

The Product Brief and the initial candidate-proposal contract became durable through PR #65. Human screen review then approved ADR-0005 and API v0.4 for PR #66: an authenticated organizer sees one deterministic initial proposal immediately, compares its candidates on a Leaflet/OpenStreetMap map and cards, and chooses a different lens from a re-proposal modal only when needed. Re-proposal replaces the displayed cards and map rather than adding a page. No implementation authorization is implied.

Hot Pepper Gourmet Web Service API is the sole initial provider. One private runtime-configured location is never accepted from or shown to the browser. Lunch is mandatory; cards and maps show only agreed provider reference fields. The map is derived only from returned shop locations and has no origin marker, routing, or current-location feature. ADR-0002's public-repository and provider-data boundary remains in effect.

The candidate-search design slice became durable through merged PR #66. Human review on 2026-08-01 changed the intended interaction: after sign-in, the first candidate set and its map appear without secondary conditions or an initial concept-selection step; requesting another lens opens a concept-selection modal, and selecting a concept replaces the displayed proposal. ADR-0005 and candidate-search API v0.4 record the approved change. Candidate-card information hierarchy and readability are deferred until the application is substantially implemented.

The active slice defines the authentication and Internet-access boundary before candidate-search implementation. The agreed direction is Django session authentication with administrator-created individual accounts, no public sign-up, login/logout/password change, administrator-assisted password reset without email delivery, and administrator account deactivation. HTTPS, Secure/HttpOnly/SameSite cookies, CSRF protection, and login throttling are mandatory boundaries. Concrete hosting, domain, email delivery, and SSO choices are outside this slice; no deployment or authentication implementation is authorized by the contract work.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses initially. Do not introduce durable provider IDs or HMAC-derived lookup data until current provider terms permit it.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Candidate-search endpoints depend on an authenticated organizer. The active contract slice defines that authentication boundary without implementing it or choosing a deployment provider.

## Next work

1. Draft and review the authentication and Internet-access boundary contract on `feat/toyama-dining-radar-auth-contract`, without implementation or deployment-provider selection.
2. After that contract becomes durable, coordinate the first candidate-search implementation slice separately.
3. Reconfirm current Hot Pepper and map-provider terms before implementation or public operation, especially credit, schema, caching, and long-term identifier handling.

## Open questions

- Provider-terms permission for durable provider identifiers or HMAC-derived lookup data.
- Concrete hosting, domain, email delivery, and SSO choices for a later deployment slice.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat). The candidate-search interaction revision, ADR-0005, API v0.4, and Codex-authored receiver became durable through merged PR #66 under ADR-0035 approval mode (i). The authentication-boundary direction recorded above was human-approved in chat on 2026-08-01; its artifacts remain drafts until reviewed and merged through the project PR flow.
