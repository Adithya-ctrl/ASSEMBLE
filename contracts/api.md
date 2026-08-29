# ASSEMBLE API contract pointer

The executable contract is defined by:

- `backend/app/models.py` for community, initiative, action, and stable-ID models;
- `backend/app/api_models.py` for solver and reasoning HTTP models;
- `backend/app/project_models.py` for executable Project models;
- `backend/app/resilience.py`, `backend/app/recompiler.py`, and `backend/app/frontier.py` for backend-only counterfactual analyses;
- `backend/app/auth/` for local identity, persisted membership, invitations and the installed auth router;
- `backend/app/main.py` for integrated routes, statuses, CORS, and stable error translation.

The canonical current human-readable route reference is [`../docs/reference/api.md`](../docs/reference/api.md). Project-specific trust rules are in [`../docs/reference/project-contract.md`](../docs/reference/project-contract.md); local identity and invitation semantics are in [`../docs/reference/identity-community-invitations.md`](../docs/reference/identity-community-invitations.md); structural-resilience semantics are in [`technical-differentiation-api.md`](technical-differentiation-api.md).

All endpoints use JSON. Unknown fields are rejected. `UNKNOWN` is never converted to `INFEASIBLE`. Errors use the stable envelope:

```json
{"error":{"code":"STABLE_CODE","message":"Human-readable message","details":{}}}
```

`contracts/examples/api_examples.json` contains validated examples for the core solver and reasoning requests and responses. Examples demonstrate contract shape; runtime evidence comes only from actual endpoint execution.

Authentication protects only the auth and community-administration routes named in its contract. The existing solver, reasoning, Project, stress-test, recompile and frontier routes are deliberately not role-gated at this checkpoint. Auth/community/invitation data is the only file-backed application state; Projects and proof context remain in memory, and none of the auth or M7 APIs has a current frontend workflow.

Any route, model, status, invariant, or stable-error change must update the executable contract, current reference, examples when affected, traceability, tests, and build status in the same change.
