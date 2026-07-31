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
