# Current requirement traceability

This table maps current behavior to its implementation and verification owner. Update it in the same change as any listed behavior.

| Current requirement | Implementation | Verification |
| --- | --- | --- |
| Strict domain and HTTP contracts | `backend/app/models.py`, `backend/app/api_models.py` | `backend/tests/test_models.py`, `backend/tests/test_api.py` |
| Canonically replayed feasible witness; empty non-feasible witness | `backend/app/api_models.py`, `backend/app/solver.py`, `backend/app/errors.py` | adversarial assignment/trace/objective cases in `backend/tests/test_solver.py`, `backend/tests/test_projects.py`, `backend/tests/test_api.py` |
| Non-relaxable missing-reference integrity | `backend/app/compiler.py` | `backend/tests/test_solver.py`, `backend/tests/test_explain.py` |
| Bounded explanation with factual role/resource/venue evidence | `backend/app/explain.py` | `backend/tests/test_explain.py`, `backend/tests/test_api.py` |
| Minimum disclosed ordered depth-two unlock and matching plan | `backend/app/interventions.py`, `backend/app/planner.py` | 16-path and dependent `Z_TRAIN` → `A_RESOURCE` cases in `backend/tests/test_unlock.py`, `backend/tests/test_planner.py` |
| Immutable, idempotency-safe transition | `backend/app/interventions.py` | `backend/tests/test_unlock.py`, `backend/tests/test_api.py` |
| Stable validation/domain/framework error envelope | `backend/app/main.py` | `backend/tests/test_api.py` |
| Project creation from explicit 0–2 path | `backend/app/project_models.py`, `backend/app/projects.py`, `backend/app/main.py` | `backend/tests/test_projects.py`, `backend/tests/test_api.py` |
| Authoritative base-state provenance | `backend/app/projects.py` | forged capability/quantity/availability/lineage cases in `backend/tests/test_api.py` |
| Normalized Project metadata and content-bound identity | `backend/app/project_models.py`, `backend/app/projects.py` | identity and whitespace cases in `backend/tests/test_projects.py` and `backend/tests/test_api.py` |
| Server-derived assignments, readiness, venue, time and resources | `backend/app/projects.py` | `backend/tests/test_projects.py` and both real Project journeys |
| Route-backed single-purpose product areas and shared proof context | `frontend/app/layout.tsx`, `frontend/app/(product)/`, `frontend/components/shell/AppShell.tsx`, `frontend/lib/workflow-context.tsx` | provider-boundary unit check; direct URL, Link, Projects → Project Proof → back/forward, hard-refresh, valid/unknown/malformed-route browser replay |
| Six-action truth-preserving interface | `frontend/app/(product)/initiatives/[initiativeId]/proof/page.tsx`, `frontend/components/AssemblyProduct.tsx`, `frontend/lib/api.ts` | production browser Clinic journey |
| Basic empty-path and Clinic successor-path Project forms | `frontend/app/(product)/initiatives/[initiativeId]/proof/page.tsx`, `frontend/components/AssemblyProduct.tsx` | production browser Basic and Clinic journeys |
| Proof provenance and stale-response protection | `frontend/lib/workflow-context.tsx`, `frontend/lib/api.ts` | browser pre-verification absence, late-response Reset/switch replay, duplicate-submit replay, source inspection; frontend typecheck/lint/build |
| Category-scoped equivalent graph/list facts | `frontend/app/(product)/community/page.tsx`, `frontend/components/community/CommunityInventory.tsx` | browser eight-entity category reachability, normalized graph/list parity, selected-detail and raw-ID-containment replay |
| Complete Project detail and dedicated Project proof | `frontend/app/(product)/projects/page.tsx`, `frontend/app/(product)/projects/proof/page.tsx`, `frontend/components/project/` | Basic/Clinic detail, Project-specific verification/path/lineage, and Inspector-focus replay |
| Semantic status, trace table, live journey updates and fresh Project-proof focus | `frontend/components/AssemblyProduct.tsx`, `frontend/components/shell/AppShell.tsx`, `frontend/components/project/ProjectProofView.tsx` | browser announcement, semantic-table and Project proof/Inspector replay |
| Strict local-only UI preferences and session-only Judge Proof Mode | `frontend/lib/preferences.ts`, `frontend/lib/preferences.test.ts`, `frontend/lib/workflow-context.tsx`, `frontend/app/(product)/preferences/page.tsx` | valid/invalid/oversized/stale-version cookie and refresh replay; preference unit tests |
| High contrast, opaque focus, reduced motion, zoom and overflow | `frontend/app/globals.css` | production browser token/media/five-width/200%-reflow checks |
| Living current documentation and historical ADR separation | `docs/README.md`, `docs/how-to/contributing.md`, `docs/adr/` | documentation link and contract tests |
| Documentation drift hard gate | `docs/how-to/audit-documentation.md`, `docs/how-to/verify-changes.md` | `backend/tests/test_documentation.py` plus human semantic replay |
| Factual presentation package | `docs/presentation/` | timing, link, ID, claim-boundary tests plus rehearsal against the running product |

## Numbered requirement coverage

The normative wording and acceptance criteria live in [`reference/requirements.md`](reference/requirements.md). These rows identify the implementation and primary evidence without duplicating that prose.

| IDs | Implementation or governing source | Primary evidence |
| --- | --- | --- |
| FR-001 | `backend/app/fixture.py`, `frontend/lib/workflow-context.tsx` | demo/API tests and browser S0 inventory replay |
| FR-002 | `frontend/components/community/CommunityInventory.tsx`, `frontend/app/(product)/community/page.tsx` | category keyboard replay, all-eight-entity reachability, detail disclosure, and graph/list parity |
| FR-003 | `frontend/app/(product)/initiatives/page.tsx`, `frontend/app/(product)/initiatives/[initiativeId]/proof/page.tsx`, `frontend/proxy.ts`, `backend/app/models.py` | browser selection plus valid/unknown/malformed dynamic-route replay and model tests |
| FR-004 | `backend/app/compiler.py`, `backend/app/solver.py`, `backend/app/main.py` | compile-once spy plus solver and API suites |
| FR-005 | `backend/app/api_models.py`, `backend/app/solver.py` | feasible/non-feasible witness invariant tests |
| FR-006 | `backend/app/explain.py` | explanation and Clinic factual-evidence tests |
| FR-007 | `backend/app/interventions.py` | 16 ordered candidates, rank, cost, and already-feasible tests |
| FR-008 | `backend/app/interventions.py`, `backend/app/planner.py` | matching dependent-order, depth/state-bound, and trace tests |
| FR-009 | `backend/app/interventions.py` | immutable transition and no-op tests |
| FR-010 | `frontend/components/AssemblyProduct.tsx`, `frontend/lib/workflow-context.tsx` | production browser transition-before-verify and UNKNOWN-retry replay |
| FR-011 | `frontend/components/AssemblyProduct.tsx`, `frontend/lib/workflow-context.tsx` | Basic base-proof and Clinic successor-proof form gates |
| FR-012 | `backend/app/projects.py`, `backend/app/main.py` | Project direct and API adversarial tests |
| FR-013 | `backend/app/project_models.py`, `backend/app/projects.py` | Basic/Clinic derived-detail tests and live journeys |
| FR-014 | `frontend/components/project/ProjectProofView.tsx`, `frontend/app/(product)/projects/proof/page.tsx` | Project identity/status, fresh verification, source-plan/path/lineage/catalyst-output and Inspector-focus replay |
| FR-015 | `frontend/lib/workflow-context.tsx`, `frontend/components/shell/AppShell.tsx` | browser Reset replay after completed Clinic Project and stale-response delay |
| FR-016 | `frontend/lib/preferences.ts`, `frontend/lib/preferences.test.ts`, `frontend/app/(product)/preferences/page.tsx`, `frontend/app/globals.css` | cookie fallback/persistence, keyboard, contrast/theme/motion, status, and target checks |
| FR-017 | `frontend/lib/workflow-context.tsx`, `frontend/components/shell/AppShell.tsx` | single live-region journey announcement replay |
| NFR-001 | solver, reasoning, transition, Project, and inspector evidence chain | cumulative backend tests and real-browser proof replay |
| NFR-002 | `backend/app/solver.py`, `backend/app/explain.py`, `backend/app/planner.py` | deterministic fixture matrix and bounded-search tests |
| NFR-003 | strict bounded backend models and `backend/app/projects.py` | invalid type/ID/extra-field/collection-overflow/forged-state/path/status tests |
| NFR-004 | `frontend/app/(product)/`, `frontend/components/`, `frontend/app/globals.css` | keyboard, focus, status, live, target, contrast, motion and desktop/mobile Lighthouse checks |
| NFR-005 | `frontend/components/shell/AppShell.tsx`, `frontend/app/globals.css` | all-route 1440/768/390/320, 200% reflow, visible mobile navigation and overflow checks |
| NFR-006 | loading state and bounded solver configuration | interactive journey and solver statistics |
| NFR-007 | `backend/app/main.py`, `frontend/app/layout.tsx`, frontend workflow-generation/abort protections | stable-envelope API tests, provider-boundary unit check, Project route preservation, and all-route stale/duplicate-response replay |
| NFR-008 | `docs/README.md`, `docs/how-to/audit-documentation.md` | deterministic docs gate and human semantic replay |
| NFR-009 | local fixture/runtime boundaries | dependency/configuration inspection and absent-capability audit |
| NFR-010 | local backend/frontend commands | full pytest, typecheck, lint, build, and browser journeys |
| NFR-011 | `frontend/app/(product)/`, `frontend/components/`, `frontend/app/globals.css` | 320/1440 all-route parity: five destinations, four Community categories, all eight entities, six proof actions, 3 Project fields, complete Project/proof/Preferences capability, no overflow or sub-44px target |

## User-story demonstration coverage

| IDs | Primary acceptance evidence | Presentation step |
| --- | --- | --- |
| US-001, US-011, US-013 | graph/list, keyboard, responsive, zoom, contrast, live-status, full-parity replay | 3-minute S0/access segment; 4-minute orientation and closing parity cue |
| US-002, US-007 | Basic S0 OPTIMAL witness and explicit empty-path HTTP 201 Project | 3-minute Basic segment; 4-minute Basic proof |
| US-003, US-004 | Clinic blocker facts and catalogue/minimum comparison | both Clinic explain/unlock segments |
| US-005, US-006 | immutable diff, blocked pending state, one verification request | both apply/verify segments |
| US-008, US-009 | Clinic one-action HTTP 201 Project and focused source inspector | both Project/source-proof segments |
| US-010 | adversarial Project API suite and stable error envelopes | trust-boundary close and judge Q&A |
| US-012 | completed-journey Reset replay | 4-minute Reset recovery and close |
