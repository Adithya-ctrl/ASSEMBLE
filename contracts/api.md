# Frozen API contract — M0

All endpoints use JSON. Unknown fields are rejected. IDs and result language are stable. `UNKNOWN` must never be converted to `INFEASIBLE`.

Backend errors use:

```json
{"error":{"code":"STABLE_CODE","message":"Human-readable message","details":{}}}
```

## Endpoints

- `GET /api/health` returns `{"status":"ok","solver":"ortools-cp-sat"}`.
- `GET /api/demo` returns the authoritative `fixture_version`, `community`, `initiatives`, and `actions`.
- `POST /api/analyse` accepts `community` and non-empty `initiative_ids`; returns compile counts and one genuine solver result per requested initiative.
- `POST /api/explain` accepts `community` and one `initiative_id`; returns bounded relax-and-resolve evidence.
- `POST /api/unlock` accepts `community`, one `initiative_id`, and the disclosed `actions`; returns the minimum result under the frozen finite catalogue and cost function.
- `POST /api/plan` accepts the unlock request plus fixed `max_depth: 2` and `max_expanded_states <= 20`; returns the bounded BFS trace.
- `POST /api/transition` accepts `community`, `action_id`, and `actions`; returns a new immutable successor state and machine-readable diff.

`POST /api/reassemble` is outside Core Acceptance and is not part of M0.

## Frozen result types

Solver status is exactly one of `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, or `UNKNOWN`.

Requirement groups are exactly:

- `role_capability`
- `language`
- `availability`
- `venue_feature`
- `venue_capacity`
- `resource_quantity`
- `maximum_contribution`

The executable source of truth is `backend/app/api_models.py`. `contracts/examples/api_examples.json` contains endpoint-specific example overlays. Gate 0 combines those overlays with the authoritative demo fixture and validates every assembled request and response against the frozen Pydantic models. Response numbers are contract-shape examples at M0, not solver evidence; integration replaces displayed values with actual runtime results.

## Ownership

These contracts, `backend/app/models.py`, `backend/app/api_models.py`, and the demo fixture are manager-owned and read-only during the first parallel wave. A worker must stop and report if a frozen interface is insufficient.

