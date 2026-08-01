# friction-log.md

> Append-only record of AI mistakes, uncertainty, and avoidable rework. Human
> decisions by themselves are not friction; record only the AI contribution.

## FR-001: Design was commissioned before the chat Spec was closed

```yaml
id: FR-001
date: 2026-07-31
found_at: AI
slice: TDR-CS
agents: [architect, designer, orchestrator]
cause_category: workflow sequencing
cause_key: design-commissioned-before-contract-agreement
pushed_to: [projects/toyama-dining-radar/activeContext.md]
status: 対応済み
principles: [P-05, P-10]
```

- Situation: External design commissioning and the review-only preview used the
  earlier coordinate-input, primary/alternative, variable-count draft before
  the user closed the candidate-search Spec checkpoint.
- AI contribution: The workflow advanced to design reconciliation without first
  establishing the chat-agreed contract as the authoritative input. That made
  the brief, preview, and reconciliation stale and created avoidable contract
  rework.
- Downward push: The current `activeContext.md` now records that the preview is
  stale and requires reconciliation against the contract before any
  implementation slice. ADR-0003 states that the contract, not the receiver,
  is the SSOT for candidate-search behaviour.
- Result: No broad governance change is proposed from one occurrence. Future
  work follows the existing chat-first checkpoint before commissioning design.

### FR-001 follow-up (2026-07-31)

- The remediation is now represented by `product-brief.md`: it is the explicit
  human-review-pending input before the stale candidate-search contract and
  design artifacts may be replaced.
- The replacement order is recorded in `activeContext.md`: Product Brief
  review, then contract/ADR revision, then design reconciliation. No external
  design commissioning is authorized by this follow-up.

### FR-001 follow-up (2026-07-31, Product Brief approval)

- The Product Brief was approved in chat before the candidate-search contract
  and ADR were rewritten. The replacement contract now remains a separate
  human-review proposal, and the stale design brief/preview remain untouched.
- This completes the documented sequencing remediation for this occurrence;
  future design work still waits for approval of the replacement contract.

## FR-002: 認証受け入れテストに必要な Given seam を契約せず、L4 実装が停止した

```yaml
id: FR-002
date: 2026-08-01
found_at: L4
slice: TDR-AUTH
agents: [architect, developer, tester]
cause_category: L4 test infrastructure contract missing
cause_key: l4-given-seam-contract-missing
pushed_to:
  - projects/toyama-dining-radar/contracts/test-support-api.yaml
  - projects/toyama-dining-radar/ARCHITECTURE.md
status: 対応済み
principles: [P-02, P-03, P-04, P-10]
```

- Situation: The approved authentication scenarios require synthetic account creation, account deactivation, scenario isolation, and a deterministic throttled-sign-in state. The authentication contracts defined only browser-facing behaviour, so developer and tester had no machine-readable agreement for the acceptance-only Given seams required to execute L4.
- AI contribution: The authentication implementation slice was started without projecting those non-public setup and observation boundaries into a test-infrastructure contract. This made the L4 blocker discoverable only after implementation work had begun.
- Downward push: `contracts/test-support-api.yaml` is now the ADR-0008 SSoT for the three minimal acceptance-only seams. `ARCHITECTURE.md` makes the public-boundary versus Given-seam split explicit. The seam is deliberately limited to synthetic authentication state; it neither extends the business API nor changes the approved acceptance scenarios.
- Result: Developer and tester can consume the same original OpenAPI file for the implementation and DSL sides. Exact production throttle values remain outside the contract, while TDR-AUTH-07 becomes deterministic.

## FR-003: Given seamだけを先に補い、browser操作とlocal/deploymentの観測境界を契約しなかった

```yaml
id: FR-003
date: 2026-08-01
found_at: L4
slice: TDR-AUTH
agents: [architect, developer, tester]
cause_category: L4 browser observation contract missing
cause_key: l4-browser-observation-contract-missing
pushed_to:
  - projects/toyama-dining-radar/adr/0007-separate-local-auth-verification-from-deployment-transport.md
  - projects/toyama-dining-radar/contracts/authentication-browser-interface.yaml
  - projects/toyama-dining-radar/contracts/test-support-api.yaml
  - projects/toyama-dining-radar/ARCHITECTURE.md
status: 対応済み
principles: [P-01, P-03, P-04, P-10]
```

- Situation: After the Given seams were specified, the local authentication slice still lacked a shared browser control surface and a way to distinguish local HTTP acceptance execution from the deferred public HTTPS transport. Isolated developer and tester could not determine which UI states, security observations, and verification layer applied to each TDR-AUTH scenario.
- AI contribution: The first remediation treated L4 setup as the only missing interface. It did not also contract the browser operation/observation side or explicitly project the local/deployment split that the human had to resolve.
- Downward push: ADR-0007 records the human resolution. `authentication-browser-interface.yaml` is the acceptance-only SSoT for test IDs, browser outcomes, profile split, and security observations; `test-support-api.yaml` exposes only the effective local acceptance security boundary for L3. The deployment transport remains out of this local slice.
- Result: Browser L4 and configuration L3 can now be implemented independently without source-code knowledge, while an HTTP localhost run cannot be misreported as public HTTPS verification.

### FR-003 follow-up (2026-08-01, tester audit)

- The first browser-interface draft named controls and observations but omitted the isolated runner's entry URL. That still left the tester unable to reach the sign-in/protected surface without inspecting implementation routes.
- `authentication-browser-interface.yaml` now makes `TDR_ACCEPTANCE_BASE_URL` plus `/` the only local acceptance entry, with required unauthenticated/authenticated outcomes. The same entry states where public-sign-up and email-reset controls must be absent. This is a test-harness boundary only; it does not choose a public origin or deployment route.

### FR-003 follow-up (2026-08-01, independent acceptance review)

- The independent reviewer found that several approved outcomes still had no stable machine-readable observation: candidate/map/lens/private-origin absence, persistent-session proof, individual-account guidance, reset-operation absence, first-request deactivation ordering, complete generic/throttled disclosure checks, and the exact candidate-error schema reference.
- `authentication-browser-interface.yaml` now defines only those missing observables: forbidden surface test ids and synthetic disclosure canaries, same-cookie entry reopen, individual-account guidance, absent-operation route probes, the required first post-deactivation request order, unknown-versus-disabled response comparison in both failure states, and `ProblemResponse` schema references. No business scenario, public candidate API shape, or local/deployment split changed.

### FR-003 follow-up (2026-08-01, TDR-AUTH-02 acceptance review remediation)

- The independent reviewer found that the opaque
  `auth-individual-account-guidance` control id alone did not make the
  approved no-credential-sharing outcome observable. Naming a control is not
  an assertion of its meaning.
- `authentication-browser-interface.yaml` now requires a machine-readable
  semantic state on that existing control: `individual-only` account use and
  `not-requested` credential sharing. The assertion uses `data-*` attributes
  so it does not prescribe visible copy, layout, or a new browser operation.
  No business scenario, public API, or authentication policy changed.
