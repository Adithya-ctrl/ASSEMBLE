# Verify a change

Run the earliest affected focused tests first, then the cumulative gates.

## Backend

From the repository root:

```bash
backend/.venv/bin/pytest -q backend/tests/test_projects.py backend/tests/test_api.py
backend/.venv/bin/pytest -q backend/tests
```

The first command is the current Project/API gate. The second is cumulative and must remain green for any backend change.

## Frontend

From `frontend/`:

```bash
npm run typecheck
npm run lint
npm run build
```

Lint must finish with zero errors and zero warnings.

## Real-browser journey

Run the real FastAPI backend and the production Next.js build. Use a clean page state.

1. Open Overview, Community, Initiatives, Projects, and Preferences through shell navigation and direct URLs. Use back, forward, and hard refresh; ordinary navigation must preserve proof context while refresh restores authoritative S0.
2. On Community, visit Overview, People, Places, and Resources, reach all eight entities, compare Graph/List facts, and inspect one focused detail plus its Technical details disclosure.
3. Open Basic Workshop's Initiative Proof route and compile the community.
4. Confirm a real feasible S0 proof exposes the Project form with explicit path `[]`.
5. Create the Basic Project and confirm HTTP 201, `READY`, verified baseline, assignments, venue, schedule, resources, readiness, dedicated Project Proof, and Inspector focus.
6. Reset and open Multilingual Clinic's Initiative Proof route.
7. Analyse, explain the shortfall, find the minimum unlock, apply the catalyst, and confirm no Project form appears before verification.
8. Verify the successor and create the Clinic Project from `TRAIN_DIGITAL_HELPERS`.
9. From Projects, follow **View Project proof**, then use browser Back and Forward. Confirm the same Project and exact proof survive all three client transitions without a fixture-reset announcement. Use the Inspector control and confirm it receives focus.
10. Hard-refresh Project Proof and confirm the in-memory Project truthfully resets to its empty state rather than being restored from browser storage.
11. Reset and confirm all downstream evidence, Project state, hashes, and relationship emphasis clear across Projects and Project Proof.

## Accessibility and resilience

- Navigate every control with a keyboard and inspect the visible focus indicator.
- Confirm the single journey announcement reports compile/analyse, blocker and shortfall, unlock and cost, pending successor, verification, and Project creation.
- Compare graph and list views for the same organisation, person, space, resource, identity, capability, language, availability, capacity, quantity, and feature facts.
- Check 1440x900, 1280x720, 768x1024, 390x844, and 320px-wide layouts.
- At 200% zoom, confirm content reflows without horizontal document or Project proof-footer overflow.
- Confirm every visible interactive target is at least 44 by 44 CSS pixels.
- Confirm reduced motion removes non-essential animation without hiding information.
- Confirm high-contrast mode and normal mode retain an opaque focus outline and readable icon-plus-text statuses.
- Confirm system/light/dark, standard/high contrast, reduced-motion override, and preferred inventory view use only the versioned `assemble_ui_preferences` cookie; invalid, oversized, and stale-version values fail closed. Judge Proof Mode must reset on refresh.
- At 320 and 390, confirm all five navigation destinations remain visibly discoverable without horizontal navigation scrolling and the disabled account status remains present.
- Confirm unknown and malformed Initiative Proof paths show a not-found state with a route back and do not request a fallback initiative.
- Check browser console warnings/errors and the app icon.

## Adversarial Project requests

Verify stable rejection for forged base capabilities, quantities, availability, lineage, unknown references, duplicate or overlong paths, omitted `catalyst_path`, extra client proof fields, whitespace-only metadata, infeasible paths, and UNKNOWN results. Error responses must not contain a Project object.

Record current results in [`../../BUILD_STATUS.md`](../../BUILD_STATUS.md). Builder evidence is not independent acceptance.

## Documentation drift gate

Complete both layers in [`audit-documentation.md`](audit-documentation.md): the deterministic automated audit and a human semantic replay of the running UI and API against current documentation. Code, tests, current docs, traceability, and current status must change together. Do not accept a milestone, commit, or push while documentation is stale.
