# B2-G3 pure-to-mounted coverage map

Status: `EXECUTED — PURE GATES GREEN; MOUNTED GAPS EXPLICIT`

This packet is scoped to pure frontend support, parser, state-machine and
stale-response checks. The set labels are coordinator-facing crosswalk IDs for
this lane; they do not replace the normative requirement names in
`docs/reference/requirements.md`.

## Authority and inspection boundary

| Item | Value |
| --- | --- |
| QA checkout | `a8b9797017668fcc4ae6e9634e2e67d7975ba23d` |
| Authoritative browser source | `453c84fc9c05495b1d21b91f505d8179019f296c` |
| Gauntlet specification | SHA-256 `97ab573c7e3b99dcee2f9a0bb9d7e00cb338b0a8714fc81a7604f5ff49b8f1f4` |
| Checked-out branch | `qa/absolute-adversarial-gauntlet` |
| Deterministic harness seed | `20260830` |
| Browser execution | Chrome 151 production runtime; definitive 37-step marathon plus supplemental gates |
| Browser adjudication | Row-level PASS/PARTIAL/NOT VERIFIED in `BROWSER_MATRIX_PREPARED.md` |

Inspected route and provider surfaces:

- `frontend/app/layout.tsx`, `frontend/app/(product)/**`, and `frontend/app/(account)/**`;
- `frontend/lib/workflow-context.tsx`, `identity-context.tsx`, `api.ts`,
  `auth-api.ts`, `auth-contract.ts`, `auth-session.ts`, `resilience-*.ts`,
  `preferences.ts`, `ui.ts`, and `workflow-types.ts`;
- `frontend/components/AssemblyProduct.tsx`, `shell/`, `project/`,
  `community/`, `community-admin/`, `identity/`, and `resilience/`;
- all seven existing frontend test files under `frontend/lib/`.

Dependency-backed frontend gates used the authoritative sibling checkout with
the same lockfile. The final product source passed 40 frontend tests, typecheck,
zero-warning lint and a production build of all 14 routes before browser
execution. The QA checkout remains an artifact/test overlay rather than a
second product runtime.

## Set crosswalk and nonvisual gaps

| Set | Contract focus | Pure coverage added here | Browser-only or integration gap left for root |
| --- | --- | --- | --- |
| F | Functional fixture, proof journey and Project gate (FR-001–015) | `projectProofGate` covers base proof, pending transition, wrong source/initiative, UNKNOWN, fully verified successor and duplicate/stale Project submit | Basic and Clinic Project journeys, Back/Forward, hard-refresh boundary and Reset mounted; forced mounted UNKNOWN remains unverified |
| Q | Malformed payloads and stable failure boundaries (NFR-001/003/007) | 25 auth plus 55 Resilience malformed cases reject deterministically | Mounted malformed Analyse and intentional 401/404/offline failures green; every auth/Resilience parser/status permutation is not mounted |
| R | Resilience and counterfactual isolation (FR-021–023, NFR-013) | Source/path/body binding, lane-local aborts, stale suppression and counterfactual no-mutation | S0/trained Stress, Recovery, Frontier and pending gate mounted; each Resilience lane was not independently delayed/reordered |
| X | Cross-surface continuity and parity (FR-002/016/017, NFR-004/005/011) | Detached request/state models protect source and Project boundaries | 80 responsive route rows, 2560 audit, Back/Forward, settings, keyboard, 200% and available 300% mounted; 400% capped |
| Y | Identity, RBAC, invitation and session continuity (FR-018–020, NFR-012) | Role-permission, expiry/error, one-shot token and duplicate-request models | Full two-account lifecycle/restart mounted; Viewer, forced expiry, Admin-loss 403 and revoke/expiry/race browser contexts remain unverified |

## Universal invariants

The pure harness asserts these invariants independently of React rendering:

1. A parser receives a canonical payload or rejects it with its contract error;
   no malformed fixture is silently coerced.
2. A response is bound to the requested source state, content hash, ordered
   catalyst path, initiative and (for recovery) exact perturbation binding.
3. Every request ticket is lane-local. A superseded or invalidated controller
   is aborted; a late resolution/rejection cannot commit data or become a new
   error. Invalidating Recovery leaves Stress and Frontier tickets current.
4. A Project gate admits only a feasible authoritative base proof or a fully
   applied, source-matching and independently verified successor. UNKNOWN,
   partial paths, foreign IDs and pending verification remain withheld.
5. A duplicate Project submit is suppressed; reset/invalidation clears the
   response and invalidates its nonce, so an old completion cannot repopulate
   Project state.
6. Auth-required and expiry events clear signed-in state; invalid credentials
   remain distinct from an inactive session; non-auth request failures do not
   fabricate a session.
7. Raw invitation tokens exist only in one-shot delivery state and are cleared
   by copy, dismiss, submit, request invalidation and unmount.
8. Counterfactual request bodies contain only backend contract fields and do
   not carry source hashes, generation metadata, operational state IDs or
   Project mappings.

## Open gaps, not silently fixed

- Firefox and WebKit/Safari were not available to this run.
- Requested 400% zoom was clamped to measured 300% by Chrome 151 headless/CDP;
  400% is NOT VERIFIED, while formal 200% and available 300% reflow are green.
- The full Cartesian visual matrix, mounted Viewer/expiry/Admin-loss scenarios,
  every injected frontend status/parser case and every delayed async lane were
  not executed. Pure and backend coverage for many of these boundaries is
  green but is not mislabelled as mounted browser evidence.
- The generic Resilience response records reject operational mappings and
  malformed known fields. No product parser decision was changed in this lane.
