# HTTP API reference

The API uses strict JSON models. Unknown fields are rejected. Errors use:

```json
{
  "error": {
    "code": "STABLE_CODE",
    "message": "Human-readable message.",
    "details": {}
  }
}
```

Framework 404 and 405 responses use the same envelope. Malformed request bodies use `422 INVALID_REQUEST`.

## Routes

| Method | Route | Success | Purpose |
| --- | --- | --- | --- |
| GET | `/api/health` | 200 | Report API and CP-SAT solver health |
| GET | `/api/demo` | 200 | Return the deterministic fictional fixture |
| POST | `/api/analyse` | 200 | Compile and solve one or more initiatives against the submitted bounded state |
| POST | `/api/explain` | 200 | Find solver-confirmed blocking requirement sets |
| POST | `/api/unlock` | 200 | Find the minimum sufficient executable ordered path, limited to two actions |
| POST | `/api/plan` | 200 | Trace a bounded depth-two catalyst path |
| POST | `/api/transition` | 200 | Apply one authoritative action to a copied state and return its diff |
| POST | `/api/stress-test` | 200 | Analyse the complete canonical structural-perturbation catalogue without changing operational lineage |
| POST | `/api/recompile` | 200 | Find a proven minimum-disruption replacement for one canonical perturbation |
| POST | `/api/frontier` | 200 | Compare each authoritative action independently as a one-action capability frontier |
| POST | `/api/projects/from-plan` | 201 | Replay a 0–2 action plan, solve it, and derive an executable Project |
| POST | `/api/auth/signup` | 201 | Create a local account and start a rotated cookie session |
| POST | `/api/auth/login` | 200 | Verify credentials and start a rotated cookie session |
| GET | `/api/auth/session` | 200 | Return the current user and community memberships |
| POST | `/api/auth/logout` | 204 | Revoke the current session and clear its cookie idempotently |
| POST | `/api/auth/password` | 200 | Change the password, revoke prior sessions, and rotate the current session |
| PATCH | `/api/auth/profile` | 200 | Update the current user's display name or avatar metadata |
| POST | `/api/communities` | 201 | Create a community with the caller as Administrator |
| GET | `/api/communities` | 200 | List communities in which the caller is a member |
| GET | `/api/communities/{community_id}/members` | 200 | List members as a Community Administrator |
| PATCH | `/api/communities/{community_id}/members/{user_id}` | 200 | Change a member role while preserving the last Administrator |
| POST | `/api/communities/{community_id}/invitations` | 201 | Create a recipient-bound invitation and return its local-delivery token once |
| GET | `/api/communities/{community_id}/invitations` | 200 | List redacted invitation lifecycle state as an Administrator |
| POST | `/api/communities/{community_id}/invitations/{invitation_id}/revoke` | 200 | Revoke a pending invitation as an Administrator |
| POST | `/api/invitations/accept` | 200 | Atomically accept an invitation bound to the current user |
| GET | `/api/communities/{community_id}/audit-events` | 200 | List bounded, non-secret community audit evidence |

## Solver result invariant

- `OPTIMAL` and `FEASIBLE` include a non-null objective, assignments, and assembly trace.
- `INFEASIBLE` and `UNKNOWN` include no objective, assignments, or trace.

## Stable error codes

| Code | Typical status | Meaning |
| --- | --- | --- |
| `INVALID_REQUEST` | 422 | JSON does not match the strict contract |
| `INVALID_REFERENCE` | 404 | Initiative or action ID is unknown |
| `INVALID_ACTION_CATALOGUE` | 422 | Client action catalogue contains duplicate action IDs |
| `ACTION_CATALOGUE_MISMATCH` | 422 | Client action catalogue differs from the server catalogue |
| `ACTION_ALREADY_APPLIED` | 409 | Additive action would produce no change |
| `ALREADY_FEASIBLE` | 409 | Unlock was requested for an already feasible initiative |
| `TRANSITION_NOT_ALLOWED` | 409 | Action precondition or transition invariant failed |
| `NO_UNLOCK_PATH` | 422 | No disclosed ordered action path of depth at most two unlocks the initiative |
| `NO_PLAN_FOUND` | 422 | Bounded planner found no successor proof |
| `COMMUNITY_STATE_MISMATCH` | 409 | Project or counterfactual-analysis base differs from the authoritative fixture |
| `PROJECT_PLAN_NOT_FEASIBLE` | 409 | Replayed Project plan is INFEASIBLE or UNKNOWN |
| `BASELINE_NOT_FEASIBLE` | 409 | Stress or recompile baseline is not decisively feasible |
| `INVALID_PERTURBATION` | 404 | Requested perturbation is not in the server-generated canonical catalogue |
| `PERTURBATION_CATALOGUE_TOO_LARGE` | 422 | Complete canonical stress catalogue exceeds the hard ceiling of 20; no partial metric is returned |
| `ROUTE_NOT_FOUND` | 404 | API route does not exist |
| `METHOD_NOT_ALLOWED` | 405 | Method is not allowed on the route |
| `ANALYSER_CONTRACT_ERROR` | 500 | An internal analyser returned a result that violates its contract |
| `HTTP_ERROR` | framework status | A non-404/405 framework HTTP failure was normalized to the stable envelope |
| `ACCOUNT_UNAVAILABLE` | 409 | A signup username or email cannot be used |
| `AUTHENTICATION_FAILED` | 401 | Login or current-password verification failed |
| `AUTHENTICATION_REQUIRED` | 401 | No current valid session is available |
| `PERMISSION_DENIED` | 403 | The persisted community role lacks permission |
| `COMMUNITY_UNAVAILABLE` | 409 | A requested community slug cannot be used |
| `COMMUNITY_NOT_FOUND` | 404 | The community is unknown or unavailable to the caller |
| `MEMBERSHIP_NOT_FOUND` | 404 | The target membership does not exist in the administered community |
| `MEMBERSHIP_EXISTS` | 409 | The invitation recipient is already a community member |
| `PENDING_INVITATION_EXISTS` | 409 | A pending invitation already covers the recipient |
| `INVITATION_NOT_AVAILABLE` | 404 | An invitation is invalid, unavailable, expired, revoked, accepted, or bound to another user |
| `INVITATION_NOT_PENDING` | 409 | An Administrator attempted to revoke a non-pending invitation |
| `LAST_ADMINISTRATOR_REQUIRED` | 409 | A role change would leave the community without an Administrator |
| `RATE_LIMITED` | 429 | A persisted authentication rate limit was exceeded |
| `SERVICE_BUSY` | 503 | SQLite could not obtain its bounded local lock |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | An unsafe authentication request was not JSON |
| `BROWSER_ORIGIN_REJECTED` | 403 | Browser origin or fetch metadata violated the local same-origin contract |

See [`project-contract.md`](project-contract.md) for the Project endpoint trust boundary.
See [`identity-community-invitations.md`](identity-community-invitations.md) for cookie, role, invitation, persistence, and security semantics.

No-applicable-actions and zero-unlock frontier outcomes are ordinary HTTP 200 analyses. Perturbed or recompiled `INFEASIBLE` and `UNKNOWN` outcomes are also returned as analysis responses, not transport errors.
