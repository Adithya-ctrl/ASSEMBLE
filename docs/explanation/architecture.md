# Current architecture

ASSEMBLE is a local two-process application:

```text
Browser
  -> Next.js interface and same-origin /api proxy
  -> FastAPI strict request models
  -> deterministic fixture and authoritative action catalogue
     -> compiler / CP-SAT solver
     -> explanation, unlock, transition, and planner services
     -> Project replay and derivation
     -> counterfactual stress, recompilation, and capability frontier
  -> installed local auth and community router
     -> private file-backed SQLite identity, membership, invitation, rate and audit state
  -> strict JSON result
```

## Backend

- `models.py`: community, initiative, action, and stable-ID contracts.
- `api_models.py`: core request, response, solver witness, trace, and error contracts.
- `fixture.py` and `data/demo_fixture.json`: authoritative fictional event fixture.
- `compiler.py`: converts declared blocks and requirements into CP-SAT variables and constraints.
- `solver.py`: solves, canonically validates, and decodes complete replayable witnesses; analyse responses reuse the exact compiled models used for their counts.
- `explain.py`: bounded relax-and-resolve explanation.
- `interventions.py`: immutable action application, canonical state identity, and minimum ordered depth-two unlock search.
- `planner.py`: bounded catalyst planning over the same executable ordered paths.
- `project_models.py`: strict executable Project contracts.
- `projects.py`: authoritative base check, action replay, fresh solve, identity, operational assignment, and readiness derivation.
- `analysis_state.py`: reconstructs authoritative bounded source states for additive analyses.
- `resilience.py`: server-generated one-fact structural perturbations and decisive-outcome resilience.
- `recompiler.py`: two-stage minimum-assignment-change recovery with the normal burden objective retained.
- `frontier.py`: independent one-action capability comparisons across initiatives.
- `auth/`: strict local account/session models, SQLite migrations and storage, permission checks, recipient-bound invitations, audit events, boundary middleware, and installable router.
- `main.py`: integrated HTTP routes, localhost CORS, validation translation, stable errors, and auth-router registration.

## Frontend

- `lib/types.ts`: HTTP contract mirror.
- `lib/api.ts`: same-origin typed client.
- `app/layout.tsx` and `lib/workflow-context.tsx`: one root-mounted provider owns shared proof state, provenance binding, workflow generations, abort controllers, Project nonce gating, announcements, preferences, and reset behavior across all client-side product navigation.
- `lib/preferences.ts`: strict versioned cookie encoding for theme, contrast, motion, and preferred inventory view only.
- `app/(product)/layout.tsx` and `components/shell/AppShell.tsx`: the provider-free product shell owns persistent navigation, account boundary, Judge Proof Mode, Inspector, and live status. Keeping the sole provider above this route-group boundary prevents Project evidence from remounting between `/projects` and `/projects/proof`.
- `app/(product)/**/page.tsx`: substantive Overview, Community, Initiatives, Initiative Proof, Projects, Project Proof, and Preferences routes.
- `components/community/CommunityInventory.tsx`: category-scoped graph/list inventory and focused detail surface.
- `components/AssemblyProduct.tsx`: initiative proof actions, progressive evidence panels, Project form, and Technical Inspector.
- `components/project/`: server-returned Project detail and dedicated source-proof presentation.
- `proxy.ts`: fail-visible normalization for malformed dynamic Initiative Proof paths before route handling.
- `app/globals.css`: shared civic visual grammar, responsive layout, contrast/theme tokens, focus, reduced motion, and overflow protection.

The interface does not calculate feasibility or readiness. It presents backend results and gates Project creation on a provenance-bound proof context. The backend independently replays and solves again when creating the Project.

The interface also does not expose the installed identity/community/invitation routes or the three counterfactual M7 analyses. The account control remains disabled and no role-specific browser behavior is claimed. Auth protection applies to auth and community-administration routes; solver, reasoning, Project, stress-test, recompile and frontier endpoints remain deliberately outside role-gating.

## State ownership

S0 is the authoritative demo state. A catalyst creates a copied successor with a canonical content-derived ID and `parent_state_id`. Switching initiatives or starting a fresh compile returns the interface to the authoritative base and clears successor proof. The predecessor remains unchanged. Projects and proof context are held in memory and are not restored after refresh or process restart.

Identity is a separate state domain. Users, sessions, communities, memberships, invitations, rate counters and audit events persist in SQLite at `ASSEMBLE_AUTH_DB_PATH`, defaulting to `backend/.data/auth.sqlite3`. These SQLite communities are not linked to the solver's authoritative fictional fixture. On POSIX, the directory is mode `0700` and the database/WAL/SHM files are mode `0600`; unsafe existing modes fail closed. This persistence does not make Projects or solver evidence persistent.

Stress and frontier scenarios use domain-separated counterfactual receipt IDs and no operational parent lineage. Recompilation consumes only a server-issued canonical perturbation ID. None of these analytical states can be supplied to Project creation as an operational successor.

## Modular presentation boundary

Each current route has one primary job and no more than three simultaneous primary tasks. The single root provider carries the authoritative in-browser proof context across ordinary Link, back, and forward navigation, including Projects to Project Proof and back; a hard refresh reloads authoritative S0. Human summaries lead, one selected detail surface reveals task-relevant facts, and technical identifiers move to explicit disclosure, Judge Proof Mode, or the Inspector. Mobile and desktop expose the same destinations and capabilities.

This frontend structure does not implement identity, Community administration, invitations, collaboration, M7 analysis views, or persisted Projects. The account control is deliberately disabled even though the FastAPI auth routes are installed; a separately implemented and accepted frontend workflow is still required.
