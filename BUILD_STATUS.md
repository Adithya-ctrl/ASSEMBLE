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
| Local identity, community membership and invitations | Accepted | Independent local browser replay passed signup/login, session lifecycle, Settings, Collaboration roles, invitations, audit, restart persistence and permission boundaries |
| M7 Resilience Lab | Accepted | Independent cumulative replay passed the dedicated Stress, Recovery and Capability frontier product surface against all three integrated APIs |
| Calm civic workspace visual system | Accepted | Independent 1440/390/320 review accepted the single navigation system, focused Community browser, route-wide visual grammar and responsive correction |

Builder evidence must not be relabelled as independent acceptance.

## Current cumulative evidence

- Backend: `279 passed`; one upstream Starlette `httpx` deprecation warning. The suite runs against a private temporary `ASSEMBLE_AUTH_DB_PATH`, not the default persistent file.
- Auth: `84 passed` in `backend/tests/auth`; signup/session/logout, password rotation, persisted community roles, invitation lifecycle, restart, secret-at-rest, origin/body/rate bounds, concurrency, and POSIX permission checks are covered.
- Structural resilience: stress-test, minimum-disruption recompile and capability-frontier API/runtime suites pass as part of the cumulative gate. Their counterfactual receipts are not operational Project states.
- Latest ordered-path/API focused gate: `53 passed`.
- Interface: `35/35` focused frontend tests pass; TypeScript check passes; ESLint passes with zero warnings; Next.js 16.3.3 production build passes.
- Modular routes: Overview, demo Community, Initiatives, dynamic Initiative Proof, Projects, Project Proof, Resilience, identity entry, Settings, Collaboration spaces and dynamic community administration resolve as real routes. `/preferences` redirects to Settings. Unknown and malformed Initiative Proof paths fail visibly without selecting a fallback initiative.
- Route persistence: one root-mounted provider preserves the same in-memory Project through Projects → Project Proof → Back → Forward at 1440 and 320; direct refresh truthfully resets to the empty session state. A deterministic layout-boundary check prevents a duplicate or route-group provider from returning.
- Community: Overview, People, Places, and Resources render one category at a time; all eight fixture entities remain reachable in equivalent graph/list representations with one focused detail surface and technical disclosure.
- Core live journey: compile, analyse, explain, unlock, plan, ordered transition and successor verification use the real backend. The Clinic reaches `OPTIMAL` only after the cost-2 training action and successor verification. Four actions produce 16 ordered depth-two candidates.
- Project API: `POST /api/projects/from-plan` creates only from the authoritative fixture plus an explicit 0–2 action path. Forged state content or lineage, unsafe client proof fields, invalid paths, whitespace metadata, INFEASIBLE and UNKNOWN all fail closed without a Project.
- Project browser journey: Basic creates `READY` from explicit `[]`; Clinic exposes no Project form before successor verification and creates `READY` from `TRAIN_DIGITAL_HELPERS` afterward.
- Accessibility: category/detail graph-list parity; one scoped application announcement per active shell, including planning and identity actions; dedicated Project proof and Inspector focus; system/light/dark and high contrast; opaque focus; reduced motion; 1440, 768, 390 and 320 layouts plus 200% reflow equivalent; no visible target below 44px; no browser console warning/error. Builder Lighthouse snapshots scored 100 accessibility with 34 passed and zero failed audits on desktop and mobile; this is not formal conformance.
- Full platform parity: accepted evidence covers the six product destinations, proof workflow, guest account/Settings access, authenticated Collaboration and Administrator controls, and all three Resilience tasks at 320, 390 and 1440, with no document overflow or effective sub-44px control.
- Preferences and layout checks: all 15 focused frontend checks pass, including strict auth response binding, stable error preservation, session-expiry boundaries, provider persistence, focus return, navigation and preference-cookie validation. The versioned `assemble_ui_preferences` cookie contains only theme, contrast, motion, and preferred inventory view; invalid, oversized, and stale-version values fail closed. Judge Proof Mode is session-only.
- Documentation: current requirements through FR-023, NFR-013 and US-017, traceability, two-layer drift audit, exact 3:00 video, exact 4:00 live-demo runbook, and bounded judge Q&A are structurally gated and require human semantic replay.
- Integrity: feasible witnesses are canonically replayed; malformed feasible analyser output fails with `ANALYSER_CONTRACT_ERROR`; missing referenced resources remain infeasible under every permitted relaxation; non-feasible/UNKNOWN solver results cannot carry an objective or witness; explicit collection ceilings return 422; no-op transitions and already-feasible unlocks are rejected.

## Current checkpoint

P0-A Project and integrity hardening is independently accepted. M6's route-backed modular product presentation, progressive disclosure, Community category/detail experience, dedicated Project surfaces, appearance preferences, and responsive navigation are also independently accepted after frozen-source static and production-browser replay.

Phase A independently connects local authentication, invitations, community roles, membership and SQLite persistence to dedicated frontend surfaces without changing the accepted planning proof chain. The account menu supports guest entry and authenticated profile/logout; Settings separates Account, Security and Appearance; Collaboration separates persisted spaces from the fictional demo; and only Administrators receive member, invitation and audit controls. Independent browser replay covered stable 401/403/409 handling, scheduled session expiry, immediate cached-session invalidation after revocation, authoritative role-loss refresh, 204 logout, profile update, one-time token removal, Viewer read-only behavior, scoped live announcements, failure visibility, responsive parity, and SQLite persistence.

Phase B adds a dedicated Resilience route with Stress, Recovery and Capability frontier tasks. It always submits canonical S0 plus the authoritative verified catalyst path, blocks while a transition awaits verification, keeps independent abort/generation lanes, and never writes counterfactual scenarios into planning or Project state. Independent replay covered Basic S0 stress at 0/4 resilient, trained Clinic stress at 0/6 resilient, trained Basic recovery with one changed assignment and burden 24, and the S0/trained frontier boundaries. Reasoning, Project and M7 endpoints remain outside community-role permissions. Projects and Project proof remain in memory.

## Intentionally absent

The current product does not include:

- role-gating for solver, reasoning, Project or M7 endpoints, despite persisted roles and declared future planning permissions;
- generic Project CRUD, tasks, manual assignment, project membership, or persistence;
- cloud services, OAuth, LLM dependence, or external data ingestion;
- deployment, publication, public repository visibility, or submission.

Do not recreate or claim these capabilities without a separately authorised contract, implementation mission, tests, documentation update, and acceptance gate.
