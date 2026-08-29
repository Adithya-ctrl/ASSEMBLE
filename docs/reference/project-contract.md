# Project contract reference

## Create request

`POST /api/projects/from-plan` requires:

| Field | Contract |
| --- | --- |
| `base_community` | Exact authoritative demo state by canonical content, `state_id`, and `parent_state_id` |
| `initiative_id` | Known stable initiative ID |
| `catalyst_path` | Required ordered list containing 0–2 known action IDs; `[]` is the explicit no-catalyst plan |
| `title` | Trimmed length 3–100 |
| `short_description` | Trimmed length 20–280 |
| `objective` | Trimmed length 20–280 |

Metadata is normalized before validation, storage, and identity hashing. The request cannot provide Project status, readiness, assignments, venue, time, resources, source identity, or solver evidence.

## Proof behavior

- Empty path: analyse the authoritative base state directly.
- Non-empty path: replay each authoritative action in order, then analyse the resulting state.
- `OPTIMAL` or `FEASIBLE`: return HTTP 201 with a Project and fresh verification result.
- `INFEASIBLE` or `UNKNOWN`: return `409 PROJECT_PLAN_NOT_FEASIBLE`; do not emit a Project.
- Base content or lineage mismatch: return `409 COMMUNITY_STATE_MISMATCH` before transition or solving; do not emit a Project.

## Returned Project

The server derives:

- stable Project and source-plan IDs;
- source initiative and base/verified state IDs;
- normalized title, description, and objective;
- `READY` or `NOT_READY` status from readiness checks;
- replayed catalyst outputs and machine-readable diffs;
- venue, venue-derived host organisation, participant capacity, schedule, and occupied slots;
- operational role assignments with full selected-person and matched requirement facts;
- resource allocations;
- capability modules, accessibility requirements, and selected-team language union;
- readiness checks, evidence, and missing items;
- equal `created_at` and `updated_at` timestamps at creation.

There are no Project mutation, list, generic CRUD, task, project-membership, or project-role endpoints. Separate local account/community/invitation endpoints exist in FastAPI, but they do not role-gate this Project endpoint, are not linked to the solver fixture, and do not persist Projects.

## Identity

`source_plan_id` binds to the initiative, ordered path, state labels, and canonical content hashes of the base and verified states. Metadata edits do not change it. A canonical state or path change does.

`project.id` additionally binds normalized title, description, and objective. Metadata edits therefore create a different Project identity without changing the source-plan identity.
