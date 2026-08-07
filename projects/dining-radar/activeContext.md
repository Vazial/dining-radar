# activeContext.md — Toyama Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

Claude took this project over from Codex on 2026-08-04, with no open pull request and a green project branch, so no unmerged Codex artifact was inherited.

`TDR-CS` (candidate search) became durable through merged PR #82. An authenticated organizer opens the screen and immediately sees one deterministic proposal — candidate cards and a Leaflet/OpenStreetMap map — without being asked for secondary conditions or an initial concept choice. Selecting a card highlights its marker and the reverse. Requesting another lens opens a modal of at most three concepts and replaces the displayed proposal rather than adding a page. Shops already shown during the same screen lifetime are ranked lower on re-proposal but never excluded.

The implementation is four modules. `recommendation` is pure Python with no framework or provider dependency: it deduplicates by provider page URL and builds the four concepts (`PROXIMITY`, `CAPACITY_REFERENCE`, `GENRE_VARIETY`, `AMENITY_REFERENCE`), offering each only when it is explainable from the current candidates (ADR-0004 decision 1). `integrations/hotpepper` is the HTTPS-only adapter with env-based configuration, query-key redaction, and provider-shape normalization. `suggestions` mediates the fresh search and the pipeline, applies per-organizer rate limiting, and owns the acceptance-only state seam; it is also the only path by which `web` may reach the provider adapter, which a structural test enforces. `web` serves `POST /candidate-proposals`, a serializer matching the API schema exactly, and the authenticated screen, whose candidate surface is rendered client-side by vanilla JavaScript with no bundler.

The candidate-card refinement slice is complete. Its design base came from one external-AI commission (`gemini-3.5-flash`, accepted at round 2 after round 1 was rejected for boundary violations); ADR-0012 then moved all post-acceptance iteration to developer rather than commissioning further rounds. Three human real-device reviews drove it. The screen now presents a one-line header (title, an account-use info marker, and a native `<details>` account menu holding password-change and sign-out), a concept banner whose re-proposal control sits at the end of its row, and the map above the cards on narrow widths — via CSS grid areas only, so DOM and keyboard-focus order never change and no candidate control was added or removed. Everyday wording replaced the domain term `切り口` in visible copy. Every activatable control declares a ≥44px target; the two credit/attribution links stay smaller inline text links deliberately (WCAG 2.5.8's in-sentence case, and their text is contractually fixed).

ADR-0013 records the human's standing policy that an approved screen may drive the test-infrastructure control-surface contracts rather than the reverse. It required two amendments, both by architect: `candidate-search-browser-interface.yaml` v0.3 adds the `auth-account-menu-toggle` disclosure purpose, and `authentication-browser-interface.yaml` v0.2 adds `browserControlSurface.authenticated.renderModel`, making explicit that TDR-AUTH's plain-HTTP DSL observes only server-rendered HTML. That second amendment is why the account menu is a JavaScript-free `<details>`: a client-inserted menu would have silently voided existing TDR-AUTH coverage. No `.feature`, `*-api.yaml`, step definition, or test DSL changed in this slice.

Verification is green at every layer: L0 govlint, L1 (112 unit tests, 95% branch coverage, mutation score 100% with 162 of 162 gremlins zapped), L2 (7 structural tests), L3 (72 boundary tests plus `manage.py check` for the production and test profiles), and L4 (15 acceptance tests, no skips). `TDR-CS-00` through `TDR-CS-08` execute against the real client-rendered screen through Playwright per ADR-0009; `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07` keep the plain-HTTP DSL (ADR-0009 decision 4). `reviews/audit-tdr-cs.md` holds the independent reviewer's translation table for `TDR-CS`.

Orchestrator measured the shipped screen on a running server at 390×844 and 1440×900. At the narrow width the map is reachable without scrolling (208px from the top, against 349px when the human first objected), the header is 44px, and the document is 1.82 viewports. At 1440px the layout is `"cards map"` at `774px 416px` with the map sticky in the right column, and no activatable control measures under 44px. **Only orchestrator can measure rendered geometry** — developer and the role agents have no browser access, and three defects this slice (marker attributes never applied, a scenario green without asserting its DOM outcome, and template comment text rendering as page content) were all invisible to L1–L4 and surfaced only by real-device measurement.

Leaflet is vendored under `static/` and served same-origin (ADR-0010), so OSM standard tiles are the only external origin the map UI contacts. `env.example` documents every runtime environment variable with no values, and a structural test compares it against the variables `src/dining_radar` actually reads. `tests/test_template_syntax.py` guards template-delimiter leakage at both source and rendered-output level (FR-007).

Two implementation choices remain verified only against synthetic fixtures: the per-concept ranking algorithm (an open item in `product-brief.md` §8), and the assumed Hot Pepper raw JSON field names used for normalization. ADR-0002 decision 7 forbids a live credentialed call from this repository, so both must be reconfirmed against current official documentation before public operation.

The product still has no deployment, no public origin, and no real accounts, secrets, or locations. `TDR-AUTH-06` passes L3 configuration and security checks only; actual HTTPS transport verification remains deferred to a deployment slice (ADR-0007).

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses. This product does not use durable provider IDs or HMAC-derived lookup data. Reopening that policy requires a new human decision, provider-terms review, and ADR.
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Leaflet itself (JS, CSS, marker icons) is vendored under `static/` and served same-origin (ADR-0010). The authenticated screen loads no third-party script.
- Candidate-search endpoints depend on an authenticated organizer. ADR-0006 and the authentication contracts define that boundary; this slice implements it locally without choosing a deployment provider.
- The approved candidate-search boundary uses `strict-origin-when-cross-origin` for public map operation so standard OSM tiles receive only the public origin as Referer. It does not weaken same-origin session or CSRF controls.
- Controls on the authenticated candidate screen must appear in the server-rendered HTML, not be inserted by client JavaScript, wherever TDR-AUTH's plain-HTTP DSL observes them (`authentication-browser-interface.yaml` v0.2 `renderModel`).

`manage.py` loads `projects/toyama-dining-radar/.env.local` when it exists, using a stdlib-only parser and `os.environ.setdefault`, so a real process environment always wins and a missing file is a no-op. That path is developer convenience only — deployment runs through `wsgi.py` and never depends on it. This closed a gap where `env.example` told the reader to copy itself to `.env.local` while nothing read that file.

ADR-0014 establishes a client-side JavaScript unit-verification layer for `candidate.js` (543 lines, previously exercised only by L4). It is not yet implemented. The ADR is explicit that none of the three defects found so far in that layer would reliably have been caught by it — its value is forward-looking regression capture.

## Next work

1. Reconfirm current Hot Pepper and map-provider terms before public operation, especially credit, schema, and caching, and reconfirm the assumed Hot Pepper raw JSON field names against current official documentation. A change to the no-history/no-durable-identifier product policy requires a new human decision before work starts.
2. Promote `project/toyama-dining-radar` to `main`. The branch carries `TDR-AUTH` and `TDR-CS` and has never been promoted.
3. Consider whether ADR-0003's stated design-preview stack (React, TypeScript, Tailwind, shadcn/ui) should match the receiver's actual dependencies (React, TypeScript, `lucide-react` only, with hand-written CSS), by installing the missing packages or amending the ADR. Designer worked around the gap by requiring visually self-contained artifacts; the divergence itself is unresolved.

## Open questions

- Concrete hosting, domain, email delivery, and SSO choices for a later deployment slice.
- Whether the "approved screen drives the test-infrastructure control-surface contract" pattern (ADR-0011, ADR-0013) should be generalized into a meta ADR beside `meta/adr/0023`, since other UI projects can hit the same friction. Architect raised this; drafting a meta ADR belongs to orchestrator (`meta/adr/0047`).

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat), and its no-history/no-durable-identifier amendment was approved in chat on 2026-08-03. The candidate-search interaction revision, ADR-0005, API v0.4, and the Codex-authored design receiver became durable through merged PR #66. ADR-0006 and the authentication contracts became durable through merged PR #67 under ADR-0035 approval mode (i), and the verified authentication implementation through merged PR #71. ADR-0008, the candidate-search contract amendment, the browser interface, and the amended acceptance-only test-support contract became durable through merged PR #76. `TDR-CS` itself, ADR-0009, ADR-0010, ADR-0011, and `candidate-search-browser-interface.yaml` v0.2 became durable through merged PR #82. Human resolution on 2026-08-01 approved L4 browser verification for `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07`, L3 verification for `TDR-AUTH-06`, and deferral of HTTPS transport verification to deployment.

ADR-0012, ADR-0013, `candidate-search-browser-interface.yaml` v0.3, and `authentication-browser-interface.yaml` v0.2 became durable through merged PR #84 under ADR-0035 approval mode (i), together with the candidate-card refinement itself. The human approved the round-2 design base, the PC layout, the narrow-width direction, the terminology change, and the three header changes across chat reviews on 2026-08-06.

**Convention for this file (FR-008):** do not describe the approval status of an in-flight pull request here. The pull request, the ADR frontmatter, and git already own that fact, and duplicating it guarantees this file becomes false the moment the merge happens (P-04). Describe what exists; let the approval record live where the approval act is.
