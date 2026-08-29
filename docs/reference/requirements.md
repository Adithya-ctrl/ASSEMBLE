# Current software requirements

## Scope

ASSEMBLE is a localhost civic capacity-and-intervention planner for a deterministic fictional fixture. It inventories declared capacity, solves initiative feasibility, explains blockers, compares disclosed catalyst actions, verifies immutable successors, creates an executable Project from a fresh proof, and exposes backend-only structural resilience analyses. Its FastAPI boundary also provides local identity, persisted community membership and recipient-bound invitations.

## Assumptions and constraints

- Fixture facts are fictional, complete only within the declared model, and small enough for bounded CP-SAT analysis.
- Initiative and catalyst identifiers reference the authoritative fixture.
- Catalyst planning is limited to depth two and at most 20 expanded states.
- Project creation starts only from exact authoritative S0 and accepts an explicit path of 0–2 actions.
- The interface and API run locally; the browser uses a same-origin Next.js proxy.
- Local auth/community/invitation state uses file-backed SQLite. Those communities are not linked to the solver's fictional fixture and are separate from in-memory Project and proof state.
- Community roles protect only auth and community-administration routes; solver, reasoning, Project and M7 routes are not role-gated.
- Feasibility is a model result, not a guarantee of social success or real-world delivery.

## Non-goals and absent capabilities

- Real community discovery, prediction, recommendation outside the catalogue, or impact measurement.
- Frontend M7 workflows; email verification, MFA, OAuth, account recovery, or cloud identity.
- Role-gating of solver, reasoning, Project or M7 routes; project membership or task authorisation.
- Project/proof persistence, generic Project CRUD, tasks, reassignment, collaboration, or notifications.
- Cloud services, OAuth, external LLMs, external data export, deployment, publication, or submission.

## Current interaction boundary

The interface is organised as route-backed, single-purpose areas for planning, Projects, identity, Settings, and persisted Collaboration spaces. A shared planning shell and workflow provider preserve proof context during product navigation; a separate identity provider owns session bootstrap and auth request cancellation without gating guest demo access. Progressive disclosure keeps raw identifiers, exact slots, hashes, solver statistics, and full trace facts out of normal task views; they remain available in selected detail, Judge Proof Mode, or the Technical Inspector.

The account and Collaboration surfaces expose FastAPI's local accounts plus Administrator, Coordinator, Member and Viewer memberships. Administrator-only controls are withheld from other roles, and every protected request is still authorised by the backend. These persisted roles govern only collaboration-space administration; they do not govern solver, reasoning, Project, or M7 routes. Structural stress, recompilation and capability frontier are current API capabilities with no current frontend surface.

## Functional requirements

- **FR-001 — Load inventory.** The system shall load the authoritative organisations, people, spaces, resources, initiatives, actions, and state identity from the deterministic fixture.
- **FR-002 — Present equivalent inventory views.** The Community route shall present Overview, People, Places, and Resources one category at a time, with labelled Graph View and List View controls backed by the same state. Human summaries appear first; selection reveals one focused detail surface, while raw IDs and exact slots remain in technical disclosure. Both representations retain equivalent organisations, capabilities, languages, availability, capacity, quantity, and features.
- **FR-003 — Select an initiative.** The Initiatives route shall let the user select one declared initiative, review its human-readable brief and current proof status, and open the dedicated Initiative Proof route without substituting a fallback initiative for an unknown route ID.
- **FR-004 — Compile and analyse.** The API shall strictly validate the submitted bounded community and initiative IDs, compile each requested initiative exactly once, and derive the returned counts and genuine solver result from those same compiled models.
- **FR-005 — Expose feasible evidence.** A FEASIBLE or OPTIMAL result shall include objective, complete role assignments, assembly trace, and solver statistics; other statuses shall not include a witness.
- **FR-006 — Explain a blocker.** For an infeasible initiative, the system shall return bounded relax-and-resolve requirement sets and factual required, available, shortfall, entity, capability, language, venue, resource, or time evidence when applicable.
- **FR-007 — Find the minimum modelled unlock.** The system shall compare all unique executable ordered action paths of length one or two, return the sufficient path ranked by total cost, path length, then action IDs, report `candidate_paths_evaluated`, and reject an already-feasible target. Four disclosed actions produce 16 ordered candidates.
- **FR-008 — Trace a bounded plan.** The planner shall use the same executable ordered-path semantics as unlock and return the selected maximum depth-two path, state sequence, costs, node trace, pruning information, and before/after target statuses within 20 expanded states.
- **FR-009 — Apply an immutable transition.** Every action in `plan.path` shall be applied in the returned order, each producing a copied successor with parent identity and machine-readable capability, person, or resource diff while leaving every predecessor unchanged; a no-op reapplication shall be rejected.
- **FR-010 — Verify the successor.** The interface shall keep the target blocked until the full path is applied and expose exactly one verification action that analyses the final returned successor before showing it as buildable. UNKNOWN shall withhold Project creation while leaving explicit verification retry available.
- **FR-011 — Gate Project creation by proof.** The interface shall expose the separately labelled Project form after a real feasible base proof or matching verified successor proof, never from inferred or stale state.
- **FR-012 — Create a Project from a replayed plan.** The Project API shall require authoritative base state, known initiative, explicit unique catalyst path of 0–2 actions, and normalized title, description, and objective; it shall replay and solve again before returning HTTP 201.
- **FR-013 — Derive execution details.** The returned Project shall derive status, assignments, complete selected-person and matched requirement facts, venue, venue-derived host organisation, schedule, resources, capability modules, accessibility, operational languages, capacity, readiness, source identities, catalyst outputs, and creation/update timestamps from authoritative state and solver evidence.
- **FR-014 — Inspect source proof.** The Project shall expose its Project identity and status, source initiative, fresh verification, `source_plan_id`, exact catalyst path, base and verified state IDs, and catalyst outputs on a dedicated Project Proof route, with a focusable control to the complete Technical Inspector.
- **FR-015 — Reset cleanly.** Reset shall restore authoritative S0 and clear analyses, explanation, unlock, plan, transition, verified result, Project form response, request errors, downstream hashes, inspector state, and relationship emphasis.
- **FR-016 — Control appearance and access representation.** Settings shall provide allow-listed theme, contrast, motion, and preferred inventory-view choices through native labelled controls, including for guests; `/preferences` shall redirect to Settings. Those four values alone may persist in a versioned first-party cookie; invalid, oversized, or stale-version values fail to defaults. Judge Proof Mode is session-only. Icon-plus-text status shall remain authoritative.
- **FR-017 — Announce the journey.** One scoped application live region per active shell shall concisely announce successful compile/analyse, blocker and shortfall, unlock and cost, successor pending proof, verification, view/contrast changes, reset, Project creation, and identity/session actions. Product account-menu actions shall share the existing planning region rather than mount a competing application region.
- **FR-018 — Manage a local account and session.** Dedicated frontend entry and Settings surfaces shall create strictly validated local accounts, authenticate, bootstrap the current session, show/update bounded profile metadata, change passwords after current-password verification, and log out through the same-origin API. The HttpOnly session cookie shall never be read or stored by JavaScript. The client shall schedule expiry from the validated public session timestamp and immediately clear cached signed-in state on `AUTHENTICATION_REQUIRED` without confusing it with invalid-credential `AUTHENTICATION_FAILED`. The API shall preserve non-enumerating failures, session rotation, earlier-session revocation after password change, and idempotent logout.
- **FR-019 — Persist communities and current roles.** An authenticated user shall list and create SQLite-backed Collaboration spaces through a dedicated surface. The creator becomes `ADMINISTRATOR`; every protected community request shall load current membership from storage. The Administrator detail shall expose member/role, invitation, and audit tasks; Coordinator, Member, and Viewer views shall state their persisted role without invoking protected Administrator operations. A `403` from an Administrator operation shall immediately withhold cached administration controls and refresh authoritative membership. The last Administrator cannot be demoted.
- **FR-020 — Complete a recipient-bound invitation lifecycle.** The Collaboration surface shall accept a recipient-bound token; an Administrator shall create, list, and revoke bounded invitations. A raw local-delivery token shall be returned and displayed only once, remain only in component memory, and be removed on copy, dismiss, unmount, or request invalidation. Only its digest persists; acceptance shall atomically verify pending state, expiry, recipient, community role and non-membership. Audit responses remain bounded and secret-free.
- **FR-021 — Stress a proved plan structurally.** The stress API shall reconstruct an authoritative source from exact S0 plus a unique 0–2 action path, require a feasible baseline, generate the complete canonical witness-derived one-fact perturbation catalogue, enforce its 20-entry ceiling before scenario solving, and report `RESILIENT`, `DEGRADED`, `CRITICAL` or `UNKNOWN` outcomes with resilience computed only over decisive results.
- **FR-022 — Recompile with minimum disruption.** Given one canonical stress perturbation ID, the recompiler shall prove the minimum changed role assignments only from an `OPTIMAL` Stage 1, then fix that scalar and minimise the unchanged normal burden objective in a fresh Stage 2. An unresolved Stage 1 shall expose no minimum or replacement witness, and every exposed feasible Stage 2 witness shall pass the normal canonical validator.
- **FR-023 — Compare the one-action capability frontier.** The frontier API shall apply each applicable authoritative action independently from the same reconstructed source, solve every initiative before and after it, track gains, losses and unknowns, and rank or Pareto-compare only candidates with complete decisive coverage. It shall never present a one-action result as a sequenced operational successor.

## Non-functional requirements

- **NFR-001 — Proof integrity and explainability.** Every feasible witness shall pass canonical replay of exact assignments, trace structure and domain facts, candidate start, sharing, objective, and all non-relaxed predicates before it is returned. Every blocker, unlock, transition, verification, readiness, and Project claim shall remain adjacent to machine-readable evidence or a direct source-proof path. UNKNOWN shall remain UNKNOWN; malformed feasible analyser output shall fail as `ANALYSER_CONTRACT_ERROR`.
- **NFR-002 — Deterministic bounded behavior.** The core shall use the disclosed fixture, deterministic CP-SAT configuration, finite action catalogue, bounded relaxation search, depth-two planner, and explicit solver time limit; it shall not rely on an LLM.
- **NFR-003 — Validation and security.** Backend models shall reject unknown fields, invalid types/IDs, and collections above the exact ceilings documented in the security reference. Project creation shall fail closed on forged base content or lineage, unsafe client proof fields, invalid paths, blank normalized metadata, INFEASIBLE, UNKNOWN, or a malformed feasible witness and shall never emit a Project on failure.
- **NFR-004 — Accessibility.** The current interface shall use semantic landmarks, heading order, labels, native keyboard controls, visible opaque focus, icon-plus-text status, one scoped live announcement, at least 44-by-44 CSS-pixel targets, reduced-motion handling, and WCAG AA-oriented contrast practices across normal, dark, and high-contrast presentations.
- **NFR-005 — Responsive reflow.** Desktop, tablet, mobile, and 200% zoom layouts shall avoid horizontal document or navigation overflow. Every destination shall remain visibly discoverable without an undisclosed horizontal gesture, and graph/list content shall remain equivalent when connector graphics are unavailable.
- **NFR-006 — Performance budget.** Controls shall visibly react within 100 ms, use honest labelled loading for backend work, avoid fake progress, and use the existing DOM/CSS/SVG stack without heavy graph, 3D, video, or animation dependencies. Solver execution remains bounded by its configured limit.
- **NFR-007 — Reliability and errors.** Domain, validation, framework, UNKNOWN, and network failures shall remain explicit and stable. API errors shall use the frozen envelope and stable code. Workflow generations and abort signals shall prevent late demo, analyse, explain, unlock, plan, transition, verify, or Project responses from repopulating reset or changed state; aborted work shall not become an error and duplicate Project submits shall be suppressed.
- **NFR-008 — Maintainability and living documentation.** Code, tests, current documentation, traceability, and current status shall change together. Diátaxis pages describe current behavior; ADRs alone preserve architectural history. Documentation drift blocks milestone acceptance and repository mutation.
- **NFR-009 — Privacy and data boundary.** The current system shall use only the fictional fixture and user-submitted bounded JSON, shall not send it to an external LLM or analytics service, and shall not export or persist Project data.
- **NFR-010 — Local reproducibility.** The backend tests, frontend typecheck/lint/build, and browser journeys shall run locally without a cloud subscription or OpenAI API key.
- **NFR-011 — Full platform feature parity.** At 320 and 1440 CSS pixels, the interface shall expose the same controls, flows, editable fields, evidence, inventory facts, and Project capabilities. Only layout and label presentation may change.
- **NFR-012 — Local identity security and durable lifecycle.** Passwords shall use bounded `scrypt-v1`; session and invitation bearer secrets shall use 256-bit random values with digest-only storage; auth bodies, fields and persisted rate buckets shall be bounded; unsafe requests shall enforce JSON and an exact bounded canonical browser-origin allow-list that cannot be widened by Host or forwarded headers; auth namespace matching shall be segment-aware; and restart shall preserve valid lifecycle, role, revocation, expiry, rate and audit state. On POSIX, the auth directory and database runtime files shall be `0700` and `0600`; unsafe existing modes fail closed.
- **NFR-013 — Counterfactual integrity and boundedness.** Stress, recompilation and frontier shall accept no client-selected witness, objective, patch, perturbation body or action catalogue; reconstruct all analysis state from authoritative S0; use explicit solver-call and collection ceilings; preserve `UNKNOWN`; and issue domain-separated counterfactual receipts that cannot be consumed as operational state or Project lineage.

## User stories and acceptance criteria

### US-001 — Understand community capacity

As a community coordinator, I want equivalent visual and textual inventory views so I can understand declared capacity in the representation that works for me. Maps to FR-001, FR-002, FR-016, NFR-004, NFR-005, NFR-011.

- **Given** the S0 fixture is loaded, **when** I choose a Community category, select an entity, and switch between Graph View and List View, **then** both representations keep all eight blocks and equivalent core facts reachable without showing every category or technical fact at once.

### US-002 — Prove a feasible initiative

As a coordinator, I want a complete assignment for Basic Workshop so I can see who, where, when, and which resources make it feasible. Maps to FR-003, FR-004, FR-005, NFR-001, NFR-002.

- **Given** authoritative S0, **when** Basic Workshop is analysed, **then** the API returns OPTIMAL with an objective, complete assignment, trace, and solver statistics.

### US-003 — Understand the Clinic blocker

As a coordinator, I want factual shortfall evidence so I do not mistake equipment for a capability problem. Maps to FR-006, FR-017, NFR-001.

- **Given** Clinic is INFEASIBLE in S0, **when** I request an explanation, **then** I see three digital helpers required, one available, shortfall two, source person LEO, and the returned bounded solver-run count.

### US-004 — Choose a sufficient minimum intervention

As a coalition planner, I want the cheapest sufficient action rather than the cheapest action so resources address the actual blocker. Maps to FR-007, FR-008, NFR-002.

- **Given** the four-action disclosed catalogue, **when** I find the minimum unlock, **then** all 16 unique ordered paths of length one or two are considered and training two helpers at cost 2 is distinguished from invalid laptop borrowing, insufficient single recruits, and valid but costlier dual recruitment.

### US-005 — Preserve state provenance

As a reviewer, I want an immutable successor and explicit diff so the original facts remain auditable. Maps to FR-009, NFR-001, NFR-007.

- **Given** the training action is applicable, **when** it is applied, **then** a successor with parent S0 adds digital support to Priya and Sam while S0 remains unchanged.

### US-006 — Require independent verification

As an initiative participant, I want the Clinic to remain blocked until the successor is solved so readiness is not optimistic. Maps to FR-010, FR-011, NFR-001.

- **Given** the catalyst has produced a successor, **when** verification has not completed, **then** there is one verification control, the Clinic remains blocked, and no Project form is available.

### US-007 — Create Basic from an empty plan

As a coordinator, I want to create a Project from an already-feasible initiative without inventing a catalyst. Maps to FR-011, FR-012, FR-013, NFR-003.

- **Given** Basic has a real feasible S0 proof, **when** I submit explicit `catalyst_path: []` and valid metadata, **then** the API returns HTTP 201 with a READY Project whose base and verified state are S0.

### US-008 — Create Clinic from the proved catalyst

As a coordinator, I want a Project only after the Clinic’s successor is verified. Maps to FR-010, FR-011, FR-012, FR-013, NFR-001.

- **Given** `TRAIN_DIGITAL_HELPERS` produces a verified OPTIMAL successor, **when** I create the Project, **then** the server replays that authoritative path, solves again, and returns READY execution details including English and Arabic operational facts.

### US-009 — Inspect the Project source

As a technical reviewer, I want a direct source-proof control so I can audit the Project without developer tools. Maps to FR-014, NFR-001, NFR-004.

- **Given** a Project exists, **when** I activate View Project proof, **then** the dedicated proof route presents the Project identity/status, source initiative, fresh verification, source-plan ID, exact path, state lineage, and catalyst outputs; its inspector control opens and focuses the complete Technical Inspector.

### US-010 — Reject forged or incomplete Project input

As a stakeholder, I want server-side validation so the interface cannot manufacture readiness. Maps to FR-012, NFR-003, NFR-007.

- **Given** a forged S0 payload, invalid path, unsafe extra proof field, blank normalized metadata, INFEASIBLE, or UNKNOWN proof, **when** Project creation is attempted, **then** a stable 4xx error is returned and no Project object is emitted.

### US-011 — Use the complete journey accessibly

As a keyboard, zoom, mobile, high-contrast, or reduced-motion user, I want the same capabilities and facts without hidden meaning. Maps to FR-002, FR-016, FR-017, NFR-004, NFR-005, NFR-006, NFR-011.

- **Given** any supported presentation mode, **when** I navigate the route-backed journey and change appearance preferences, **then** every destination, control, and status remains labelled, focus-visible, operable, announced, and free of horizontal document or navigation overflow.

### US-012 — Reset without stale proof

As a judge, I want one reset to clear all downstream evidence so I can replay from a trustworthy baseline. Maps to FR-015, NFR-007.

- **Given** a successor and Project exist, **when** I reset, **then** S0 returns and downstream panels, request errors, Project response, hashes, inspector state, and active seams clear.

### US-013 — Retain full mobile and desktop capability

As a mobile or desktop user, I want the complete workflow and evidence on either platform so device width does not decide what I can do or verify. Maps to FR-001–FR-017, NFR-004, NFR-005, NFR-011.

- **Given** the same journey state at 320 and 1440 CSS pixels, **when** I inspect and operate every product route, **then** both widths expose the same destinations, category/detail controls, flows, three editable Project fields, inventory facts, proof evidence, preferences, and Project capabilities; only layout and label presentation may differ.

### US-014 — Keep a local account across restart

As a local user, I want a bounded account and revocable session so community administration does not depend on a cloud identity provider. Maps to FR-018, NFR-012.

- **Given** I submit valid signup or login details through the dedicated entry, **when** I refresh the browser or restart the API against the same private SQLite file, **then** the account menu and Settings restore my public user/memberships through the HttpOnly session without exposing raw session or password material; logout, scheduled expiry, or an authoritative revoked-session response returns me to guest planning access.

### US-015 — Invite and govern community members

As a Community Administrator, I want recipient-bound invitations and current persisted role checks so membership changes are explicit and auditable. Maps to FR-019, FR-020, NFR-012.

- **Given** I administer a Collaboration space and invite a registered recipient, **when** that recipient accepts the one-time token and I inspect member, invitation, and audit tabs, **then** one membership is created atomically, the raw token disappears after one local delivery, secrets remain redacted, current roles take effect immediately, a `403` clears stale Administrator controls before refresh, and non-Administrators see a truthful read-only access surface.

### US-016 — Test and recover a fragile plan

As a technical reviewer, I want canonical structural stress and minimum-disruption recompilation so resilience and recovery claims remain solver-verifiable. Maps to FR-021, FR-022, NFR-001, NFR-013.

- **Given** an authoritative feasible source path, **when** I run stress and submit one returned canonical perturbation ID to recompile, **then** every one-fact scenario is accounted for, UNKNOWN remains explicit, and any replacement witness reports only a proved minimum assignment-change count plus validated normal-burden evidence.

### US-017 — Compare one catalyst's capacity effect

As a coalition planner, I want a one-action capability frontier so I can compare disclosed catalysts without confusing analytical receipts with operational successors. Maps to FR-023, NFR-002, NFR-013.

- **Given** authoritative S0 and its action catalogue, **when** I request the frontier, **then** each applicable action is evaluated independently across all initiatives, incomplete coverage cannot produce a winner, and the returned counterfactual IDs cannot be used to create a Project.

## Demonstration mapping

The presentation runbooks are evidence-navigation aids, not substitute acceptance tests.

| User stories | Three-minute video step | Four-minute live-demo step |
| --- | --- | --- |
| US-001, US-011, US-013 | S0 inventory and access modes | S0 orientation and parity cue |
| US-002, US-007 | Basic Workshop proof | Compile and Basic proof |
| US-003, US-004 | Clinic blocker and minimum unlock | Explain and compare catalyst actions |
| US-005, US-006 | Immutable successor and verification | Apply, inspect diff, then verify |
| US-008, US-009 | READY Project and source proof | Create Clinic Project and open inspector |
| US-010 | Trust-boundary close | Security/provenance close |
| US-012 | Recording reset | Reset recovery path |
| US-014, US-015 | Local account, session refresh, Collaboration, role and invitation evidence | Open Account/Settings and Collaboration; retain the explicit demo-fixture separation |
| US-016, US-017 | API evidence only; no current M7 frontend surface | API evidence only; do not imply these analyses are on screen |
