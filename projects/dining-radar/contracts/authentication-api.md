# Toyama Dining Radar browser authentication and runtime boundary

> **Status**: This is a reviewable logical browser/API and configuration boundary for ADR-0006. It is not an implementation route table, deployment runbook, or a selection of a host, domain, email provider, or SSO provider.

## Authoritative interface boundary

The browser uses the Django application at one same-origin HTTPS public origin. The real origin is runtime/deployment configuration and is never recorded as a real value in this public repository. The current `POST /candidate-proposals` contract remains the only candidate-search browser API; its `organizerSession` security scheme is satisfied only by the session described here.

| Logical browser operation | Who may use it | Required boundary | Observable outcome |
|---|---|---|---|
| Sign in | A manager-provisioned individual account | HTTPS; CSRF-protected form; login throttle; generic failure | Starts a same-origin Django session on success. Failure does not disclose whether an account exists or is disabled. |
| Sign out | An authenticated organizer | HTTPS; CSRF-protected state change | Invalidates the current browser session for protected use. |
| Change password | An authenticated organizer | HTTPS; CSRF-protected state change; current authenticated session | Changes the account credential without exposing it in logs, URLs, or the repository. |
| Reset password | Administrator and the affected organizer through an administrator-assisted process | A privileged administrator path outside the public application API | No public forgot-password request, reset email, or reset token endpoint exists in the initial scope. |
| Create or deactivate account | Administrator only | A privileged administrator path outside the public application API | No public registration endpoint exists. Deactivation prevents subsequent protected candidate-search access. |
| View or re-propose candidates | An authenticated, active organizer | Existing candidate-search API: same-origin session and CSRF for POST | Returns only the candidate-search contract response; never a private origin, provider credential, or provider internals. |

Route names, templates, redirect targets, the administrator console implementation, and the session expiry are intentionally not part of this logical interface. A later implementation slice may name them without weakening this contract.

## Required runtime configuration boundary

| Concern | Required invariant | Must not be committed or browser-visible |
|---|---|---|
| Public transport | Authenticated use is served over HTTPS. | Real host/domain, certificate material, deployment topology. |
| Session cookie | The Django session cookie is `Secure`, `HttpOnly`, and has an explicit `SameSite` policy of `Lax` or stricter. | Session signing secret, a live cookie value, session store contents, exact production expiry. |
| CSRF | Every cookie-authenticated state-changing browser request, including login, logout, password change, and candidate proposal POST, is CSRF-protected. | CSRF secret/token values and rejected-request diagnostics that reveal internals. |
| Cross-origin use | The browser interface is same-origin. Credentialed arbitrary-origin CORS and local-storage bearer tokens are absent. | Broad production allowlists or real application origins. |
| Account lifecycle | Only administrators provision, reset, and deactivate individual accounts; public sign-up and email reset are disabled in the initial scope. | Real user names, email addresses, password hashes, account status, reset records, login history. |
| Login abuse protection | Failed sign-in attempts are throttled and have generic responses. The exact threshold/window is an implementation and operations choice. | Per-user failure history, rate-limit keys, operational thresholds if they encode real usage. |
| Provider/privacy separation | Auth handling and all errors avoid the private search origin, provider key, key-bearing URL, provider response, shop identifier, or provider-internal failure detail. | Those values in source, tests, fixtures, logs, traces, and browser responses. |

## Explicitly deferred decisions

- Concrete deployment provider, domain, certificate handling, observability destination, and administrator console access path.
- Exact session lifetime, rotation/invalidation mechanics, password policy, throttle values, and recovery procedure details.
- Email delivery and public self-service recovery; they are excluded rather than silently assumed.
- SSO or external identity providers.

Any change that exposes a new public account-management operation, accepts credentials across origins, chooses a real public origin, or introduces email/SSO is outside this contract and requires a separate reviewed slice.
