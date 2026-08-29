# GAUNTLET-ABSOLUTE-01 browser evidence matrix

Status: `EXECUTED — MIXED PASS / PARTIAL / NOT VERIFIED`

This matrix records mounted Chrome evidence for authoritative product source
`453c84fc9c05495b1d21b91f505d8179019f296c`. `PARTIAL` means that a bounded
subset is green and the named remainder was not exercised in a real browser.
It is not a release pass. Historical interrupted runs are harness evidence
only; the definitive 37-step marathon completed from a fresh database.

## Run envelope

| Dimension | Executed evidence |
| --- | --- |
| Runtime | Frontend `http://127.0.0.1:3134`; backend `http://127.0.0.1:8018`; Chrome 151.0.7922.175 headless/CDP |
| Durable state | Fresh private DB `/private/tmp/assemble-gauntlet-final-qGlAm1/auth.sqlite3`; restart at step 30 |
| Viewports | 320, 375, 390, 768, 1024, 1280, 1440, 1920; separate 2560 audit |
| Zoom | Formal 200% PASS; measured 300% PASS; requested 400% clamped and NOT VERIFIED |
| Appearance | system/light/dark, standard/high contrast, system/reduced motion |
| Sessions | guest, Administrator, invited Coordinator then Member; Viewer and expired-session browser contexts not verified |
| Source | S0, verified catalyst successor, pending successor, invalid/malformed source route |
| Faults | malformed response, delayed response, source switch, offline/online, image failure, intentional 401/404, restart |
| Evidence | `tests/adversarial/evidence/browser/final-453c84f/` |

## F — workflow and Project proof

| ID | Journey/check | Expected evidence | Status |
| --- | --- | --- | --- |
| F-01 | Direct `/` and `/community` entry | Fixture loads; one product shell and one scoped application announcement | PASS — 80-row route matrix plus Back/Forward chain |
| F-02 | Community categories and initiative selection | Category-scoped facts; selected initiative changes proof URL without fallback substitution | PASS — marathon category/view/Basic/Clinic traversal |
| F-03 | Unknown and malformed initiative proof URLs | Not-found state, route back, and zero fallback analysis request | PASS — four-route battery, zero Analyse requests |
| F-04 | Basic empty-path proof | Feasible result then separately labelled Project form; exact source proof | PASS — OPTIMAL → Project → Project Proof |
| F-05 | Clinic six-action path | Explain → unlock → plan → apply → verify ordering; Project form absent before fresh verification | PASS — exact six-action sequence and gate |
| F-06 | UNKNOWN successor retry | UNKNOWN remains visible/retryable and cannot create a Project | PARTIAL — backend/pure model only; mounted UNKNOWN not forced |
| F-07 | Projects → Project proof → Back/Forward | Same Project and source proof survive client transitions; no fixture-reset announcement | PASS — marathon plus eight-route browser history chain |
| F-08 | Hard-refresh Project proof | In-memory Project truthfully resets to empty state | PASS — exact empty/session-only disclosure |
| F-09 | Completed journey Reset | Analyses, explanation, path, transition, hashes, Project response, inspector and emphasis clear | PASS — Basic and Clinic reset to S0 |

## Q — parser and stable-failure presentation

| ID | Journey/check | Expected evidence | Status |
| --- | --- | --- | --- |
| Q-01 | Inject malformed auth response for each auth surface | Stable client contract error; no partial identity state | PARTIAL — 25 pure parser cases; not every auth surface mounted |
| Q-02 | Inject malformed Stress/Recovery/Frontier response | Evidence withheld; no operational mapping or Project state | PARTIAL — 55 pure Resilience cases; mounted `{}` Analyse fails closed |
| Q-03 | Replay 401 `AUTHENTICATION_REQUIRED` | Cached signed-in controls clear and account shell becomes guest | PASS — exact guest bootstrap/no-store boundary |
| Q-04 | Replay 401 invalid credentials | Credential failure remains distinct; no session invalidation | PARTIAL — backend/pure state only |
| Q-05 | Replay 403 Administrator operation | Admin data/controls withheld and membership refreshed | PARTIAL — RBAC/live role refresh; in-flight Admin 403 not forced |
| Q-06 | Replay 404/409/429/503 | Code/message envelope remains visible and retryable where offered | PARTIAL — invitation replay 404/offline mounted; remaining statuses HTTP/parser only |
| Q-07 | Delayed reset/switch response | Late data does not repaint the new workflow; abort is not shown as an error | PASS — paused Basic Analyse discarded after Clinic switch |

## R — Resilience Lab

| ID | Journey/check | Expected evidence | Status |
| --- | --- | --- | --- |
| R-01 | Open Resilience before a feasible proof | Verification-required boundary; no stress request | PASS — honest no-proof and pending-successor boundaries |
| R-02 | Basic S0 Stress | Complete one-fact catalogue, truthful ratio/criticality, no Project mutation | PASS — 4/4 CRITICAL, 0 UNKNOWN, ratio 0 |
| R-03 | Trained Clinic Stress | Source state/path match the verified successor; evidence remains analytical | PASS — 6/6 CRITICAL, 0 UNKNOWN, ratio 0 |
| R-04 | Trained Basic Recovery | Selected returned perturbation only; Stage 1 minimum and Stage 2 burden claims | PASS — Priya→Leo, one change, Sam preserved, burden 24 |
| R-05 | S0 Frontier | Independent action cards, Pareto/highest-leverage evidence, no sequence language | PASS — TRAIN highest; TRAIN+BORROW Pareto |
| R-06 | Trained Frontier | Inapplicable training action and source path are truthful | PASS — TRAIN inapplicable, winner null |
| R-07 | Stress → Recovery invalidation | New Stress run clears Recovery result and aborts old Recovery lane | PARTIAL — pure reducer/generation regression only |
| R-08 | Stress/Recovery/Frontier concurrency | Independent lanes do not cancel or repaint each other | PARTIAL — independent lane model only |
| R-09 | Reset/source switch during each lane | Late counterfactual receipts cannot alter community, transition, Project or proof | PARTIAL — mounted delayed Analyse plus pure all-lane guards |

## X — cross-surface parity and interaction continuity

| ID | Journey/check | Expected evidence | Status |
| --- | --- | --- | --- |
| X-01 | 1440/768/390/320 on every destination | Same controls, fields, evidence and destinations; no horizontal overflow | PASS — 80 rows across 8 viewports plus 2560 audit |
| X-02 | Graph/List on all four Community categories | Equivalent entity and fact set; selected detail remains reachable | PASS — marathon traversal |
| X-03 | Keyboard route and tab replay | Native controls, visible opaque focus, tab/tabpanel semantics and focus return | PASS — supported Enter/Space/Radix paths |
| X-04 | Settings as guest and signed-in user | Four allow-listed preferences only; `/preferences` redirects to `/settings` | PASS — redirect and both session states |
| X-05 | Theme/contrast/motion and 200% zoom | No loss of status, controls, focus, or content reflow | PASS WITH LIMIT — 200% and available 300% green; 400% NOT VERIFIED |
| X-06 | Account menu from product shell | Shared application announcement; no competing product live region | PASS — account/proof menus and one shell boundary |

## Y — identity/RBAC/invitation lifecycle

| ID | Journey/check | Expected evidence | Status |
| --- | --- | --- | --- |
| Y-01 | Signup and login by username/email | Session-aware navigation; raw HttpOnly cookie is never read by page code | PASS — signup/logout/new-password login and cookie attributes |
| Y-02 | Refresh, expiry and revoked-session replay | Valid expiry schedules invalidation; stale session controls disappear immediately | PARTIAL — restart/refresh mounted; exact expiry/revocation backend only |
| Y-03 | Profile and password forms | Bounded fields, current-password check, rotated session and clear status | PASS — profile/password/session rotation |
| Y-04 | Logout including already-inactive session | Idempotent signed-out state and announcement | PASS — mounted 204/cookie clear; backend idempotence |
| Y-05 | Create/list Collaboration space | Creator appears as Administrator; planning fixture remains separate | PASS — persisted Administrator community |
| Y-06 | Administrator members/role/invite/audit tabs | Current persisted membership drives controls; protected calls are made only as Administrator | PASS — all four admin tabs/actions exercised |
| Y-07 | Coordinator/Member/Viewer detail | Persisted role shown; no Administrator controls or protected admin calls | PARTIAL — Coordinator then Member mounted; Viewer not mounted |
| Y-08 | Administrator role loss via 403 | Cached administration data/token clears; authoritative membership refreshes | PARTIAL — live Coordinator→Member refresh; Admin 403 not forced |
| Y-09 | Invitation token delivery | Token appears once, copy/dismiss/unmount/request invalidation removes it, list never shows token | PASS — no-store/no-referrer, DOM/list/audit/restart redaction |
| Y-10 | Recipient-bound accept/revoke/replay | Recipient mismatch, revoke, expiry and single-use failures remain stable; audit is secret-free | PARTIAL — accept/replay mounted; wrong-recipient/revoke/expiry/races backend only |
| Y-11 | Restart persistence | Session revocation, role, invite lifecycle and audit survive restart; Project/proof remains session-only | PASS — exact post-restart UI and DB evidence |

## Terminal console/network adjudication

- Definitive phase 1 expected HTTP errors were two guest-session 401 responses
  and one intentional invitation replay 404. Matching Chrome resource entries
  were expected and retained.
- Phase 1 `ERR_ABORTED` entries were one Basic-proof RSC prefetch, two
  community-detail RSC prefetches, and logout navigation. The first three were
  cancelled speculative Next requests. Logout also produced exact HTTP 204,
  cleared the cookie and was followed by successful new-password login; the
  abort occurred during post-response navigation, not instead of the server
  result.
- Phase 2 after restart had zero console errors, page errors, failed requests
  or unexpected HTTP errors.
- The supplemental route matrix had 86 expected guest-session 401s and five
  speculative RSC cancellations; zero unexpected failures.
- The remaining battery had 22 expected guest-session 401s, three intentionally
  blocked images, one intentional offline failure and six speculative RSC
  cancellations; zero unexpected failures.
- The 2560 audit had nine expected guest-session 401 console entries and three
  to four speculative RSC cancellations across two green replays; zero
  unexpected failures.

## Explicitly not verified

- Firefox and WebKit/Safari execution.
- 400% zoom: Chrome 151 headless/CDP clamped requested 4× to measured 3×.
- Full Viewer browser role, mounted session expiry, wrong-password rate UX,
  every response-status/parser permutation and every async lane under delay.
- The full Cartesian product of every named visual state × viewport × theme.

These omissions remain visible in the acceptance report and are not silently
converted into PASS.
