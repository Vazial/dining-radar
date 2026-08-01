# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

The Product Brief and the initial candidate-proposal contract became durable through PR #65. Human screen review then approved ADR-0005 and API v0.4 for PR #66: an authenticated organizer sees one deterministic initial proposal immediately, compares its candidates on a Leaflet/OpenStreetMap map and cards, and chooses a different lens from a re-proposal modal only when needed. Re-proposal replaces the displayed cards and map rather than adding a page. No implementation authorization is implied.

Hot Pepper Gourmet Web Service API is the sole initial provider. One private runtime-configured location is never accepted from or shown to the browser. Lunch is mandatory; cards and maps show only agreed provider reference fields. The map is derived only from returned shop locations and has no origin marker, routing, or current-location feature. ADR-0002's public-repository and provider-data boundary remains in effect.

The candidate-search design slice became durable through merged PR #66. Human review on 2026-08-01 changed the intended interaction: after sign-in, the first candidate set and its map appear without secondary conditions or an initial concept-selection step; requesting another lens opens a concept-selection modal, and selecting a concept replaces the displayed proposal. ADR-0005 and candidate-search API v0.4 record the approved change. Candidate-card information hierarchy and readability are deferred until the application is substantially implemented.

The authentication and Internet-access boundary became durable through merged PR #67. The active implementation slice now has a reviewable local Django authentication path for administrator-created and deactivated individual accounts, login/logout/password change, administrator-assisted reset without email, session and CSRF protection, generic throttled login failure, and a responsive minimal authenticated application shell. `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07` pass L4 browser-facing verification. Because deployment is deferred, `TDR-AUTH-06` passes L3 configuration and security checks; actual HTTPS transport remains deferred to the deployment slice. The implementation has no Hot Pepper connection, candidate generation, map, public deployment, or real accounts, secrets, and locations. Concrete hosting, domain, email delivery, and SSO remain outside this slice.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses initially. Do not introduce durable provider IDs or HMAC-derived lookup data until current provider terms permit it.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Candidate-search endpoints depend on an authenticated organizer. ADR-0006 and the authentication contracts define that boundary; the active slice implements it locally without choosing a deployment provider.

## Next work

1. Review and merge the verified authentication implementation PR from `feat/toyama-dining-radar-auth-implementation` into `project/toyama-dining-radar`.
2. After that implementation becomes durable, agree the purpose and scope of the first candidate-search implementation slice separately.
3. Reconfirm current Hot Pepper and map-provider terms before candidate-search implementation or public operation, especially credit, schema, caching, and long-term identifier handling.

## Open questions

- Provider-terms permission for durable provider identifiers or HMAC-derived lookup data.
- Concrete hosting, domain, email delivery, and SSO choices for a later deployment slice.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat). The candidate-search interaction revision, ADR-0005, API v0.4, and Codex-authored receiver became durable through merged PR #66. ADR-0006 and the authentication contracts became durable through merged PR #67 under ADR-0035 approval mode (i). The authentication implementation scope was human-approved in chat on 2026-08-01. Human resolution on 2026-08-01 approved L4 browser verification for `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07`, L3 local configuration/security verification for `TDR-AUTH-06`, and deferral of actual HTTPS transport verification to deployment. The implementation remains reviewable until its project PR is merged.
