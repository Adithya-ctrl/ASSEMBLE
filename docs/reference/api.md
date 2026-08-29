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

See [`project-contract.md`](project-contract.md) for the Project endpoint trust boundary.

No-applicable-actions and zero-unlock frontier outcomes are ordinary HTTP 200 analyses. Perturbed or recompiled `INFEASIBLE` and `UNKNOWN` outcomes are also returned as analysis responses, not transport errors.
