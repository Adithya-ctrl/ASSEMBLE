# B2-G6 — GAUNTLET-ABSOLUTE-01 A–Z checklist and crosswalk

Status: **HOLD — declared incomplete browser rows**

This is the bounded source-of-truth, coverage, and release-gate crosswalk for
the independent audit lane. It does not accept a practice set from a passing unit
test, a builder report, or a prepared browser artifact. The current acceptance
ledger is [`docs/ADVERSARIAL_ACCEPTANCE_REPORT.md`](../../../docs/ADVERSARIAL_ACCEPTANCE_REPORT.md);
its `WITHHELD` final statement and known defects remain authoritative for this
audit snapshot.

## Authority and source order

| Order | Source | Use in this crosswalk |
| --- | --- | --- |
| 1 | Gauntlet specification SHA-256 `97ab573c7e3b99dcee2f9a0bb9d7e00cb338b0a8714fc81a7604f5ff49b8f1f4` (3,580 lines / 66,719 bytes as recorded in the acceptance ledger) | Normative GAUNTLET-ABSOLUTE-01 set definitions and release gate |
| 2 | `docs/reference/requirements.md` | Current FR-001–FR-023, NFR-001–NFR-013 and US-001–US-017 wording and acceptance criteria |
| 3 | `contracts/*.md`, `backend/app/**`, `frontend/app/**`, `frontend/components/**`, `frontend/lib/**` | Executable contract and current implementation surfaces |
| 4 | `docs/TRACEABILITY.md` | Requirement → implementation → evidence ownership |
| 5 | `backend/tests/**`, `frontend/lib/*.test.ts`, `tests/adversarial/**` | Test coverage and prepared nonvisual/browser evidence |
| 6 | `BUILD_STATUS.md` and `docs/ADVERSARIAL_ACCEPTANCE_REPORT.md` | Current product status versus this gauntlet's independent acceptance status |
| 7 | `docs/adr/**` | Historical decisions only; ADR wording is not treated as current-state truth |

The QA source overlay is
`a8b9797017668fcc4ae6e9634e2e67d7975ba23d`; definitive browser evidence is
bound to authoritative product source
`453c84fc9c05495b1d21b91f505d8179019f296c`. The read-only machine audit in
[`run_readonly_audit.py`](run_readonly_audit.py) verifies the route, requirement,
traceability, link, surface, and stale-current-claim portions of this table.

## Authorised source evolution

The checkout began at `fc9925c5bfd175df5e83768954540b7110873c69`.
The control centre later authorised two bounded auth repair cherry-picks:
`2c0bd2e71bfc4de11a306a5d5b3b4bc93c03de9d` and
`5c6b411ea4849a8c46a32ee02c5b654c2116f6c0`, then the strict-model repair as
`04878c1a16577e70cfd072df01fb62c8bb05a33b`, the analyser repair as
`eb88841e835354943ba414fe01e8ba924437647f`, and source-bound status receipt as
`a8b9797017668fcc4ae6e9634e2e67d7975ba23d`. Earlier pin failures were expected
authorised drift and harness updates, not product failures. The audit now
records source identities separately from the future artifact commit to avoid
a self-referential hash requirement.

## Exact A–Z checklist

The result column is the acceptance-ledger result at this snapshot. `PARTIAL
PASS` means only the listed bounded lane is green; it is not a release pass.

| Set | Contract focus | Current implementation and evidence crosswalk | Result | Remaining gate / exact gap |
| --- | --- | --- | --- | --- |
| A | Single-value and boundary matrix: strict IDs, types, collection ceilings, numeric booleans, request limits; FR-001/004/012, NFR-003/007/012 | Strict model/auth/HTTP matrices plus cumulative backend replay | **PASS** | Frozen 552/552 and adjacent 117/117 boundaries green. |
| B | Solver oracle: eligibility, availability, venue, resources, sharing, objective and deterministic status; FR-004/005, NFR-001/002 | Genuine independent small-domain enumerator plus production regression/metamorphic packet | **PASS** | Independent 298/298, 100 repeats and explicit MODEL_INVALID/UNKNOWN green. |
| C | Canonical witness validator and single-fact tamper rejection; FR-005, NFR-001/003 | Independent 23-mutation catalogue plus replay/API/Project tests | **PASS** | Complete catalogue green. |
| D | Bounded explanation and factual blocker evidence; FR-006/017, NFR-001 | Independent 19-case group/pair/time/resource/malicious analyser matrix | **PASS** | Seven repaired trust defects and status-only compatibility green. |
| E | Minimum sufficient ordered unlock, planner path and immutable transition; FR-007–FR-009, NFR-001/002/007 | Independent no-path/no-op/tie/purity/ceiling oracle plus production replay | **PASS** | Complete bounded set green. |
| F | Project trust boundary, proof gate, empty path, successor, derived fields, reset; FR-010–FR-015, NFR-001/003/007 | Backend/pure gates plus mounted Basic/Clinic Project, Back/Forward, refresh and Reset | **PARTIAL PASS** | Forced mounted UNKNOWN successor retry not verified. |
| G | Structural stress catalogue/counts/criticality/receipts/source purity; FR-021, NFR-001/013 | Independent oracle plus mounted Basic 4/4 and trained Clinic 6/6 | **PASS** | Published fixture truth and no-Project mutation green. |
| H | Two-stage minimum-disruption recompiler and burden tie-break; FR-022, NFR-001/013 | Genuine independent oracle plus mounted exact Recovery | **PASS** | Priya→Leo, one change, Sam preserved, burden 24. |
| I | One-action frontier, coverage, UNKNOWN, ranking and Pareto; FR-023, NFR-002/013 | Independent Pareto/loss oracle plus mounted S0/trained views | **PASS** | TRAIN/BORROW/current-winner truth green. |
| J | Password hashing, sessions, cookies, rate/origin bounds; FR-018, NFR-012 | Repaired auth backend plus mounted signup/password/logout/login/restart | **PARTIAL PASS** | Wrong-password rate UX and forced browser expiry not verified. |
| K | Roles, membership authorization, invitations and audit; FR-019/020, NFR-012 | Backend lifecycle/races plus mounted Admin/Coordinator→Member/invite/audit | **PARTIAL PASS** | Viewer and revoke/expiry/two-context race remain backend-only. |
| L | SQLite migrations, private modes, restart, lock and concurrency; FR-018–FR-020, NFR-012 | Exact 0600/0700, BUSY, restart, 800 in-process and 160 process constructors | **PASS** | Repaired cold-start and fail-closed storage boundaries green. |
| M | Ambitious browser workflows and failure paths; FR-001–FR-020, NFR-004/005/007/010/011 | Definitive 37-step marathon, route/history/offline/tab/image/25-loop gates | **PARTIAL PASS** | Full reset/switch torture and every slow/backend-loss permutation incomplete. |
| N | Mounted Stress, Recovery and Capability frontier; FR-021–FR-023, NFR-013 | S0/trained modes, pending gate, Judge isolation and Project purity | **PARTIAL PASS** | Each Resilience lane's mounted stale/concurrency race incomplete. |
| O | Identity, Settings, Collaboration, role and invitation workflows; FR-018–FR-020, NFR-012 | Two-account lifecycle, live role, audit and restart mounted | **PARTIAL PASS** | Full four-role, expiry, revoke and simultaneous-accept browser flows incomplete. |
| P | Route/HTTP abuse: methods, paths, media, JSON, fields and errors; FR-003/004/007/012, NFR-003/007 | Complete non-auth and auth/community/invitation matrices | **PASS** | 317/317 green. |
| Q | Client response-parser attacks; NFR-001/003/007, FR-018/021–FR-023 | 80 deterministic rejects plus mounted malformed Analyse | **PARTIAL PASS** | Every auth/M7 parser and HTTP status is not individually mounted. |
| R | Stale-response, abort, generation and source binding; FR-015/023, NFR-007/013 | Pure all-lane model plus delayed mounted Analyse source switch | **PARTIAL PASS** | Every async lane was not separately delayed in Chrome. |
| S | Visual/layout, responsive parity and appearance; FR-002/014/016/017, NFR-004/005/011 | 80 route rows, 2560 audit and reviewed screenshots | **PARTIAL PASS** | Full state×viewport×theme screenshot Cartesian product incomplete. |
| T | Image/3D and heavy-dependency hardening; NFR-004/006/009/010 | Successful WebP visuals and three forced image failures at 320@2x | **PARTIAL PASS** | Slow/cache-disabled matrix incomplete; no WebGL/3D dependency exists. |
| U | Performance/resource bounds; NFR-002/006/010/013 | 100 solves, bounded resilience calls and 25 mounted workflow loops | **PASS** | Exact timings recorded; bounded local prototype claim only. |
| V | Security input safety and fail-closed trust boundaries; NFR-003/009/012/013 | Repaired auth/model/analyser suites plus mounted hostile-text rendering | **PASS** | No execution/injection/route escape observed in tested fields. |
| W | Accessibility: keyboard, semantics, focus, targets, appearance and zoom; NFR-004/005/011 | 80-row semantics/target audit, AX tree, keyboard, dark/high/reduced, 200%/300% | **PARTIAL PASS** | Screen-reader journey and 400% not verified. |
| X | Model-based workflow state and counterfactual no-mutation; FR-009–FR-017/023, NFR-007/013 | Seeded pure model plus mounted route/history/tab/stale/persistence flows | **PARTIAL PASS** | Hundreds of generated sequences were not compared to mounted controls. |
| Y | Auth/session/RBAC/invitation state machine; FR-018–FR-020, NFR-012 | Pure/backend model plus mounted two-account lifecycle/restart | **PARTIAL PASS** | Expiry/Admin-loss/in-flight combinations not mounted. |
| Z | Cross-subsystem boss fights; all FR/NFR | 37-step marathon, restart, counterfactual purity, 320/200% combined flows | **PARTIAL PASS** | Not all 12 named boss fights executed verbatim. |

## Structural audit results at this snapshot

The read-only audit command (`python3 tests/adversarial/audit/run_readonly_audit.py`)
returned `status: HOLD` with these exact counts:

| Check | Result |
| --- | ---: |
| Python API route decorators | 26 |
| Documented API route rows | 26 |
| Route mismatches | 0 documented-only; 0 implementation-only |
| Functional requirements | 23/23 consecutive; traceable |
| Non-functional requirements | 13/13 consecutive; traceable |
| User stories | 17/17 consecutive; traceable |
| Broken local Markdown links (including ADRs) | 0 |
| Missing traceability source paths | 0 |
| Required frontend route page files | 13/13 |
| Numbered traceability rows with implementation and evidence | 36/36 |
| Required adversarial test/evidence category artifacts | 22/22 |
| Current contract-pointer drift findings | 0 PASS after reconciled documentation ancestor |
| Tested identities | QA overlay `a8b9797`; browser product `453c84f`; no self-referential artifact-HEAD check |

The original audit findings were:

1. `contracts/api.md:22` says “none of the auth or M7 APIs has a current frontend workflow.” The installed account routes and `/resilience` route contradict this claim. Current corroboration is `contracts/auth-api.md:15`, `docs/reference/technical-differentiation.md:3-13`, and `docs/TRACEABILITY.md:25`.
2. `contracts/technical-differentiation-api.md:5-7` says “the current frontend has no surface for these analyses.” `frontend/app/(product)/resilience/page.tsx:1-4` and `frontend/components/resilience/ResilienceIntegration.tsx:193-222` provide that surface.

`docs/adr/0006` and `docs/adr/0007` contain superseded “no frontend workflow/surface” wording, but they are intentionally historical and are excluded from current-state drift adjudication under `docs/README.md` and `docs/how-to/audit-documentation.md`.

The control centre repaired DOC-001/002 and four adjacent documentation drifts
in six root-owned files with documentation tests 11/11 and a clean diff check.
The authorised root commit was then cherry-picked as the separate ancestor
`ed1892fa978552a90689e9fea0f878a0f269fd67`. Replay on that source returned
machine-audit PASS with zero findings.

## Coverage and release accounting

The acceptance ledger records the following independent/baseline evidence; the
numbers are not additive acceptance claims:

- Complete frozen backend: 1,975/1,975, independently matched by the control centre; non-adversarial current backend 395/395. These collections overlap.
- Genuine independent solver package: 298/298. The older 310-case production-helper packet remains regression/metamorphic evidence only.
- The pure frontend packet records 17/17 tests and exactly 80 malformed parser cases; pure reducers and request models do not prove mounted React/Next or browser behavior.
- Independent witness/explain/unlock 31/31; resilience oracles 15/15; route abuse 317/317. Counts overlap and are not summed.
- All seven auth/storage, five model, seven explanation and two mounted pattern defects are repaired and replayed. DOC-001/002 are repaired only in the root-owned source described above.

## Known environment and browser gaps

These are explicit unavailable conditions, not silently accepted results:

| Gap | Exact evidence / consequence |
| --- | --- |
| Browser engines | Chrome 151 is verified; Firefox and WebKit/Safari are NOT VERIFIED. |
| Zoom | Formal 200% and available 300% pass; requested 400% is NOT VERIFIED because Chrome clamped 4× to 3×. |
| Visual breadth | 80 responsive rows, 2560 audit and selected screenshots are green; the full state×viewport×theme Cartesian capture is incomplete. |
| Accessibility | Keyboard, semantics, names, targets, contrast/motion and AX tree are green; a full screen-reader journey is not verified. |
| Mounted races | Representative stale Analyse and two-account lifecycle are green; every parser/status/async/RBAC/invitation race was not mounted. |
| Robustness | Mutation testing and randomized browser monkey testing were not completed. |

## Release gate

This lane cannot mark release acceptance. The exact current condition is:

```text
HOLD = any declared PARTIAL/NOT VERIFIED A–Z row.
```

The documentation findings are closed. The report's final release statement is
**WITHHELD** until every required gate is
green and no known reproducible defect remains. This packet changes only
gauntlet-owned tests, browser harnesses, evidence and audit/report artifacts; it
does not modify product or shared documentation.
