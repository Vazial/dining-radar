# Authentication acceptance review — final L4 step/DSL audit

## Disposition

**Suitable for human approval of the changed local-L4 step and DSL artifacts.**
This is a fresh independent audit of the authentication acceptance test, its
Gherkin-to-step mapping, and its browser/HTTP DSL. It does not review
production code, unit tests, or the L3 evidence for `TDR-AUTH-06`.

The prior sole open finding for `TDR-AUTH-02` is closed. The browser-interface
SSoT now defines `auth-individual-account-guidance` as a semantic observation
with `data-auth-account-use=individual-only` and
`data-auth-credential-sharing=not-requested`. The DSL requires that control
and asserts both attributes after sign-in. This makes the approved
individual-account/no-sharing outcome observable without prescribing visible
copy, layout, or a new browser operation.

`TDR-AUTH-06` remains intentionally outside this local L4 suite. The approved
local/deployment split assigns its configuration and security evidence to L3
and actual HTTPS transport evidence to the deployment slice.

## Independent translation table

| Contract scenario and statement | Step/test route and observable | Result |
|---|---|---|
| 01: no session opens proposal screen or API | A fresh cookie jar opens `/` and sends an unauthenticated `POST /candidate-proposals`. | Covered. |
| 01: safe sign-in guidance and no candidate/map/lens/origin disclosure | The entry requires the sign-in form; it rejects every unauthenticated forbidden control and all declared disclosure ids/canaries. | Covered at the declared browser-interface boundary. |
| 01 API: `AUTHENTICATION_REQUIRED` | The response must be 401, match `ProblemResponse` in `candidate-search-api.yaml`, and carry that code. | Covered. |
| 02: an active individual account signs in | The declared synthetic-account seam establishes Given state; sign-in uses the rendered same-origin form. | Covered. |
| 02: same-origin session starts and the candidate screen opens | The authenticated shell is asserted, then `/` is reopened with the same cookie jar and remains authenticated. | Covered. |
| 02: the organizer is not asked to share credentials | The authenticated semantic observation is required and its account-use and credential-sharing attributes are asserted exactly. | Covered. |
| 03: no public sign-up or email self-reset; administrator assistance only | Initial, generic-failure, and throttled-failure states expose assistance and exclude both public-operation controls; `/sign-up` and `/password-reset` return 404, and the reset response has no token/resetToken/email keys. | Covered at the declared browser-interface boundary. |
| 04: sign-out stops protected access | Sign-out produces unauthenticated controls, then the same cookie jar receives schema-valid 401 `AUTHENTICATION_REQUIRED` and the entry remains unauthenticated. | Covered. |
| 04: password change affects a later sign-in | The public password-change form is submitted; after sign-out, a fresh entry accepts the new password and restores the authenticated shell. | Covered. |
| 05: deactivation revokes an existing session | The account seam deactivates the same synthetic account; the first post-deactivation operation is the candidate request with the existing cookie jar. | Covered. |
| 05: no protected disclosure after deactivation | The 401 response receives schema and disclosure checks; reopening the entry applies the unauthenticated forbidden-control/canary checks. | Covered at the declared browser-interface boundary. |
| 07: failed sign-in is throttled | The declared throttle seam establishes deterministic state immediately before each unknown/disabled browser sign-in action. | Covered without embedding a throttle threshold or time delay. |
| 07: account state and confidential values are not disclosed | Generic and throttled results assert their controls, reject disclosure ids/canaries/submitted passwords, and compare normalized unknown versus disabled public DOM. | Covered. |

## Five-point step/DSL checklist

| Check | Result | Evidence |
|---|---|---|
| 1. Contract over/under-implementation | Pass | Each local-L4 scenario has one dedicated method. The new semantic attributes project an existing approved outcome; they add no business operation or decision. |
| 2. Given legitimacy | Pass | State reset, synthetic account state, and throttle setup use only the declared acceptance-test seams. Browser actions use the public same-origin UI/API boundary. |
| 3. Then observes public outcomes | Pass | UI controls, semantic attributes, API status/code/schema, session persistence, stale-session order, and disclosure canaries are asserted through the browser-interface/API contracts. |
| 4. No failure masking | Pass | Step mappings are thin delegations. The DSL has bounded redirects and direct assertions, with no retry/sleep loop, broad exception swallowing, or conditional success route. |
| 5. No hidden assumptions | Pass | The local URL comes from the required runner environment value; CSRF/HTTPS are explicitly delegated to the approved L3/deployment scope; throttle setup does not encode an operational threshold. |

## Scenario-to-test coverage, orphan, and duplicate audit

| Contract ID | Intended level | Dedicated method | Status |
|---|---|---|---|
| TDR-AUTH-01 | Local L4 | `test_tdr_auth_01_unauthenticated_visitor_cannot_use_candidate_search` | Covered. |
| TDR-AUTH-02 | Local L4 | `test_tdr_auth_02_active_organizer_signs_in_to_candidate_screen` | Covered. |
| TDR-AUTH-03 | Local L4 | `test_tdr_auth_03_public_signup_and_email_reset_are_not_available` | Covered at the browser-interface boundary. |
| TDR-AUTH-04 | Local L4 | `test_tdr_auth_04_organizer_can_sign_out_and_change_password` | Covered. |
| TDR-AUTH-05 | Local L4 | `test_tdr_auth_05_deactivation_revokes_protected_access` | Covered. |
| TDR-AUTH-06 | L3 plus deployment | No local L4 method by approved scope | Not an orphan in this suite. |
| TDR-AUTH-07 | Local L4 | `test_tdr_auth_07_throttle_and_generic_failure_do_not_disclose_account_state` | Covered. |

There is one dedicated method per local-L4 scenario and no orphan acceptance
method. The repeated 401 assertion in 01, 04, and 05 is intentional rather
than duplicate coverage: it proves never-authenticated, signed-out, and
deactivated-session states separately. The security-boundary test seam is not
consumed by this suite because it belongs to the approved L3 scope for
`TDR-AUTH-06`.

## Closure of prior findings

| Prior finding | Status | Independent evidence |
|---|---|---|
| Cover all unauthenticated forbidden controls and initial/generic/throttled states | Closed | `_assert_unauthenticated_controls` covers all declared forbidden ids; public-operation checks exercise each declared state. |
| Make candidate/map/lens/origin absence observable | Closed | The browser-interface SSoT declares the candidate controls and private-origin id; the DSL rejects them and the applicable disclosure canaries. |
| Observe “do not share credentials” or narrow the scenario | Closed | The semantic observation defines two required data attributes and `assert_authenticated_shell` asserts both exact values. |
| Make deactivated stale-session candidate request the first operation | Closed | `assert_protected_access_is_revoked` posts with the existing cookie jar before reopening `/`, matching `firstPostDeactivationOperation`. |
| Assert all listed disclosures and mechanically validate `ProblemResponse` | Closed | Generic/throttled/API paths perform the declared checks; both candidate 401 paths validate the API schema. |

## Approval handoff

**Final disposition: approve the changed local-L4 steps and DSL.** The
translation and checklist show no remaining acceptance-layer blocker. This is
approval of the scenario-to-step/DSL translation only; normal automated
verification and human review of the implementation PR remain required.
