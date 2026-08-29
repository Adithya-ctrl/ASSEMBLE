# ASSEMBLE API contract pointer

The executable contract is defined by:

- `backend/app/models.py` for community, initiative, action, and stable-ID models;
- `backend/app/api_models.py` for solver and reasoning HTTP models;
- `backend/app/project_models.py` for executable Project models;
- `backend/app/main.py` for routes, statuses, CORS, and stable error translation.

The canonical current human-readable reference is [`../docs/reference/api.md`](../docs/reference/api.md). Project-specific trust and identity rules are in [`../docs/reference/project-contract.md`](../docs/reference/project-contract.md).

All endpoints use JSON. Unknown fields are rejected. `UNKNOWN` is never converted to `INFEASIBLE`. Errors use the stable envelope:

```json
{"error":{"code":"STABLE_CODE","message":"Human-readable message","details":{}}}
```

`contracts/examples/api_examples.json` contains validated examples for the core solver and reasoning requests and responses. Examples demonstrate contract shape; runtime evidence comes only from actual endpoint execution.

Any route, model, status, invariant, or stable-error change must update the executable contract, current reference, examples when affected, traceability, tests, and build status in the same change.
