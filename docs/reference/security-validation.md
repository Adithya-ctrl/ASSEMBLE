# Security and validation reference

ASSEMBLE is currently a localhost, deterministic fixture application. Its FastAPI backend provides local accounts, HttpOnly cookie sessions, persisted community roles and recipient-bound invitations in a private SQLite store; the frontend exposes those capabilities only through the same-origin proxy, strict runtime response parsers, an independent session provider, and role-aware Collaboration surfaces. It does not provide OAuth, cloud persistence, deployment, or external data ingestion. Authentication does not wrap solver, reasoning, Project, or M7 routes.

## Trust boundaries

| Input | Trust decision |
| --- | --- |
| Community state used by analyse/explain | Strictly schema-validated bounded input; analyser calls cannot mutate the submitted community or initiative, and returned status is source-bound to that request |
| Action catalogue used by reasoning routes | Must exactly match the disclosed server catalogue |
| Project base community | Must exactly match authoritative fixture content and identity/lineage |
| Project catalyst path | Required, ordered, unique, known, and bounded to 0–2 actions |
| Project metadata | Trimmed and length-validated; extra fields rejected |
| Assignments/readiness/status | Never trusted from the client; always derived server-side |
| Auth request body | Actual received bytes bounded to 16 KiB; unsafe routes require JSON and strict models |
| Password/session/invitation secrets | Scrypt password hashes and digest-only bearer storage; raw secrets excluded from persistence and ordinary responses |
| Community permissions | Reload current persisted membership for every protected community-administration request; preserve the last Administrator |
| Browser cookie boundary | HttpOnly, SameSite=Lax host-only cookie; present Origin must exactly match the bounded canonical allow-list; duplicate security-sensitive Origin, Sec-Fetch-Site, Content-Type or Content-Length headers are rejected; Host and forwarded headers never broaden it |
| Counterfactual analysis | Reconstruct from authoritative S0 and action catalogue; accept no client witness, patch, perturbation body or catalogue |
| Resilience browser integration | Send untouched canonical demo S0 plus only the verified ordered catalyst path; strict runtime parsers, independent cancellation generations and source bindings reject stale or mismatched responses |

## Explicit collection ceilings

Requests fail with `422 INVALID_REQUEST` before reasoning when they exceed these schema limits:

| Collection | Maximum |
| --- | ---: |
| Organisations in a community | 32 |
| People in a community | 128 |
| Spaces in a community | 32 |
| Resources in a community | 64 |
| Initiatives or requested initiative IDs | 32 |
| Catalyst actions in a submitted catalogue | 32 |
| Capabilities or willingness facts per person; features or required capabilities per block/role | 32 |
| Languages per person or role | 16 |
| Roles per initiative | 32 |
| Resource requirements, each precondition category, or effects per action | 64 |
| Availability or candidate-start slots | 4 |

Unlock and planning are further restricted to unique non-repeating paths of one or two actions. With the authoritative four-action fixture, this is 16 ordered candidates.

Auth request bodies are capped at 16 KiB of actual received bytes. Username, email, password, profile, community, invitation and audit-list field limits are specified in [`identity-community-invitations.md`](identity-community-invitations.md). Stress-test catalogues contain at most 20 server-generated perturbations; the published solver-call ceilings are 601 for stress, 32 for recompile and 1056 for frontier.

Stable identifiers contain 1–256 characters. Integer, boolean and literal fields use strict types: numeric strings, integral floats and booleans do not cross those boundaries by coercion.

## Fail-closed behavior

- Missing referenced initiative resources remain non-relaxable integrity failures.
- UNKNOWN never becomes infeasible or feasible and never carries a partial witness.
- An analyser may not mutate its submitted community or initiative. Its result must bind to the requested initiative and keep status, witness and objective fields consistent; malformed output is an internal contract breach returned as `500 ANALYSER_CONTRACT_ERROR`, never relabelled UNKNOWN.
- An infeasible or unknown Project proof returns `409 PROJECT_PLAN_NOT_FEASIBLE` without a Project object.
- A forged base state returns `409 COMMUNITY_STATE_MISMATCH` before Project transition or solving.
- Reapplying an already-present additive effect returns a stable conflict instead of a false successful transition.
- Framework and domain failures use stable error envelopes.
- Missing/expired/revoked sessions and persisted role failures return stable auth errors; password changes rotate the current session and revoke earlier sessions.
- The frontend schedules invalidation from the parsed session expiry, clears cached identity on `AUTHENTICATION_REQUIRED`, and fails closed while refreshing membership after an Administrator request returns `403`.
- Invitation acceptance is recipient-bound and single-transaction; public token failures are deliberately indistinguishable.
- Rate counters persist across restart and bound signup, login, password-change and invitation-acceptance attempts before expensive verification.
- Noncanonical password-hash encodings or salts, invalid avatar ports, unsafe POSIX database permissions, oversized streamed bodies, non-JSON unsafe auth requests, duplicate sensitive headers, and invalid or rejected exact browser origins fail closed. Auth namespace scope is segment-aware, so lookalike paths fall through to ordinary 404 handling.
- Counterfactual IDs are domain-separated from operational state IDs and cannot become Project lineage. `UNKNOWN` is explicit and excluded from decisive stress/frontier claims.
- The Resilience Lab is read-only: a pending transition disables it, new source/path generations clear incompatible results, and neither visible analysis nor raw Judge evidence can update workflow community, transition or Project state.

## Current adversarial coverage

Tests cover forged capabilities, resource quantity, space availability and lineage under the same `S0` label; whitespace-only metadata; omitted and extra fields; unknown, duplicate, overlong, insufficient, and already-applied paths; strict scalar types and ID length; analyser input mutation, source/status binding and unsafe witness combinations; adversarial trace/objective facts; missing referenced IDs; collection overflow; wrong methods; and unknown routes. Auth coverage adds canonical hash/salt encoding, session fixation, rotation/revocation, avatar URL bounds, secret-at-rest scans, recipient-bound invitation replay/races, last-Administrator and cross-community boundaries, persisted rate limits, restart recovery, convergent concurrent cold-start, locked-store translation, exact origin and duplicate-header handling, streamed-byte limits, and exact POSIX `0700`/`0600` enforcement. M7 coverage adds authoritative reconstruction, one-fact delta assertions, catalogue bounds, two-stage recompile invariants, incomplete-coverage frontier ambiguity and non-operational counterfactual identity.

The [absolute adversarial acceptance report](../ADVERSARIAL_ACCEPTANCE_REPORT.md) records the supporting executed matrix and its explicit gaps. It is not a production-security certification, and partial browser rows do not establish unexecuted permutations.

## Persistence and authorisation boundary

The default auth store is `backend/.data/auth.sqlite3`, ignored by Git; `ASSEMBLE_AUTH_DB_PATH` overrides it. On POSIX its directory is mode `0700` and database/WAL/SHM files are mode `0600`. Auth/community/invitation records are the only persistent application state. Auth-created SQLite communities are not linked to the solver's authoritative fictional fixture. Projects, proof context and current task state remain in memory.

The current frontend exposes local signup, login, session, profile, password, Collaboration administration and recipient-bound invitation workflows through the same-origin proxy. Do not describe that localhost boundary as a production multi-user security system, or describe solver, reasoning, Project, stress-test, recompile or frontier routes as authorised by community roles; they are deliberately not role-gated. There is no project membership, task authorisation, account recovery, email ownership verification, MFA, OAuth, public-deployment CSRF design, distributed rate limiter, deployment hardening or encrypted application-level database. The local controls are not a production-security or privacy certification.
