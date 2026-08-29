# Security and validation reference

ASSEMBLE is currently a localhost, deterministic fixture application. It does not provide accounts, sessions, cloud persistence, OAuth, deployment, or external data ingestion.

## Trust boundaries

| Input | Trust decision |
| --- | --- |
| Community state used by analyse/explain | Strictly schema-validated bounded input; result applies only to that submitted state |
| Action catalogue used by reasoning routes | Must exactly match the disclosed server catalogue |
| Project base community | Must exactly match authoritative fixture content and identity/lineage |
| Project catalyst path | Required, ordered, unique, known, and bounded to 0–2 actions |
| Project metadata | Trimmed and length-validated; extra fields rejected |
| Assignments/readiness/status | Never trusted from the client; always derived server-side |

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

## Fail-closed behavior

- Missing referenced initiative resources remain non-relaxable integrity failures.
- UNKNOWN never becomes infeasible or feasible and never carries a partial witness.
- A decoded feasible witness that fails canonical replay is an internal contract breach returned as `500 ANALYSER_CONTRACT_ERROR`; it is not relabelled UNKNOWN.
- An infeasible or unknown Project proof returns `409 PROJECT_PLAN_NOT_FEASIBLE` without a Project object.
- A forged base state returns `409 COMMUNITY_STATE_MISMATCH` before Project transition or solving.
- Reapplying an already-present additive effect returns a stable conflict instead of a false successful transition.
- Framework and domain failures use stable error envelopes.

## Current adversarial coverage

Tests cover forged capabilities, resource quantity, space availability and lineage under the same `S0` label; whitespace-only metadata; omitted and extra fields; unknown, duplicate, overlong, insufficient, and already-applied paths; unsafe status/witness combinations and adversarial trace/objective facts; missing referenced IDs; collection overflow; numeric booleans and strings; wrong methods; and unknown routes.

## Deliberately absent

Authentication and role-based access control are not current capabilities. Do not describe the application as multi-user, authenticated, private, or deployment-ready. A future security mission requires a new current contract, threat model, tests, and documentation update before implementation.
