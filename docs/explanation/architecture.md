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

## State ownership

S0 is the authoritative demo state. A catalyst creates a copied successor with a canonical content-derived ID and `parent_state_id`. Switching initiatives or starting a fresh compile returns the interface to the authoritative base and clears successor proof. The predecessor remains unchanged.

## Modular presentation boundary

Each current route has one primary job and no more than three simultaneous primary tasks. The single root provider carries the authoritative in-browser proof context across ordinary Link, back, and forward navigation, including Projects to Project Proof and back; a hard refresh reloads authoritative S0. Human summaries lead, one selected detail surface reveals task-relevant facts, and technical identifiers move to explicit disclosure, Judge Proof Mode, or the Inspector. Mobile and desktop expose the same destinations and capabilities.

This structure does not implement accounts, identity, Community roles, collaboration, or persistence. The account control is deliberately disabled and labelled unavailable until a separately accepted identity integration exists.
