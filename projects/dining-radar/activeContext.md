# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

The Product Brief and the initial candidate-proposal contract became durable through PR #65. Human screen review then approved ADR-0005 and API v0.4 for PR #66: an authenticated organizer sees one deterministic initial proposal immediately, compares its candidates on a Leaflet/OpenStreetMap map and cards, and chooses a different lens from a re-proposal modal only when needed. Re-proposal replaces the displayed cards and map rather than adding a page. The candidate-search contract is now approved and merged; the slice stands at cross-section ② (implementation agreement) with no implementation written yet.

Claude took over this project from Codex on 2026-08-04. The handover happened with no open pull request and a green project branch, so no unmerged Codex artifact was inherited. This slice-0 pull request also brings `main` into the project branch, which had fallen 63 commits behind and therefore predated meta ADR-0040 through ADR-0047.

Hot Pepper Gourmet Web Service API is the sole initial provider. One private runtime-configured location is never accepted from or shown to the browser. Lunch is mandatory; cards and maps show only agreed provider reference fields. The map is derived only from returned shop locations and has no origin marker, routing, or current-location feature. ADR-0002's public-repository and provider-data boundary remains in effect.

The candidate-search design slice became durable through merged PR #66. Human review on 2026-08-01 changed the intended interaction: after sign-in, the first candidate set and its map appear without secondary conditions or an initial concept-selection step; requesting another lens opens a concept-selection modal, and selecting a concept replaces the displayed proposal. ADR-0005 and candidate-search API v0.4 record the approved change. Candidate-card information hierarchy and readability are deferred until the application is substantially implemented.

The authentication and Internet-access boundary became durable through merged PR #67, and its verified local Django implementation became durable through merged PR #71. It has administrator-created and deactivated individual accounts, login/logout/password change, administrator-assisted reset without email, session and CSRF protection, generic throttled login failure, and a responsive minimal authenticated application shell. `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07` pass L4 browser-facing verification. Because deployment is deferred, `TDR-AUTH-06` passes L3 configuration and security checks; actual HTTPS transport remains deferred to the deployment slice. It has no Hot Pepper connection, candidate generation, map, public deployment, or real accounts, secrets, and locations. Concrete hosting, domain, email delivery, and SSO remain outside this slice.

The user approved the first candidate-search implementation scope, ADR-0008, Product Brief policy amendment, and candidate-search contract amendment in chat on 2026-08-03. Re-proposal performs a fresh provider search and only lowers the display rank of candidates already shown during the same browser screen lifetime; this product does not add visit history, a blacklist, durable provider identifiers, or a provider-response cache. The exact private origin remains a Must-not-disclose value, while preventing approximate regional inference from displayed shops and their map is a Want. These artifacts became durable through merged PR #76.

`contracts/candidate-search-browser-interface.yaml` and the amended acceptance-only `contracts/test-support-api.yaml` also became durable through PR #76. An independent tester found those contracts sufficient to translate `TDR-CS-00` through `TDR-CS-08`. Candidate implementation is therefore unblocked.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses. This product does not use durable provider IDs or HMAC-derived lookup data. Reopening that policy requires a new human decision, provider-terms review, and ADR.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Candidate-search endpoints depend on an authenticated organizer. ADR-0006 and the authentication contracts define that boundary; the active slice implements it locally without choosing a deployment provider.
- The approved candidate-search boundary uses `strict-origin-when-cross-origin` for public map operation so standard OSM tiles receive only the public origin as Referer. It does not weaken same-origin session or CSRF controls.

## Next work

1. Merge this slice-0 pull request so the project branch carries current `main` and both activeContext files describe the present state.
2. Implement the approved candidate-search slice at cross-section ②: developer and tester work in parallel without sharing context. Developer builds the server-side HTTPS Hot Pepper adapter, deterministic recommendation, authenticated proposal endpoint, candidate cards, Leaflet/OSM map, re-proposal modal, and safe failure handling against L1 through L3. Tester translates `TDR-CS-00` through `TDR-CS-08` into step definitions and DSL for L4. Reviewer audits only after CI is fully green.
3. Reconfirm current Hot Pepper and map-provider terms before public operation, especially credit, schema, and caching. A change to the no-history/no-durable-identifier product policy requires a new human decision before work starts.

## Open questions

- Concrete hosting, domain, email delivery, and SSO choices for a later deployment slice.

## Approval state

The original `product-brief.md` is human-approved (2026-07-31 chat). Its no-history/no-durable-identifier policy amendment, ADR-0008, and the corresponding candidate-search contract amendment were human-approved in chat on 2026-08-03 and became durable through merged PR #76, together with the candidate browser interface and the amended acceptance-only test-support contract. The candidate-search interaction revision, ADR-0005, API v0.4, and Codex-authored receiver became durable through merged PR #66. ADR-0006 and the authentication contracts became durable through merged PR #67 under ADR-0035 approval mode (i); its verified implementation became durable through merged PR #71. Human resolution on 2026-08-01 approved L4 browser verification for `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07`, L3 local configuration/security verification for `TDR-AUTH-06`, and deferral of actual HTTPS transport verification to deployment.
