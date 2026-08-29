# Verify a change

Run the earliest affected focused tests first, then the cumulative gates.

## Backend

From the repository root:

```bash
auth_test_dir="$(mktemp -d)"
chmod 700 "$auth_test_dir"
ASSEMBLE_AUTH_DB_PATH="$auth_test_dir/auth.sqlite3" backend/.venv/bin/pytest -q backend/tests/auth
ASSEMBLE_AUTH_DB_PATH="$auth_test_dir/auth.sqlite3" backend/.venv/bin/pytest -q backend/tests/test_resilience.py backend/tests/test_recompiler.py backend/tests/test_frontier.py backend/tests/test_technical_api.py backend/tests/test_api.py
ASSEMBLE_AUTH_DB_PATH="$auth_test_dir/auth.sqlite3" backend/.venv/bin/pytest -q backend/tests/test_documentation.py
ASSEMBLE_AUTH_DB_PATH="$auth_test_dir/auth.sqlite3" backend/.venv/bin/pytest -q backend/tests
```

The temporary directory is private and keeps verification out of the default persistent store. The commands cover auth, M7/API, documentation, and cumulative backend gates; the last must remain green for any backend change. Remove the temporary directory after the run if it is no longer needed.

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

1. Open Overview, demo Community, Initiatives, Projects, Collaboration, and Settings through shell/account navigation and direct URLs. Confirm `/preferences` redirects to Settings. Use back, forward, and hard refresh; ordinary planning navigation must preserve proof context while refresh restores authoritative S0.
2. On Community, visit Overview, People, Places, and Resources, reach all eight entities, compare Graph/List facts, and inspect one focused detail plus its Technical details disclosure. Confirm human availability is chronological while exact technical/source values remain intact.
3. Open Basic Workshop's Initiative Proof route and compile the community.
4. Confirm a real feasible S0 proof exposes the Project form with explicit path `[]`.
5. Create the Basic Project and confirm HTTP 201, `READY`, verified baseline, assignments, venue, schedule, resources, readiness, dedicated Project Proof, and Inspector focus.
6. Reset and open Multilingual Clinic's Initiative Proof route.
7. Analyse, explain the shortfall, find the minimum unlock, apply the catalyst, and confirm no Project form appears before verification.
8. Verify the successor and create the Clinic Project from `TRAIN_DIGITAL_HELPERS`.
9. From Projects, follow **View Project proof**, then use browser Back and Forward. Confirm the same Project and exact proof survive all three client transitions without a fixture-reset announcement. Use the Inspector control and confirm it receives focus.
10. Hard-refresh Project Proof and confirm the in-memory Project truthfully resets to its empty state rather than being restored from browser storage.
11. Reset and confirm all downstream evidence, Project state, hashes, and relationship emphasis clear across Projects and Project Proof.

The planning journey verifies the proof workflow only. Separately replay the current identity UI: guest account menu and Appearance; signup/login; session refresh and scheduled expiry; revoked-session invalidation without stale signed-in controls; profile and password forms; 204 logout; Collaboration list/create/accept; Administrator members/invitations/audit; one-time token removal; `403` role-loss refresh to a non-Administrator view; stable 401/403/404/409/429/503 presentation; and restart persistence. Confirm account-menu actions use the product shell's single application announcement and persisted roles do not gate the planning demo.

For the visual current-state check, confirm guest Collaboration and empty Project Proof use purposeful next-action compositions without invented records. Verify Overview, Community, Projects, login, and signup assign or crop the original scene assets deliberately rather than repeating one identical hero treatment. Confirm scene motion remains static on mobile and under reduced motion.

Then replay `/resilience` against the real backend: Basic S0 Stress, S0 Capability frontier, trained Clinic Stress, and trained Basic Stress followed by Recovery. Confirm every request uses canonical `demo.community` plus the authoritative verified catalyst path, a pending transition blocks actions, a new Stress run invalidates Recovery, late responses do not bind after a source change, Judge mode alone reveals raw receipts, and no result mutates planning, transition or Project state.

## Integrated backend API journeys

- Restart two FastAPI applications against the same dedicated private SQLite file and replay signup → session → community creation → recipient-bound invitation → acceptance → membership/role check. Confirm revocation and role changes persist, secrets remain redacted, and the directory/file modes are `0700`/`0600` on POSIX.
- Confirm auth/community routes reject missing sessions, wrong roles, non-JSON unsafe bodies, rejected browser origins, oversized actual request bytes and exceeded persisted rate limits with stable envelopes.
- Confirm solver, reasoning, Project, stress-test, recompile and frontier routes remain callable without an auth session. This is the deliberate current boundary, not an authorisation guarantee.
- Replay structural stress against a feasible authoritative path, recompile from one returned canonical perturbation ID, and run the one-action frontier. Confirm counterfactual IDs never appear as operational Project lineage, forged bases fail closed, and `UNKNOWN` is never counted as decisive evidence.

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
- At 320 and 390, confirm all six product destinations remain visibly discoverable, the account menu remains operable, and Settings, Collaboration and Resilience retain the same tasks without horizontal navigation scrolling.
- Confirm unknown and malformed Initiative Proof paths show a not-found state with a route back and do not request a fallback initiative.
- Check browser console warnings/errors and the app icon.

## Adversarial Project requests

Verify stable rejection for forged base capabilities, quantities, availability, lineage, unknown references, duplicate or overlong paths, omitted `catalyst_path`, extra client proof fields, whitespace-only metadata, infeasible paths, and UNKNOWN results. Error responses must not contain a Project object.

Record current results in [`../../BUILD_STATUS.md`](../../BUILD_STATUS.md). Builder evidence is not independent acceptance.

## Documentation drift gate

Complete both layers in [`audit-documentation.md`](audit-documentation.md): the deterministic automated audit and a human semantic replay of the running UI and API against current documentation. Code, tests, current docs, traceability, and current status must change together. Do not accept a milestone, commit, or push while documentation is stale.
