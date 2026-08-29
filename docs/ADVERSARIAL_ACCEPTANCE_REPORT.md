# ASSEMBLE Adversarial Acceptance Report

Status: **HOLD — NOT RELEASE-ACCEPTED**

This report is the live evidence ledger for `GAUNTLET-ABSOLUTE-01`. A passing
baseline is not full adversarial acceptance. Pending or unavailable work is not
counted as passed, and any reproducible product defect places the release gate
on HOLD until the defect is reported, repaired under separate authority, and
replayed through focused and cumulative gates.

## Tested identity and environment

- QA source-overlay HEAD: `a8b9797017668fcc4ae6e9634e2e67d7975ba23d`
- Baseline parent: `fc9925c5bfd175df5e83768954540b7110873c69`
- Integrated repair: source commit
  `4dc565dbf1db06c53436a0579c5976a11ad4eebd`, cherry-picked as
  `2c0bd2e71bfc4de11a306a5d5b3b4bc93c03de9d`; residual AUTH-007 source
  `b8b8a3b6cfa8aff29ad9a86f2da3a550e62f5863`, cherry-picked as
  `5c6b411ea4849a8c46a32ee02c5b654c2116f6c0`; strict-model repair source
  `43a917ecb92eb00e366e6347eb06a91c0f77fd79`, cherry-picked as
  `04878c1a16577e70cfd072df01fb62c8bb05a33b`; analyser-boundary source
  `055ee9dd98653ff629fff3031e8f3ea503c2ffcc`, cherry-picked as
  `eb88841e835354943ba414fe01e8ba924437647f`; source-bound status-receipt
  source `6281fb3fa57c00343f7b8ad7534858ae41259c9b`, cherry-picked as
  `a8b9797017668fcc4ae6e9634e2e67d7975ba23d`
- Branch: `qa/absolute-adversarial-gauntlet`
- Worktree: `/private/tmp/assemble-adversarial-gauntlet`
- Reconciled documentation ancestor: root source `5cf13ae` cherry-picked as
  `ed1892fa978552a90689e9fea0f878a0f269fd67`; the read-only audit was replayed
  on this source and returned PASS with zero findings.
- Definitive browser source: authoritative clean `main` at
  `453c84fc9c05495b1d21b91f505d8179019f296c`; production frontend
  `http://127.0.0.1:3134` backed by `http://127.0.0.1:8018` and fresh private
  SQLite database `/private/tmp/assemble-gauntlet-final-qGlAm1/auth.sqlite3`.
  This superseded both the exploratory 3132/8016 boundary and the pre-pattern-
  repair 3133/8017 boundary.
- Test start: 2026-08-29/30, Australia/Sydney
- OS: macOS 15.7.9 (24G830), Darwin 24.6.0, arm64
- Browser: isolated Google Chrome 151.0.7922.175 headless/CDP. Firefox and
  WebKit/Safari were not verified.
- Backend Python: 3.13.13
- Node: 22.23.1
- npm: 10.9.8
- Next.js: 16.3.3
- Fresh DB path policy: a new private temporary directory and SQLite database
  path per backend gate; no development database is reused as acceptance proof.
- Gauntlet specification: SHA-256
  `97ab573c7e3b99dcee2f9a0bb9d7e00cb338b0a8714fc81a7604f5ff49b8f1f4`,
  3,580 lines, 66,719 bytes.

## Baseline gates

| Gate | Result | Evidence |
|---|---:|---|
| Current non-adversarial backend | PASS | 395 passed, one known Starlette/httpx deprecation warning |
| Original plus adversarial auth | PASS | 192 passed, same known warning |
| Independent solver package | PASS | 298 passed |
| Independent witness/explain/unlock package | PASS | 31 passed |
| Independent resilience oracle package | PASS | 15 passed |
| Documentation tests | PASS | 11 passed, 0.49 s |
| Frontend focused tests | PASS | 40 passed on definitive product source |
| Frontend typecheck | PASS | `tsc --noEmit --incremental false` |
| Frontend lint | PASS | `eslint .` |
| Frontend production build | PASS | Next.js 16.3.3; 14 routes generated |
| Frozen complete backend collection | PASS | 1,975 passed, one known Starlette/httpx warning, 8.92 s; independent root replay 1,975 passed in 8.68 s |

The clean worktree had no local `node_modules`. Two preliminary invocations
failed before exercising product behavior: package resolution could not find
`tsx`, then Turbopack rejected an external dependency symlink. The final tests
used the lockfile-identical installed runtime, and the production build used an
APFS copy in a temporary harness. The build required network access for the two
Google fonts configured by the product. These are harness observations, not
product defect closures.

## Practice-set status

| Set | Status | Notes |
|---|---|---|
| A — single-value/boundary | PASS | Frozen strict-model matrix 552/552, adjacent 117/117 and complete backend replay green |
| B — solver oracle | PASS | Independent 1–5 enumeration 298/298, 100 repeats, tie/objective and MODEL_INVALID/UNKNOWN propagation green |
| C — witness validator | PASS | Complete 23 single-fact mutation catalogue and independent replay green |
| D — explanation engine | PASS | Complete blocker/malicious-analyser matrix 19/19 after seven bounded product repairs; status-only compatibility preserved |
| E — unlock/planner | PASS | Independent no-path/no-op/tie/purity/32-action and 1,024-path ceiling cases green |
| F — Project trust boundary | PARTIAL PASS | Basic/Clinic Project, refresh, Back/Forward and Reset mounted; forced mounted UNKNOWN retry not verified |
| G — structural stress | PASS | Independent oracle plus Basic S0 4/4 and trained Clinic 6/6 mounted truth green |
| H — recompiler | PASS | Independent minimum/burden oracle and mounted Priya→Leo recovery green |
| I — capability frontier | PASS | Independent Pareto/loss oracle plus mounted S0/trained frontier green |
| J — auth crypto/session | PARTIAL PASS | Seven defects repaired; lifecycle, cookie, password rotation and restart mounted; wrong-password rate and forced expiry browser UX not verified |
| K — roles/invitations/audit | PARTIAL PASS | Admin/two-account invitation, live role and audit mounted; Viewer/revoke/expiry/two-browser race remain backend-only |
| L — SQLite/restart/concurrency | PASS | Exact-mode, restart, 800 in-process and 160 clean-process cold-start replay green |
| M — ambitious browser workflows | PARTIAL PASS | Definitive 37-step marathon complete; reset/switch torture, full semantic-reader and all slow/failure permutations remain incomplete |
| N — Resilience Lab browser | PARTIAL PASS | S0/trained Stress, Recovery, Frontier, pending gate and Judge isolation mounted; each lane's stale/concurrency race not mounted |
| O — identity/collaboration browser | PARTIAL PASS | Two-account lifecycle/restart green; full four-role, wrong-password rate, revoke/expiry and simultaneous accept browser flows not run |
| P — route/HTTP abuse | PASS | Complete non-auth plus auth/community/invitation matrix is 317/317 green |
| Q — response-parser attacks | PARTIAL PASS | 80 deterministic malformed cases plus mounted malformed Analyse green; every mounted auth/Resilience parser permutation not run |
| R — stale/abort matrix | PARTIAL PASS | Pure lane/generation matrix plus delayed mounted Analyse discard green; every async lane not delayed in Chrome |
| S — visual regression/layout | PARTIAL PASS | 80 responsive route rows, 2560 audit and reviewed evidence screenshots green; full state×viewport×theme Cartesian matrix not captured |
| T — image/3D hardening | PARTIAL PASS | Real WebP scenes load; three forced image failures at 320@2x retained function/semantics/layout; slow/cache-disabled matrix incomplete; no WebGL/3D dependency exists |
| U — performance/resource bounds | PASS | 100 solves and bounded resilience timings recorded; 25 full browser loops had zero DOM/document/listener growth after collection |
| V — security input safety | PASS | Auth/model/analyser boundaries green; hostile HTML/SQL-like text rendered literally with no execution/injection |
| W — accessibility deep audit | PARTIAL PASS | Landmarks/names/targets/keyboard/dark/high/reduced/200% and AX tree green; screen-reader product journey and 400% not verified |
| X — model-based workflow state | PARTIAL PASS | Seeded pure state models and mounted Back/Forward/tab/stale/persistence flows green; browser comparison for hundreds of generated sequences not run |
| Y — auth state machine | PARTIAL PASS | Pure/backend model plus mounted two-account lifecycle/restart green; expiry/Admin-loss/in-flight combinations not mounted |
| Z — cross-subsystem boss fights | PARTIAL PASS | 37-step, restart, counterfactual purity, 320/200% combined flows cover bounded fights; all 12 named scenarios not executed verbatim |

## A–Z owner and next-gate ledger

Passing counts in one row are evidence for that row only. Tests overlap across
sets and are never added together as if they were independent observations.

| Set | Current owner | Status | Next acceptance gate |
|---|---|---|---|
| A | Root QA | PASS | Strict boundaries plus cumulative replay complete |
| B | Independent oracle lane; root replayed | PASS | 298/298 and source-freeze replay complete |
| C | Independent oracle lane; root replayed | PASS | Complete 23-mutation catalogue green |
| D | Independent oracle lane; root replayed | PASS | Seven repaired defects plus bounded compatibility green |
| E | Independent oracle lane; root replayed | PASS | Full bounded path/purity matrix green |
| F | Root QA | PARTIAL PASS | Mounted UNKNOWN successor retry remains unverified |
| G | Independent oracle + Root browser | PASS | S0/trained mounted truth matches oracle |
| H | Independent oracle + Root browser | PASS | Mounted exact recovery matches oracle |
| I | Independent oracle + Root browser | PASS | Mounted S0/trained frontier matches oracle |
| J | Root QA | PARTIAL PASS | Wrong-password rate and forced expiry browser UX remain |
| K | Root QA | PARTIAL PASS | Viewer/revoke/expiry/two-context accept remain browser gaps |
| L | Root QA | PASS | Restart/private-mode/busy/cold-start matrices green |
| M | Root QA | PARTIAL PASS | Named torture/failure permutations remain incomplete |
| N | Root QA | PARTIAL PASS | Delayed mounted races for all three lanes remain |
| O | Root QA | PARTIAL PASS | Four-role and complete invitation lifecycle browser matrix remains |
| P | Root QA | PASS | 317/317 route abuse and cumulative replay green |
| Q | Root QA | PARTIAL PASS | Mounted parser injection is representative, not exhaustive |
| R | Root QA | PARTIAL PASS | Mounted Analyse race plus pure full matrix; remaining lanes unmounted |
| S | Root QA | PARTIAL PASS | Full visual Cartesian matrix not captured |
| T | Root QA | PARTIAL PASS | Slow/cache-disabled image matrix incomplete |
| U | Performance worker; root browser | PASS | Backend timings and 25-loop mounted evidence complete |
| V | Root QA | PASS | Hostile input and trust-boundary replay complete |
| W | Root QA | PARTIAL PASS | Screen-reader journey and 400% unavailable |
| X | Root QA | PARTIAL PASS | Hundreds of generated sequences remain pure-model evidence |
| Y | Root QA | PARTIAL PASS | Expiry/Admin-loss/in-flight combinations remain unmounted |
| Z | Root QA | PARTIAL PASS | All 12 named boss fights not executed verbatim |

Root QA personally executed the definitive 37-step marathon, responsive,
accessibility, image-failure, stale-response, hostile-input, history, tab-
isolation and browser-loop gates. Worker packets were evidence only and were
adjudicated against the source/runtime identities above.

## Required completion accounting

- Browser workflows completed: definitive steps 1–29 on a zero-state database,
  control-centre restart of the same database, then preserved-context steps
  30–37. Historical interrupted attempts are harness failures, not acceptance.
- Generated/model-based sequences: existing solver order/repeat and planner
  purity regressions are non-independent and non-additive; independent coverage
  is in progress and no final sequence total is claimed yet.
- Solver brute-force cases: independent package passed 298/298, including 256
  seeded exhaustive cases (people 1–5, roles 1–3, spaces 1–2, resources 0–2,
  slots 2–4), initiative batches 1–5, 119 optimum-tie cases with 1,716 tied
  witnesses, 100 deterministic repeats and explicit MODEL_INVALID/UNKNOWN
  propagation. The older helper-importing cases remain regression/metamorphic
  evidence only.
- Recompiler brute-force cases: independent G/H/I package passed 15/15 and the
  combined relevant gate 55/55; the older 12 helper-importing lexicographic
  cases remain regression/metamorphic evidence only.
- Boundary cases: 80 deterministic malformed frontend parser cases plus the
  backend auth and HTTP matrices; counts overlap and are not added into a
  synthetic total.
- Responsive viewports: 80 rows across 320, 375, 390, 768, 1024, 1280, 1440
  and 1920, plus eight 2560 route rows; no material horizontal overflow.
- Accessibility modes: keyboard routes, accessibility tree, landmarks,
  accessible names, 44px targets at 320/390/1440, dark, high contrast, reduced
  motion and formal 200% passed. Maximum available 300% passed. Requested 400%
  is NOT VERIFIED because Chrome clamped 4× to measured 3×.
- Auth concurrency/race cases: focused in-process and clean-process replay is
  green; two-account browser lifecycle/restart is green; selected in-flight
  expiry/role/invitation races remain backend-only.
- Counterfactual cases: independent structural/recovery/frontier oracles and
  mounted S0/trained Stress, Recovery, Frontier, Judge and Project-purity
  evidence are green; delayed mounted races for each lane remain pending.
- Defects found: 23 confirmed product defects so far: 7 auth/storage, 5 strict
  core-model boundaries, 7 analyser trust-boundary defects, 2 invalid mounted
  HTML patterns, and 2 current-state documentation defects. Harness failures
  are recorded separately and are not product results.
- Defects repaired: all 7 auth/storage, all 5 strict-model, and all 7 analyser
  trust-boundary defects pass
  focused and feature replay, including 800 in-process and 160 clean-process
  concurrent cold-start constructors.
  Invitation-ordering and auth-HTTP harness defects were corrected only after
  explicit control-centre adjudication.
- Open product-code defects: none within the tested source and completed rows.
  `GAUNTLET-UI-001/002` are closed by `453c84f` and mounted replay.
  `DOC-001/002` plus four adjacent drifts are closed by the separately
  cherry-picked root documentation commit; documentation tests are 11/11 and
  the machine audit now reports PASS with zero findings.

## Untested or currently unavailable

- Firefox and WebKit/Safari are not verified; all browser evidence is Chrome
  151 headless/CDP.
- 400% zoom is NOT VERIFIED due the measured 300% automation cap.
- The full state × viewport × theme screenshot Cartesian product, full screen-
  reader journey, every slow/offline request permutation, every mounted parser
  status and all named browser race/boss-fight variants are incomplete.
- Mutation testing and randomized browser monkey testing were not completed.
- A passing final statement remains withheld while these declared incomplete
  release-gate rows remain. The documentation defects are repaired in the
  root-owned source but have not been duplicated into this QA overlay.

## Definitive browser and runtime evidence

The 37-step run began from direct SQLite counts of zero users, sessions,
communities and invitations. Steps 1–29 completed Basic and Clinic Project
proofs, Resilience truth, preferences/accessibility modes, signup/profile/
password rotation, community creation, invitation delivery/acceptance/replay,
live role change, audit redaction, logout and new-password login. The control
centre then gracefully restarted backend port 8018 against the same database.
Read-only post-restart counts were users=2, sessions=4, communities=1,
memberships=2 and audit_events=12. Preserved owner/member contexts completed
steps 30–37, proving persisted auth/community/role/audit state and explicitly
non-persisted session-only Project/proof state.

Selected screenshot evidence:

| File | PNG dimensions | Claim |
| --- | ---: | --- |
| `phase1-29-owner.png` | 1440×1000 | Owner flow checkpoint |
| `phase1-29-member-390.png` | 390×844 | Member mobile checkpoint |
| `step37-owner-settings-1440.png` | 1440×1140 | Final owner Settings at 1440×1000 viewport |
| `step37-member-communities-390.png` | 390×981 | Final member Collaboration at 390×844 viewport |
| `supplemental-basic-s0-stress-1440.png` | 1440×2053 | Complete Basic S0 Stress evidence |
| `supplemental-pending-resilience-block-1440.png` | 1440×900 | Pending successor blocks Resilience |
| `supplemental-settings-dark-high-reduced-320.png` | 320×1362 | Mobile dark/high/reduced parity |
| `supplemental-settings-300pct-environment-cap-1440.png` | 1440×1160 | Maximum available 300% reflow |
| `remaining-images-blocked-resilience-320@2x.png` | 640×4164 | 320 CSS px at DPR2 with illustration request blocked |
| `ultrawide-resilience-2560.png` | 2560×1440 | 2560px reading measure/layout |

Terminal adjudication retained all expected errors. Phase 1 had two guest
session 401s and the intentional invitation-replay 404. Its three RSC
`ERR_ABORTED` entries were cancelled speculative Next requests. Logout also
logged an abort during navigation, but the exact 204 response, cookie removal
and later new-password login independently prove the server action completed.
Phase 2 had zero console/page/request/HTTP failures. Supplemental matrices
classified expected guest-session 401s, intentional offline/image failures and
speculative RSC cancellations; no unexpected failure remained.

Performance/resource evidence is bounded, not a production-load claim. Twenty
warm `/api/demo` calls had p50 0.587ms/p95 0.645ms; 100 serial Basic solves all
returned OPTIMAL/objective 24 with semantic hash
`a903181c09b41a605c1b6c53b1af561b5067a83125397b4fb1a7d38661c37118`
and p50 0.633ms/p95 0.957ms. Basic S0 Stress was 40.655ms; trained Clinic
Stress 92.930ms; S0 Frontier 18.498ms; trained Frontier 17.505ms. Twenty-five
mounted Basic compile→analyse→reset loops made exactly 50 Analyse and 26 Demo
requests; p50 431.4ms/p95 445.9ms/worst 450.6ms, with post-collection deltas of
zero DOM nodes, documents and event listeners. Heap use was 973,360 bytes
higher after the bounded loop; that observation neither proves nor suggests a
leak by itself.

## Defect ledger

The cumulative backend replay auto-collected the auth lane and reproduced five
defects twice. The control centre confirmed them against the frozen contract
before any repair or expectation change:

1. `GAUNTLET-AUTH-001`: permissive base64 decoding lets a noncanonical stored
   scrypt salt representation verify.
2. `GAUNTLET-AUTH-002`: the internal password-hash entry point accepts caller
   supplied salts outside the declared 16-byte size.
3. `GAUNTLET-AUTH-003`: an avatar URL with port `99999` passes model validation.
4. `GAUNTLET-AUTH-004`: a configured browser origin with trailing tab is
   silently trimmed and accepted.
5. `GAUNTLET-AUTH-005`: duplicate Origin fields collapse to the final
   allowlisted value and an unsafe auth request returns HTTP 200.

The completed G2 focused replay then exposed two more defects, both confirmed
by the control centre:

6. `GAUNTLET-AUTH-006`: a pre-existing POSIX `0400` database escapes as a raw
   read-only SQLite failure instead of failing the exact `0600` permission
   boundary.
7. `GAUNTLET-AUTH-007`: four concurrent cold-start constructors originally
   raced between path existence and exclusive creation, producing
   `FileExistsError` losers. The first repair removed that failure but repeated
   replay still produced transient `StorageBusyError` losers. A residual repair
   serialized constructor-only initialization and added bounded initialization
   retry without changing request-time busy-to-503 behavior.

Severity interpretation is deliberately bounded: `001`–`004` are local
encoding/invariant/input/configuration failures, not evidence of a remote
password bypass. `005` is the P1 security-sensitive request-header boundary;
`006` is fail-closed storage availability; and `007` is concurrent-start
availability. Repair replay must also prove `_supported_stored_hash` matches the
strict verifier and exercise both duplicate-header orders for Origin,
Sec-Fetch-Site, Content-Type, and Content-Length.

Common environment: tested commit above, Python 3.13.13, FastAPI TestClient,
fresh pytest temporary paths/databases, no browser viewport or domain state.
Each reproduced 2/2 at discovery time, when product code remained unchanged.
Focused regressions live in the isolated auth adversarial namespace.
Root-cause and minimal-repair details are preserved in the control-centre HOLD
packets; authorised repairs were integrated only after adjudication.

After integrating the bounded repair, the frozen seven passed 7/7 once, G2
passed 57/57, expanded strict-hash and duplicate-header parity passed 9/9, and
the full original-plus-adversarial auth layer passed 190/190. A ten-run
cold-start stability gate passed four times, then failed; the next immediate
replay also failed with one `StorageBusyError`. Downstream acceptance gates were
stopped, and `GAUNTLET-AUTH-007` remained open at that intermediate checkpoint.
After the residual repair, the frozen defect nodes passed 21/21, adjacent
strict-hash/header cases passed 8/8, 100 batches of 8 in-process constructors
passed 800/800, and 20 batches of 8 real Python processes passed 160/160 with
every migration ledger exactly `[1]`. Restart/persistence cases passed 16/16,
and combined original-plus-adversarial auth passed 192/192. AUTH-007 is closed
at the auth/restart/concurrency layer; browser evidence remains pending.

`GAUNTLET-TEST-001` was a harness defect, not a product defect. Its fixed clock
gave four invitations the same `created_at`, while the product's stable
secondary ordering is `id DESC`; the test incorrectly assumed the newest
logical invite must be at index zero. Under explicit authority the test now
locates the target by ID, asserts its `PENDING` state, and independently checks
that repeated list calls preserve the same ordered ID sequence. Five
consecutive focused replays passed. No product ordering was changed and no
security regression was weakened.

The inspected solver packet is accepted only as regression/metamorphic
evidence: 310/310 focused checks passed in 0.65 s, and the original 279-test
backend suite plus those checks passed 589/589 in 4.70 s with the known warning.
Its expected-value logic imports production compiler/action/solver helpers, it
covers only 1–4 initiatives and two repeats, and it does not supply the required
MODEL_INVALID/downstream-UNKNOWN cases. It is not counted as an independent
oracle; B2-G7 owns that missing evidence.

The independently inspected pure frontend packet is also accepted only at its
declared nonvisual layer: 17/17 tests passed in 0.27 s with deterministic seed
`20260830`, including exactly 80 malformed parser cases. Full frontend
typecheck, a targeted check for the out-of-tree harness tests, and targeted
lint for the new frontend support files passed. Those pure reducers and request
models remain non-mounted evidence; the later executed browser matrix records
mounted results and gaps separately rather than laundering the pure results.

Practice Set P's non-auth HTTP packet is accepted: 215/215 cases passed in
0.95 s on the repaired QA HEAD. It inventories every declared non-auth route,
checks inverse and unsupported methods, media/JSON/unknown-field failures,
required fields and collection ceilings, stable error envelopes, lookalike and
duplicate-slash routes, and representative domain error statuses. The worker
independently verified the gauntlet document identity and read all 3,580 lines
before finalizing the set. The complementary auth/community/invitation matrix
passed 102/102, making the complete Set P replay 317/317. Its first run exposed
seven harness defects—wrapped-app inventory, dual-method path assumptions,
idempotent logout, and one wrong test method—which were corrected only after
explicit control-centre authorization. No security/header/body expectation or
product behavior changed.

The strict model matrix added 552 cases and independently reproduced the same
33 failures twice: unbounded StableId length (`MODEL-001`), coercive integer
fields (`MODEL-002`), coercive booleans (`MODEL-003`), coercive initiative
duration (`MODEL-004`), and coercive `PlanRequest.max_depth` (`MODEL-005`). The
control centre confirmed all five. After the bounded repair was cherry-picked,
the unchanged matrix passed 552/552, adjacent model/API boundaries passed
117/117, HTTP passed 317/317, auth passed 192/192, downstream M7 serialization
passed 49/49, and the current non-adversarial backend collection passed
382/382. MODEL-001..005 were closed at these layers; after the remaining lanes
froze, the complete all-gauntlet backend collection passed 1,975/1,975.

`EXPLAIN-001` originally contained nine red malicious-analyser cases. Control-
centre adjudication classified two as invalid harness assumptions because the
documented seam deliberately accepts a bare valid status, exact `{status}` or
exact matching `{initiative_id,status}` receipt. The remaining seven were
confirmed product defects: mutation of the supplied community; mutation of the
supplied initiative; rich-result initiative mismatch; duplicate assignments;
truncated trace; INFEASIBLE with witness fields; and UNKNOWN with objective or
metrics. After isolated-input and rich-result/canonical-witness validation plus
the bounded source-receipt compatibility repair, the corrected matrix passed
19/19, witness/explain/unlock passed 31/31, dependent tests passed 129/129 and
the non-adversarial backend passed 395/395. The complete frozen backend
collection then passed 1,975/1,975; an independent root replay matched it.

The pre-repair `b9627272` browser marathon found two Chrome HTML-pattern
failures and stopped at step 25:

1. `GAUNTLET-UI-001`: the collaboration slug character-class expression was
   invalid under HTML's current Unicode-sets (`v`) pattern semantics because
   its hyphen was unescaped.
2. `GAUNTLET-UI-002`: the invitation-token character-class expression was
   invalid for the same reason.

Chrome 151 emitted uncaught regular-expression errors and treated each
constraint as valid/fail-open. The bounded product repair `453c84f` escaped the
hyphens for current HTML Unicode-sets semantics. Focused mounted replay proved
the exact rendered patterns, valid/invalid `checkValidity()` behavior and zero
console/page errors. UI-001/002 are closed. The definitive marathon restarted
from a fresh database on that source and completed 37/37.

Harness defects are preserved separately. `GAUNTLET-TEST-001` corrected
invitation list-position assumptions; `TEST-002/003` corrected explanation
compatibility and regex assumptions; `TEST-004` replaced a stale in-page Next
URL waiter; `TEST-005/006` corrected the Project endpoint and supported Reset
route. `TEST-007` through `TEST-033` hardened exact statuses, labels, selectors,
route readiness, keyboard activation, state isolation, accessible-name
extraction, in-memory secrets and screenshot viewports. `TEST-034` records the
Chrome 4×→3× environment cap without claiming 400%. The supplemental battery
also corrected stale copy constants, a static Project-cleared live-region false
positive, the exact `SERVICE_UNAVAILABLE` offline contract, intentional image-
console classification and harness ElementHandle disposal before resource
measurement. None changed product expectations. Every interrupted attempt is
recorded as harness failure, not product evidence.

The read-only documentation audit originally found two confirmed current-state
defects.
`DOC-001` is the stale statement at `contracts/api.md:22` that neither auth nor
M7 has a frontend workflow. `DOC-002` is the stale statement at
`contracts/technical-differentiation-api.md:5-7` that the analyses have no
frontend surface. The control centre repaired those and four adjacent drifts
in six root-owned files, then authorised the repair as a separate cherry-picked
ancestor. Documentation tests pass 11/11 and the machine audit now reports PASS
with zero findings. The audit records immutable
tested identities separately: QA source-overlay `a8b9797` and browser product
source `453c84f`. It does not require an artifact commit to contain its own
future hash. Source identities and evidence hashes are reviewed independently.

## Final statement

**WITHHELD.** The exhaustive release statement is not valid until every required
release gate is green and no known reproducible defect remains within the tested
commit, environments, declared bounded contracts, and completed gauntlet.
