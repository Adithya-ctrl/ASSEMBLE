# ASSEMBLE documentation

These pages describe the software as it behaves now. Historical decisions and superseded approaches belong only in [`adr/`](adr/README.md).

## Documentation roles

| Governance role | Canonical source | Purpose |
| --- | --- | --- |
| Constitution | [`how-to/contributing.md`](how-to/contributing.md) | Change, verification, documentation, and commit rules |
| Map | This page | Where current product and engineering information lives |
| Status | [`../BUILD_STATUS.md`](../BUILD_STATUS.md) | Current gates, blockers, and unauthorised or intentionally absent capabilities |
| History | [`adr/`](adr/README.md) | Accepted architectural decisions and their consequences |

## Learn by completing a journey

- [`tutorials/project-journeys.md`](tutorials/project-journeys.md): create a Project from Basic Workshop or the unlocked Clinic.

## Present the current software

- [`presentation/project-overview.md`](presentation/project-overview.md): one-page problem, audience, workflow, value, and scope summary.
- [`presentation/three-minute-video.md`](presentation/three-minute-video.md): exact 3:00 narrated recording plan.
- [`presentation/four-minute-live-demo.md`](presentation/four-minute-live-demo.md): exact 4:00 operator runbook, recovery path, and shortened fallback.
- [`presentation/judge-questions.md`](presentation/judge-questions.md): friendly and adversarial judge questions with truthful evidence and boundaries.

## Complete a task

- [`how-to/run-locally.md`](how-to/run-locally.md): run the API and interface locally.
- [`how-to/integrate-auth-backend.md`](how-to/integrate-auth-backend.md): inspect the completed auth registration and configure its local SQLite boundary.
- [`how-to/verify-changes.md`](how-to/verify-changes.md): run cumulative backend, frontend, browser, accessibility, and security gates.
- [`how-to/audit-documentation.md`](how-to/audit-documentation.md): apply the automated and human documentation-drift gate.
- [`how-to/contributing.md`](how-to/contributing.md): change the system without breaking its evidence chain.

## Look up exact behavior

- [`reference/api.md`](reference/api.md): HTTP routes, statuses, and stable errors.
- [`reference/requirements.md`](reference/requirements.md): numbered functional, non-functional, and user-story acceptance requirements.
- [`reference/project-contract.md`](reference/project-contract.md): Project creation trust boundary and returned fields.
- [`reference/identity-community-invitations.md`](reference/identity-community-invitations.md): installed local account, session, role, invitation, persistence, and security contract.
- [`reference/technical-differentiation.md`](reference/technical-differentiation.md): stress-test, recovery, capability-frontier, and Resilience Lab trust boundaries.
- [`reference/accessibility.md`](reference/accessibility.md): semantic, keyboard, contrast, motion, zoom, and parity requirements.
- [`reference/security-validation.md`](reference/security-validation.md): current validation and fail-closed behavior.
- [`UI_DIRECTION.md`](UI_DIRECTION.md): current civic interface and browser-acceptance direction.
- [`TRACEABILITY.md`](TRACEABILITY.md): requirement-to-code-to-evidence mapping.

## Understand why the system works this way

- [`explanation/architecture.md`](explanation/architecture.md): current component and data flow.
- [`explanation/problem-and-purpose.md`](explanation/problem-and-purpose.md): current problem, purpose, audiences, and jobs to be done.
- [`explanation/proof-chain.md`](explanation/proof-chain.md): how solver evidence becomes an executable Project.

## Current surface boundary

The frontend exposes the local auth/community/invitation boundary through dedicated identity, Settings, Collaboration, and Administrator surfaces. Guest access to the fictional planning demo remains available, and persisted collaboration spaces are explicitly separate from that fixture; their roles do not gate solver, reasoning, Project, or M7 routes. The dedicated Resilience Lab presents all three M7 counterfactual analyses without turning their receipts into operational state. Projects and browser proof context remain in memory. See [`../BUILD_STATUS.md`](../BUILD_STATUS.md) for the current acceptance boundary.

## Documentation update rule

A behavior change is incomplete until the canonical page for that behavior, its traceability row, and its verification evidence are updated in the same change. Current-state pages must not preserve old behavior “for context”; record the reason for a durable change in an ADR and update current pages to describe only the replacement.
