# ADR 0006: Local identity, community and invitation boundary

- Status: Accepted and integrated in the FastAPI backend
- Date: 2026-08-29

## Context

The earlier accepted ASSEMBLE checkpoint had no accounts, sessions, community membership, role authorisation or persistence. The next backend milestone needed those capabilities without changing solver or Project semantics or pretending that a frontend identity workflow already existed. Local hackathon operation had to remain deterministic and independent of an email or cloud provider.

## Decision

Implement identity, community membership and invitations as an isolated `app.auth` package. Use Python's standard-library SQLite driver and numbered, transactional migrations. Enable foreign keys and WAL mode. The database path and cookie security mode are explicit settings; tests use a temporary file and an injected clock. No new package dependency is required.

Hash passwords with `hashlib.scrypt` using a fresh 16-byte salt and the exact local work factors `N=16384`, `r=8`, `p=1`, `dkLen=32`, with a 64 MiB `maxmem` ceiling. The `scrypt-v1` stored encoding carries those parameters; verification accepts only those bounded values and compares the derived digest in constant time, preventing a forged database record from selecting unbounded work. Generate session and invitation bearer secrets from 32 random bytes and persist only their SHA-256 digests. Session cookies are opaque, `HttpOnly`, `SameSite=Lax`, scoped to `/`, omit `Domain`, and are `Secure` when the configured origin uses HTTPS. Login and password change rotate sessions; password changes revoke all earlier sessions.

Persist users, sessions, communities, memberships, invitations, fixed-window rate counters and append-only audit events. Invitation rows bind the digest to community, role, inviter, normalized recipient, expiry and lifecycle state. Acceptance is a single transaction that checks token, state, expiry, recipient and existing membership before consuming the invitation and creating the membership.

Use four community roles: `ADMINISTRATOR`, `COORDINATOR`, `MEMBER`, and `VIEWER`. Server-side permission checks are derived from the current persisted membership on every protected community-administration request. Administrators alone create/revoke invitations, list invitation state, list members and change roles. The last Administrator cannot be demoted. Demoting another Administrator atomically revokes that inviter's pending grants in the community. All authenticated roles may read the community; planning and Project permissions remain declarations only. The integrated solver, reasoning, Project and M7 routes are deliberately not role-gated at this checkpoint.

Expose the slice through a registration function that installs a router and auth-specific handlers. The shared application entry point performs that one-call registration after existing routes are declared. This installation does not add a frontend identity workflow.

## Consequences

- Local state survives application restarts when the same database path is used.
- SQLite serializes the lifecycle transitions that must be single-use.
- Raw invite tokens are returned once only for deterministic local delivery and are never recoverable from storage.
- POSIX state is created under a mode-0700 directory with mode-0600 database/WAL/SHM files; unsafe existing modes fail closed. Windows permissions remain a host-ACL responsibility.
- The default local HTTP cookie cannot use `Secure`; production-like HTTPS operation must set `ASSEMBLE_AUTH_COOKIE_SECURE=1`.
- `SameSite=Lax` is the hackathon browser boundary. A public deployment would additionally require an explicit origin/CSRF policy, TLS termination review, secret rotation, observability and a distributed rate limiter.
- Unsafe JSON routes also reject a present origin outside the exact bounded canonical `ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS` allow-list and a present cross-site `Sec-Fetch-Site`; Host and forwarded headers cannot broaden the list, and non-browser clients without those headers remain supported. Auth namespace matching is segment-aware so lookalike routes retain ordinary 404 handling. This is a bounded local same-origin defence, not a complete public-deployment CSRF design.
- Existing solver, planner, Project and frontend behavior remains unchanged by router registration.
- Auth, community and invitation records persist; Projects, proof context and current task state remain in memory.
- Auth-created SQLite communities are not linked to the solver's authoritative fictional fixture.
