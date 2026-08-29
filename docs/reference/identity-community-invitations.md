# Identity, community and invitation contract

This page is the current contract for the auth/community/invitation backend installed in the shared FastAPI application. The registration and local configuration are described in [`../how-to/integrate-auth-backend.md`](../how-to/integrate-auth-backend.md).

## Integration and product boundary

The integrated implementation lives in:

- `backend/app/auth/`;
- `backend/tests/auth/`;
- `contracts/auth-api.md`;
- this reference, ADR 0006, the auth integration guide, and auth-specific traceability, verification and status claims;
- `backend/app/main.py`, which performs the reviewed router registration.

Registration does not alter solver/compiler/explain/interventions/planner/Project/M7 semantics. Auth-created SQLite communities are not linked to the solver's authoritative fictional community fixture. Auth and persisted community-role checks protect only auth and community-administration routes. Solver, reasoning, Project, stress-test, recompile and frontier endpoints are deliberately not role-gated. The current frontend has no identity, membership or invitation workflow and its account control remains disabled. Only auth/community/invitation state persists; Projects and proof context remain in memory.

## Threat model

| Asset or boundary | Threat | Required control |
| --- | --- | --- |
| Password | Offline database disclosure or forged expensive hash parameters | 16-byte random salt; `scrypt-v1`, N=16384, r=8, p=1, dkLen=32, maxmem=64 MiB; bounded parser; constant-time digest comparison |
| Session | Fixation, theft, stale reuse | 256-bit opaque token; digest-only storage; HttpOnly SameSite cookie; rotation; expiry; revocation; password version |
| Invitation | Database token leakage, guessing, replay | 256-bit opaque token; digest-only storage; recipient/community/role/inviter binding; transactional single-use lifecycle |
| Community role | Horizontal or vertical escalation | Load current membership from storage on every request; explicit permission matrix; last-Administrator guard |
| Identity lookup | Username/email enumeration | Generic login, account-conflict and public invitation failures |
| Request handling | Brute force and resource exhaustion | Persisted fixed-window counters; strict models; extra-field rejection; field and body ceilings |
| Audit evidence | Secret leakage or mutable history | Append-only events; allow-listed non-secret metadata; never record password, cookie or raw invite token |
| Restart | Lost revocation or resurrected invite | File-backed SQLite; migration ledger; lifecycle and counters persisted |

Out of scope for this localhost milestone: public internet deployment, account recovery, email ownership verification, MFA, OAuth, distributed replicas, external mail, malware on the host, and protection after an attacker obtains the running process memory. An email-bound invitation proves only equality with the unverified email stored on the local account; it does not prove ownership of that mailbox.

## Data model

| Record | Security-relevant fields |
| --- | --- |
| `users` | immutable ID; normalized unique username/email; password hash; password version; profile metadata; timestamps |
| `sessions` | token digest; user; password version; created/last-seen/expires/revoked timestamps |
| `communities` | immutable ID; normalized unique slug; name; creator; timestamps |
| `memberships` | community and user primary key; role; inviter; created/updated timestamps |
| `invitations` | digest; community; role; inviter; recipient kind/value; created/expires; state; accepted user/time; revoked time |
| `rate_limits` | opaque bucket digest; window start; count, including password-change attempts before scrypt |
| `audit_events` | immutable ID; event type; actor/subject/community/invitation references; timestamp; non-secret JSON metadata |
| `schema_migrations` | applied migration version and timestamp |

All timestamps are UTC epoch seconds. Usernames and emails compare case-insensitively after normalization. Display names preserve user casing. Avatar metadata is an optional `https://` URL of at most 512 characters; image bytes are not stored.

## Role and permission matrix

| Permission | Administrator | Coordinator | Member | Viewer |
| --- | :---: | :---: | :---: | :---: |
| Read community and membership-visible context | Yes | Yes | Yes | Yes |
| Declared future planning/Project permission (not enforced) | Yes | Yes | No | No |
| Declared future Project-participation permission (not enforced) | Yes | Yes | Yes | No |
| List members | Yes | No | No | No |
| Create/list/revoke invitations | Yes | No | No | No |
| Change a membership role | Yes, except removing the last Administrator | No | No | No |

The latter two Project permissions are declarations for the control centre. This slice does not edit or wrap protected reasoning or Project endpoints.

## HTTP contract

All request models reject unknown fields. Errors use the existing stable envelope `{"error":{"code":"STABLE_CODE","message":"Human-readable message.","details":{}}}`. Authentication is cookie-based; raw session tokens are never returned in JSON. The `assemble_session` cookie has an absolute seven-day lifetime; `now >= expires_at` is invalid and last-seen activity does not extend it. Successful signup, login and password change set a fresh cookie whose `Max-Age` and `Expires` match that persisted absolute expiry. Cookies are host-only, use path `/`, and omit `Domain`; logout clears the same name/path/security attributes even when the cookie is missing or stale. Auth and session responses use `Cache-Control: no-store`; the one-time invitation-token response also uses `Referrer-Policy: no-referrer`. Tokens never appear in URLs, logs or audit events.

Unsafe cookie-authenticated routes require `application/json`. A present `Origin` must equal one entry in the strict `ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS` HTTP(S) allow-list; it is never inferred from `Host` or forwarded headers. The comma-separated setting defaults to `http://localhost:3000,http://127.0.0.1:3000`, accepts no more than 32 unique canonical origins or 4096 UTF-8 bytes, supports explicit non-default frontend ports, and fails installation closed for empty, wildcard, credential-bearing, path/query/fragment-bearing, malformed, non-canonical or oversized values. A present `Sec-Fetch-Site` must be `same-origin` or `none`; absent browser headers remain valid for non-browser local clients. The client rate-limit identity is `request.client.host`. `X-Forwarded-For`, `X-Forwarded-Host` and `Host` never broaden the origin contract.

The auth request boundary matches complete namespace segments. `/api/auth`, `/api/communities` and `/api/invitations` are scoped; lookalikes such as `/api/authentic`, `/api/communities-v2` and `/api/invitations-old` fall through to the ordinary `404 ROUTE_NOT_FOUND` response.

| Method | Route | Success | Authentication and purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/signup` | 201 | Public; create account and rotated session |
| POST | `/api/auth/login` | 200 | Public; generic credential check and rotated session |
| GET | `/api/auth/session` | 200 | Session; return current user and memberships |
| POST | `/api/auth/logout` | 204 | Session when valid; idempotently revoke/clear cookie |
| POST | `/api/auth/password` | 200 | Session; verify current password, replace hash, revoke all sessions, issue one fresh session |
| PATCH | `/api/auth/profile` | 200 | Session; update optional display name/avatar metadata |
| POST | `/api/communities` | 201 | Session; create community and Administrator membership |
| GET | `/api/communities` | 200 | Session; list caller memberships |
| GET | `/api/communities/{community_id}/members` | 200 | Administrator; list members |
| PATCH | `/api/communities/{community_id}/members/{user_id}` | 200 | Administrator; change role with last-Administrator guard |
| POST | `/api/communities/{community_id}/invitations` | 201 | Administrator; create recipient-bound invite and return local-delivery token once |
| GET | `/api/communities/{community_id}/invitations` | 200 | Administrator; list redacted current lifecycle state |
| POST | `/api/communities/{community_id}/invitations/{invitation_id}/revoke` | 200 | Administrator; revoke a pending invite |
| POST | `/api/invitations/accept` | 200 | Session; atomically accept invite for the current normalized username/email |
| GET | `/api/communities/{community_id}/audit-events` | 200 | Administrator; list bounded newest-first audit evidence |

Invitation expiry is chosen by the Administrator from 5 minutes through 7 days. The default is 24 hours. Only one pending invitation may exist for a normalized recipient in a community. Existing members cannot be invited. An accepted invite is single-use. List responses never expose `token_hash` or the raw token.

## Stable auth errors

| Code | Typical status | Meaning |
| --- | --- | --- |
| `INVALID_REQUEST` | 422 | Strict JSON or field ceiling failed |
| `ACCOUNT_UNAVAILABLE` | 409 | Signup identity cannot be used; field is not disclosed, but the conflict status still reveals that some supplied identity is unavailable |
| `AUTHENTICATION_FAILED` | 401 | Login or current-password verification failed |
| `AUTHENTICATION_REQUIRED` | 401 | No current valid session |
| `PERMISSION_DENIED` | 403 | Persisted membership lacks permission |
| `COMMUNITY_UNAVAILABLE` | 409 | Requested community slug cannot be used |
| `COMMUNITY_NOT_FOUND` | 404 | Community is unknown or the caller has no membership; both use the same empty details |
| `MEMBERSHIP_NOT_FOUND` | 404 | Target membership does not exist in an administered community |
| `MEMBERSHIP_EXISTS` | 409 | Recipient is already a member |
| `PENDING_INVITATION_EXISTS` | 409 | A pending invite already covers the recipient |
| `INVITATION_NOT_AVAILABLE` | 404 | Token is invalid, wrong-recipient, expired, revoked, accepted or replayed |
| `INVITATION_NOT_PENDING` | 409 | Administrator attempted to revoke a non-pending invite |
| `LAST_ADMINISTRATOR_REQUIRED` | 409 | Role change would leave no Administrator |
| `RATE_LIMITED` | 429 | Persisted fixed-window bound was exceeded; response includes `Retry-After` |
| `SERVICE_BUSY` | 503 | SQLite could not obtain its bounded local lock; response includes `Retry-After: 1` |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Unsafe auth request is not JSON |
| `BROWSER_ORIGIN_REJECTED` | 403 | Present browser origin/fetch metadata violates the local same-origin contract |

Public token failures deliberately share status, code, message and empty details. Administrator-only lists provide explicit `PENDING`, `ACCEPTED`, `REVOKED`, and `EXPIRED` lifecycle evidence.

## Bounded rate-limit contract

Before expensive password or invitation verification, the backend consumes independent persisted fixed-window buckets. Every sensitive request consumes a scope-plus-`request.client.host` bucket and a separate scope-plus-normalized-identity bucket; signup consumes username and email identity buckets separately, while password change and invitation acceptance use the authenticated user ID and never a raw bearer. Forwarded client headers are ignored. Each bucket allows ten attempts per 60-second window for signup, login, password change and invitation acceptance independently. A successful attempt does not erase earlier attempts. Buckets survive restart; expired buckets may be compacted opportunistically. This bounds both repeated targeting and identity spraying in the local prototype; it is not a substitute for an edge rate limiter in a public deployment.

## Validation ceilings

- Request body: 16 KiB of actual received bytes. Auth-scoped middleware counts the ASGI stream and rejects absent, dishonest or oversized `Content-Length` bodies before Pydantic receives an unbounded buffer.
- Username: 3–64 characters, lowercase-normalized, letters/digits plus `.`, `_`, or `-`, beginning and ending alphanumeric.
- Email: 3–254 characters, basic single-`@` syntax, lowercase-normalized; ownership is not verified locally.
- Password: 12–128 Unicode characters and at least three of lowercase, uppercase, digit and symbol classes.
- Community name: 1–120 trimmed characters; slug: 3–64 normalized URL-safe characters.
- Display name: optional, 1–120 trimmed characters; avatar URL: optional HTTPS URL, at most 512 characters.
- Audit list limit: 1–200, default 100.

## Audit event contract

The slice records account creation, login success/failure, logout, password change, known-session rejection, community creation, membership creation, role change, invitation creation/revocation/expiry/acceptance and rate-limit rejection. Random unknown cookies do not create unbounded audit rows. Metadata contains only identifiers, roles, recipient kind and reason categories. Passwords, password hashes, session tokens/digests, raw invite tokens/digests, and full submitted recipients are forbidden. Database triggers reject audit-event updates and deletions.

Demoting an Administrator atomically revokes that inviter's still-pending invitations in the same community and records `INVITER_NO_LONGER_AUTHORISED`. This prevents a removed Administrator's unaccepted grants remaining live. The last-Administrator invariant is checked in the same immediate transaction.

The default store is `backend/.data/auth.sqlite3`; `ASSEMBLE_AUTH_DB_PATH` selects a different file. On POSIX, a newly created auth database directory is mode `0700`; the database and any WAL/SHM files are mode `0600`. Startup fails closed when an existing configured database or its directory grants group/other access. Windows relies on the host ACL and requires a deployment-specific review. SQLite lock acquisition is bounded; a busy/locked store returns the stable `503 SERVICE_BUSY` envelope rather than leaking a driver exception.

## Current verification evidence

The current integrated gate is 84 focused auth tests and 279 cumulative backend tests. The auth gate includes two-connection/thread races, a genuinely fresh application opened against the same SQLite file, direct secret-at-rest inspection, exact expiry boundaries, cookie/header/origin replay, actual streamed-byte overflow, locked-store translation and POSIX mode checks. The shared application imports and invokes `install_auth_api(app)` and its OpenAPI surface contains both existing and auth routes. This is backend integration evidence, not frontend identity availability, role-gating of non-auth routes, public-deployment readiness or independent product acceptance.
