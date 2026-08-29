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
| M6 route-backed modular interface | Accepted | Independent frozen-source production replay passed across routes, proof journeys, preferences, responsive layouts and accessibility checks |
| M6 documentation reconciliation | Accepted | Current architecture, requirements, traceability, tutorials and presentation guidance passed the independent current-state audit |

Builder evidence must not be relabelled as independent acceptance.

## Current cumulative evidence

- Backend: `145 passed`; one upstream Starlette `httpx` deprecation warning.
- Latest ordered-path/API focused gate: `53 passed`.
- Interface: TypeScript check passes; ESLint passes with zero warnings; Next.js 16.3.3 production build passes.
- Modular routes: Overview, Community, Initiatives, dynamic Initiative Proof, Projects, Project Proof, and Preferences resolve as real product routes under a shared workflow provider. Unknown and malformed Initiative Proof paths fail visibly without selecting a fallback initiative.
- Route persistence: one root-mounted provider preserves the same in-memory Project through Projects → Project Proof → Back → Forward at 1440 and 320; direct refresh truthfully resets to the empty session state. A deterministic layout-boundary check prevents a duplicate or route-group provider from returning.
- Community: Overview, People, Places, and Resources render one category at a time; all eight fixture entities remain reachable in equivalent graph/list representations with one focused detail surface and technical disclosure.
- Core live journey: compile, analyse, explain, unlock, plan, ordered transition and successor verification use the real backend. The Clinic reaches `OPTIMAL` only after the cost-2 training action and successor verification. Four actions produce 16 ordered depth-two candidates.
- Project API: `POST /api/projects/from-plan` creates only from the authoritative fixture plus an explicit 0–2 action path. Forged state content or lineage, unsafe client proof fields, invalid paths, whitespace metadata, INFEASIBLE and UNKNOWN all fail closed without a Project.
- Project browser journey: Basic creates `READY` from explicit `[]`; Clinic exposes no Project form before successor verification and creates `READY` from `TRAIN_DIGITAL_HELPERS` afterward.
- Accessibility: category/detail graph-list parity; one journey announcement; dedicated Project proof and Inspector focus; system/light/dark and high contrast; opaque focus; reduced motion; 1440, 768, 390 and 320 layouts plus 200% reflow equivalent; no visible target below 44px; no browser console warning/error. Builder Lighthouse snapshots scored 100 accessibility with 34 passed and zero failed audits on desktop and mobile; this is not formal conformance.
- Full platform parity: independent replay confirmed all five navigation destinations, four Community categories, all eight entities, six proof actions, three editable Project fields, complete Project/Project-proof capability, Preferences, Judge Proof Mode, and the truthful account boundary at 320 and 1440, with no document/navigation overflow or visible sub-44px target.
- Preferences and layout checks: four frontend unit checks pass. The versioned `assemble_ui_preferences` cookie contains only theme, contrast, motion, and preferred inventory view; invalid, oversized, and stale-version values fail closed. Judge Proof Mode is session-only.
- Documentation: current requirements, user stories, traceability, two-layer drift audit, exact 3:00 video, exact 4:00 live-demo runbook, and bounded judge Q&A are structurally gated and require human semantic replay.
- Integrity: feasible witnesses are canonically replayed; malformed feasible analyser output fails with `ANALYSER_CONTRACT_ERROR`; missing referenced resources remain infeasible under every permitted relaxation; non-feasible/UNKNOWN solver results cannot carry an objective or witness; explicit collection ceilings return 422; no-op transitions and already-feasible unlocks are rejected.

## Current checkpoint

P0-A Project and integrity hardening is independently accepted. M6's route-backed modular product presentation, progressive disclosure, Community category/detail experience, dedicated Project surfaces, appearance preferences, and responsive navigation are also independently accepted after frozen-source static and production-browser replay.

Authentication, invitations, community roles, membership, and persistence remain outside this checkout's accepted product surface. The account control truthfully reports that identity is unavailable; no role-specific behavior is claimed.

## Intentionally absent

The current product does not include:

- authentication, accounts, sessions, or role-based access control;
- generic Project CRUD, tasks, manual assignment, project membership, or persistence;
- cloud services, OAuth, LLM dependence, or external data ingestion;
- deployment, publication, public repository visibility, or submission.

Do not recreate or claim these capabilities without a separately authorised contract, implementation mission, tests, documentation update, and acceptance gate.
