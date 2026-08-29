# ASSEMBLE current build status

Last independent acceptance: 2026-08-30 AEST.

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
| Civic Toybox spatial visual system | Accepted | Independent visual review accepted the image-led civic workbench with no P0/P1; the final bounded P2 polish has builder static and production-browser evidence |
| Absolute adversarial acceptance gauntlet | **HOLD — not release-accepted** | Every completed row passed and no product defect remains open within those rows, but the explicitly unverified cross-browser, 400% zoom, screen-reader, Cartesian, mounted-permutation, boss-fight, mutation and randomized-browser work prevents an exhaustive release statement. See the [supporting evidence ledger](docs/ADVERSARIAL_ACCEPTANCE_REPORT.md). |

Builder evidence must not be relabelled as independent acceptance.

## Current cumulative evidence

- Complete backend collection: `1,975/1,975 passed`; one upstream Starlette `httpx` deprecation warning. The non-adversarial backend subset is `395/395 passed`, and the original-plus-adversarial auth subset is `192/192 passed`. Every run uses a private temporary `ASSEMBLE_AUTH_DB_PATH`, not the default persistent file.
- Structural resilience: stress-test, minimum-disruption recompile and capability-frontier API/runtime suites pass as part of the cumulative gate. Their counterfactual receipts are not operational Project states.
- Interface: `40/40` focused frontend tests and `17/17` adversarial TypeScript harness tests pass; TypeScript check passes; ESLint passes with zero warnings; Next.js 16.3.3 production build passes with 14 routes.
- Documentation and source audit: `11/11` deterministic documentation tests and `6/6` adversarial audit-wrapper tests pass; the read-only audit reports `PASS` with zero findings.
- Modular routes: Overview, demo Community, Initiatives, dynamic Initiative Proof, Projects, Project Proof, Resilience, identity entry, Settings, Collaboration spaces and dynamic community administration resolve as real routes. `/preferences` redirects to Settings. Unknown and malformed Initiative Proof paths fail visibly without selecting a fallback initiative.
- Route persistence: one root-mounted provider preserves the same in-memory Project through Projects → Project Proof → Back → Forward at 1440 and 320; direct refresh truthfully resets to the empty session state. A deterministic layout-boundary check prevents a duplicate or route-group provider from returning.
- Community: Overview, People, Places, and Resources render one category at a time; all eight fixture entities remain reachable in equivalent graph/list representations with one focused detail surface and technical disclosure. Human-facing availability labels are chronological without mutating authoritative source arrays.
- Core live journey: compile, analyse, explain, unlock, plan, ordered transition and successor verification use the real backend. The Clinic reaches `OPTIMAL` only after the cost-2 training action and successor verification. Four actions produce 16 ordered depth-two candidates.
- Project API: `POST /api/projects/from-plan` creates only from the authoritative fixture plus an explicit 0–2 action path. Forged state content or lineage, unsafe client proof fields, invalid paths, whitespace metadata, INFEASIBLE and UNKNOWN all fail closed without a Project.
- Project browser journey: Basic creates `READY` from explicit `[]`; Clinic exposes no Project form before successor verification and creates `READY` from `TRAIN_DIGITAL_HELPERS` afterward.
- Accessibility: category/detail graph-list parity; one scoped application announcement per active shell, including planning and identity actions; dedicated Project proof and Inspector focus; meaningful scene alternatives or intentionally empty decorative alternatives; system/light/dark and high contrast; opaque focus; reduced motion; no visible target below 44px in the executed matrix. The definitive Chrome replay covered 200% zoom and the environment's measured 300% maximum; 400% and a complete screen-reader journey remain unverified. Earlier Builder Lighthouse snapshots are supporting implementation checks, not formal conformance.
- Full platform parity: the definitive 37-step Chrome marathon passed, as did 80 responsive route rows from 320 through 1920 CSS pixels and a separate 2560-pixel audit. Completed rows cover proof workflows, identity and Collaboration, resilience, themes, keyboard operation, console/network adjudication and restart persistence. This is not cross-browser or exhaustive release acceptance.
- Preferences and layout checks: all focused frontend checks pass, including strict auth and M7 response binding, stable error preservation, session-expiry boundaries, provider persistence, chronological availability presentation, focus return, Civic Scene motion structure, navigation and preference-cookie validation. The versioned `assemble_ui_preferences` cookie contains only theme, contrast, motion, and preferred inventory view; invalid, oversized, and stale-version values fail closed. Judge Proof Mode is session-only.
- Documentation: current requirements through FR-023, NFR-013 and US-017, traceability, two-layer drift audit, exact 3:00 video, exact 4:00 live-demo runbook, and bounded judge Q&A are structurally gated and require human semantic replay.
- Integrity: analyser calls preserve their submitted community and initiative, bind returned status to the requested initiative, and enforce status/witness/objective consistency before reasoning; feasible witnesses are canonically replayed. Missing referenced resources remain infeasible under every permitted relaxation; non-feasible/UNKNOWN solver results cannot carry an objective or witness; strict scalar and collection boundaries reject coercive or oversized inputs; no-op transitions and already-feasible unlocks are rejected.

## Adversarial release gate

The [absolute adversarial acceptance report](docs/ADVERSARIAL_ACCEPTANCE_REPORT.md) is the supporting A–Z evidence ledger; this file remains the canonical owner of current release status and gate counts. All completed gauntlet rows pass, all defects found in those rows have been repaired and replayed, and no product defect remains open within the completed scope.

Exhaustive release acceptance is still withheld. The following work was not verified and must not be inferred from the completed rows:

- Firefox and WebKit/Safari execution;
- requested 400% zoom, because the automated Chrome environment measured a 300% maximum;
- the complete state × viewport × theme screenshot Cartesian product and a full screen-reader journey;
- every mounted asynchronous, parser, RBAC and race permutation, and every named boss fight verbatim;
- mutation testing and randomized browser monkey testing.

## Current checkpoint

P0-A Project and integrity hardening is independently accepted. M6's route-backed modular product presentation, progressive disclosure, Community category/detail experience, dedicated Project surfaces, appearance preferences, and responsive navigation are also independently accepted after frozen-source static and production-browser replay.

Phase A independently connects local authentication, invitations, community roles, membership and SQLite persistence to dedicated frontend surfaces without changing the accepted planning proof chain. The account menu supports guest entry and authenticated profile/logout; Settings separates Account, Security and Appearance; Collaboration separates persisted spaces from the fictional demo; and only Administrators receive member, invitation and audit controls. Independent browser replay covered stable 401/403/409 handling, scheduled session expiry, immediate cached-session invalidation after revocation, authoritative role-loss refresh, 204 logout, profile update, one-time token removal, Viewer read-only behavior, scoped live announcements, failure visibility, responsive parity, and SQLite persistence.

Phase B adds a dedicated Resilience route with Stress, Recovery and Capability frontier tasks. It always submits canonical S0 plus the authoritative verified catalyst path, blocks while a transition awaits verification, keeps independent abort/generation lanes, and never writes counterfactual scenarios into planning or Project state. Independent replay covered Basic S0 stress at 0/4 resilient, trained Clinic stress at 0/6 resilient, trained Basic recovery with one changed assignment and burden 24, and the S0/trained frontier boundaries. Reasoning, Project and M7 endpoints remain outside community-role permissions. Projects and Project proof remain in memory.

The accepted presentation layer uses a deep civic-workbench shell, five original compressed WebP scenes, and isolated CSS perspective/parallax to clarify Overview, initiatives, Community, identity and Resilience. It has no WebGL or 3D framework. Mobile and reduced-motion modes remain static. Guest Collaboration and empty Project Proof use truthful next-action compositions without invented data, while normal views retain progressive disclosure of technical evidence.

## Intentionally absent

The current product does not include:

- role-gating for solver, reasoning, Project or M7 endpoints, despite persisted roles and declared future planning permissions;
- generic Project CRUD, tasks, manual assignment, project membership, or persistence;
- cloud services, OAuth, LLM dependence, or external data ingestion;
- deployment, publication, public repository visibility, or submission.

Do not recreate or claim these capabilities without a separately authorised contract, implementation mission, tests, documentation update, and acceptance gate.
