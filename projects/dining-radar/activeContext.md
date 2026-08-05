# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

Claude took this project over from Codex on 2026-08-04, with no open pull request and a green project branch, so no unmerged Codex artifact was inherited.

`TDR-CS` (candidate search) is complete and became durable through merged PR #82. An authenticated organizer opens the screen and immediately sees one deterministic proposal — candidate cards and a Leaflet/OpenStreetMap map — without being asked for secondary conditions or an initial concept choice. Selecting a card highlights its marker and the reverse. Requesting another lens opens a modal of at most three concepts and replaces the displayed proposal rather than adding a page. Shops already shown during the same screen lifetime are ranked lower on re-proposal but never excluded.

The implementation is four modules. `recommendation` is pure Python with no framework or provider dependency: it deduplicates by provider page URL and builds the four concepts (`PROXIMITY`, `CAPACITY_REFERENCE`, `GENRE_VARIETY`, `AMENITY_REFERENCE`), offering each only when it is explainable from the current candidates (ADR-0004 decision 1). `integrations/hotpepper` is the HTTPS-only adapter with env-based configuration, query-key redaction, and provider-shape normalization. `suggestions` mediates the fresh search and the pipeline, applies per-organizer rate limiting, and owns the acceptance-only state seam; it is also the only path by which `web` may reach the provider adapter, which a structural test enforces. `web` serves `POST /candidate-proposals`, a serializer matching the API schema exactly, and the authenticated screen, whose candidate surface is rendered client-side by vanilla JavaScript with no bundler.

Verification is green at every layer: L0 govlint, L1 (107 unit tests, 95% branch coverage, mutation score 100% with 162 of 162 gremlins zapped), L2 (7 structural tests), L3 (67 boundary tests plus `manage.py check` for the production and test profiles), and L4 (15 acceptance tests, no skips). `TDR-CS-00` through `TDR-CS-08` execute against the real client-rendered screen through Playwright per ADR-0009; `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07` keep the plain-HTTP DSL (ADR-0009 decision 4). `reviews/audit-tdr-cs.md` holds the independent reviewer's translation table; the three findings it raised were resolved and re-audited, and two minor observations remain recorded there for the human approver.

Leaflet is vendored under `static/` and served same-origin (ADR-0010), so OSM standard tiles are the only external origin the map UI contacts. `env.example` documents every runtime environment variable with no values, and a structural test compares it against the variables `src/dining_radar` actually reads, so the template cannot silently drift from the implementation in either direction.

Two implementation choices were made where the contracts deliberately left the rule to the implementer: the per-concept ranking algorithm (an open item in `product-brief.md` §8), and the assumed Hot Pepper raw JSON field names used for normalization. The latter is verified only against synthetic fixtures, because ADR-0002 decision 7 forbids a live credentialed call from this repository; it must be reconfirmed against current official documentation before public operation.

The product still has no deployment, no public origin, and no real accounts, secrets, or locations. `TDR-AUTH-06` passes L3 configuration and security checks only; actual HTTPS transport verification remains deferred to a deployment slice (ADR-0007).

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses. This product does not use durable provider IDs or HMAC-derived lookup data. Reopening that policy requires a new human decision, provider-terms review, and ADR.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Leaflet itself (JS, CSS, marker icons) is vendored under `static/` and served same-origin (ADR-0010). The authenticated screen loads no third-party script.
- Candidate-search endpoints depend on an authenticated organizer. ADR-0006 and the authentication contracts define that boundary; this slice implements it locally without choosing a deployment provider.
- The approved candidate-search boundary uses `strict-origin-when-cross-origin` for public map operation so standard OSM tiles receive only the public origin as Referer. It does not weaken same-origin session or CSRF controls.

## Next work

1. Reconfirm current Hot Pepper and map-provider terms before public operation, especially credit, schema, and caching, and reconfirm the assumed Hot Pepper raw JSON field names against current official documentation. A change to the no-history/no-durable-identifier product policy requires a new human decision before work starts.
2. Candidate-card information hierarchy and readability were deferred until the application was substantially implemented. It now is, so this is available to pick up.

## Open questions

- Concrete hosting, domain, email delivery, and SSO choices for a later deployment slice.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat), and its no-history/no-durable-identifier amendment was approved in chat on 2026-08-03. The candidate-search interaction revision, ADR-0005, API v0.4, and the Codex-authored design receiver became durable through merged PR #66. ADR-0006 and the authentication contracts became durable through merged PR #67 under ADR-0035 approval mode (i), and the verified authentication implementation through merged PR #71. ADR-0008, the candidate-search contract amendment, the browser interface, and the amended acceptance-only test-support contract became durable through merged PR #76. Human resolution on 2026-08-01 approved L4 browser verification for `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07`, L3 verification for `TDR-AUTH-06`, and deferral of HTTPS transport verification to deployment.

ADR-0009 (JS-capable browser automation for the candidate-search L4), ADR-0010 (vendored Leaflet), ADR-0011 (visible formatting separated from raw-value equality), the resulting `contracts/candidate-search-browser-interface.yaml` v0.2 amendment, and the `TDR-CS` implementation itself became durable through merged PR #82 under approval mode (i). The human decided the three ADRs in chat on 2026-08-04 and 2026-08-05, and `reviews/audit-tdr-cs.md` was the translation-table material for that approval.
