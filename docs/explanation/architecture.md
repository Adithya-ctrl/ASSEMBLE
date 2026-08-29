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
- `main.py`: HTTP routes, localhost CORS, validation translation, and stable errors.

## Frontend

- `lib/types.ts`: HTTP contract mirror.
- `lib/api.ts`: same-origin typed client.
- `app/page.tsx`: the evidence-first six-action workspace and post-proof Project flow.
- `app/globals.css`: civic visual system, responsive layout, high-contrast tokens, focus, reduced motion, and overflow protection.

The interface does not calculate feasibility or readiness. It presents backend results and gates Project creation on a provenance-bound proof context. The backend independently replays and solves again when creating the Project.

## State ownership

S0 is the authoritative demo state. A catalyst creates a copied successor with a canonical content-derived ID and `parent_state_id`. Switching initiatives or starting a fresh compile returns the interface to the authoritative base and clears successor proof. The predecessor remains unchanged.

## Next-milestone design input — not implemented

The next separately authorised product milestone should keep backend capabilities in modular domains and present them through progressive disclosure: one clear job per screen or component, no feature dumping into the main dashboard, and the same capabilities on mobile and desktop. Interaction-level references include the calm app shells, predictable detail views, restrained density, and strong onboarding/empty states found in Immich and Outline. ASSEMBLE must not copy their branding or compositions, and this guidance does not imply that a new navigation model, authentication, collaboration, or redesign already exists.
