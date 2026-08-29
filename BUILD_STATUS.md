# ASSEMBLE current build status

Last independent acceptance: 2026-08-29 AEST.

This page records current health only. Architectural history and superseded decisions belong in [`docs/adr/`](docs/adr/README.md).

## Acceptance state

| Current area | Status | Acceptance evidence |
| --- | --- | --- |
| Deterministic solver, explanation, unlock, transition and planner core | Accepted | Independent cumulative tests and complete real six-action journey |
| Evidence-first civic interface | Accepted | Independent production-browser, responsive, truthfulness and accessibility replay |
| Solver-derived executable Projects | Accepted | Independent authoritative replay, cumulative tests, production build and both real Project journeys |
| Living current documentation | Accepted | Independent Diátaxis navigation, current-state semantics, traceability and automated drift gate |

Builder evidence must not be relabelled as independent acceptance.

## Current cumulative evidence

- Backend: `144 passed`; one upstream Starlette `httpx` deprecation warning.
- Latest ordered-path/API focused gate: `53 passed`.
- Interface: TypeScript check passes; ESLint passes with zero warnings; Next.js 16.3.3 production build passes.
- Core live journey: compile, analyse, explain, unlock, plan, ordered transition and successor verification use the real backend. The Clinic reaches `OPTIMAL` only after the cost-2 training action and successor verification. Four actions produce 16 ordered depth-two candidates.
- Project API: `POST /api/projects/from-plan` creates only from the authoritative fixture plus an explicit 0–2 action path. Forged state content or lineage, unsafe client proof fields, invalid paths, whitespace metadata, INFEASIBLE and UNKNOWN all fail closed without a Project.
- Project browser journey: Basic creates `READY` from explicit `[]`; Clinic exposes no Project form before successor verification and creates `READY` from `TRAIN_DIGITAL_HELPERS` afterward.
- Accessibility: graph/list eight-block fact parity; one journey announcement; source-proof inspector focus; high contrast; opaque focus; reduced motion; 1440, 1280, 768, 390 and 320 layouts; 200% reflow equivalent; no visible target below 44px; no browser console warning/error.
- Full platform parity: independent replay found the same visible control sequence, three editable Project fields and complete Project-proof rows at 320 and 1440, with no document/key-region overflow or visible sub-44px target. Builder replay additionally compared 26 completed-Project evidence items and seven selected-team facts at both widths.
- Documentation: current requirements, user stories, traceability, two-layer drift audit, exact 3:00 video, exact 4:00 live-demo runbook, and bounded judge Q&A are structurally gated and require human semantic replay.
- Integrity: feasible witnesses are canonically replayed; malformed feasible analyser output fails with `ANALYSER_CONTRACT_ERROR`; missing referenced resources remain infeasible under every permitted relaxation; non-feasible/UNKNOWN solver results cannot carry an objective or witness; explicit collection ceilings return 422; no-op transitions and already-feasible unlocks are rejected.

## Current checkpoint

P0-A Project and integrity hardening is independently accepted. The backend passed 144 tests; frontend typecheck, zero-warning lint and the Next.js production build passed; the documentation gate passed 9 tests; and the real Basic/Clinic browser journeys, Project proof, Reset recovery and 320/1440 parity were independently replayed. No implementation defect is known from this accepted snapshot.

The requested modular authentication, invitations, community roles, settings and multi-page product experience are the next separately contracted milestone. They are not present in this checkpoint.

## Intentionally absent

The current product does not include:

- authentication, accounts, sessions, or role-based access control;
- generic Project CRUD, tasks, manual assignment, project membership, or persistence;
- cloud services, OAuth, LLM dependence, or external data ingestion;
- deployment, publication, public repository visibility, or submission.

Do not recreate or claim these capabilities without a separately authorised contract, implementation mission, tests, documentation update, and acceptance gate.
