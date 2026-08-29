# Browser evidence — authoritative product source 453c84f

## Identity

- Product source: `453c84fc9c05495b1d21b91f505d8179019f296c`
- Browser: Google Chrome 151.0.7922.175, isolated headless/CDP context
- Frontend: `http://127.0.0.1:3134`
- Backend: `http://127.0.0.1:8018`
- Zero-state/restart DB: `/private/tmp/assemble-gauntlet-final-qGlAm1/auth.sqlite3`
- Gauntlet spec: SHA-256 `97ab573c7e3b99dcee2f9a0bb9d7e00cb338b0a8714fc81a7604f5ff49b8f1f4`, 3,580 lines, 66,719 bytes

The database path is provenance only. The database, session cookies, passwords
and raw invitation token are not part of this evidence directory.

## Executed scripts

| Script | Result |
| --- | --- |
| `community_pattern_regression.mjs` | PASS — exact rendered slug/token patterns, valid/invalid `checkValidity()`, zero console/page errors |
| `final_marathon_phase1_29.mjs` | PASS — definitive steps 1–29 from zero state |
| `final_marathon_phase2_30_37.mjs` | PASS — preserved contexts after controlled backend restart, steps 30–37 |
| `recapture_step37.mjs` | PASS — exact viewport and PNG-width correction |
| `supplemental_resilience_accessibility.mjs` | PASS — S0 truth, pending gate, Judge isolation, 80 responsive/a11y rows, appearance and zoom |
| `remaining_browser_security_visual.mjs` | PASS — Back/Forward, tab isolation, stale/malformed/offline/image/hostile-text/AX-tree gates |
| `browser_loop_performance.mjs` | PASS — 25 complete Basic loops, exact request counts and bounded resource metrics |
| `ultrawide_2560_audit.mjs` | PASS — eight routes at 2560×1440 and screenshot |

Historical interrupted executions are recorded as harness defects in the main
report and are not acceptance evidence.

## Screenshot dimensions and adjudication

| File | Dimensions | Review |
| --- | ---: | --- |
| `phase1-29-owner.png` | 1440×1000 | Owner phase-1 checkpoint |
| `phase1-29-member-390.png` | 390×844 | Member mobile checkpoint |
| `step37-owner-settings-1440.png` | 1440×1140 | Full-page capture from 1440×1000 viewport; readable and unclipped |
| `step37-member-communities-390.png` | 390×981 | Full-page capture from 390×844 viewport; same capability retained |
| `supplemental-basic-s0-stress-1440.png` | 1440×2053 | Four critical outcomes and ratio 0% visibly complete |
| `supplemental-pending-resilience-block-1440.png` | 1440×900 | Exact verification-required boundary |
| `supplemental-settings-dark-high-reduced-320.png` | 320×1362 | Dark/high/reduced controls readable at 320px |
| `supplemental-settings-300pct-environment-cap-1440.png` | 1440×1160 | Measured 300% maximum available reflow |
| `remaining-images-blocked-resilience-320@2x.png` | 640×4164 | 320 CSS px/DPR2; illustration unavailable but all content/actions remain usable |
| `ultrawide-resilience-2560.png` | 2560×1440 | Stable navigation and bounded reading regions at 2560px |

## Network and console classification

- Phase 1: two expected guest-session 401s and one intentional invitation
  replay 404. Three RSC `ERR_ABORTED` entries were speculative prefetch
  cancellations. Logout also logged an abort during navigation, but its exact
  204 response, cookie removal and successful later login prove completion.
- Phase 2: zero console errors, page errors, failed requests or unexpected HTTP
  errors.
- Supplemental matrix: 86 expected guest-session 401s, five speculative RSC
  cancellations, zero unexpected failures.
- Remaining battery: 22 expected guest-session 401s, three intentionally
  blocked image requests, one intentional offline failure, six speculative RSC
  cancellations, zero unexpected failures.
- 2560 audit: nine expected guest-session 401 console entries, three to four
  speculative RSC cancellations across two green replays, zero unexpected
  failures.

## Environment limits

- Firefox and WebKit/Safari: NOT VERIFIED.
- 400% zoom: NOT VERIFIED — Chrome 151 headless/CDP clamped requested 4× to
  measured 3×. Formal 200% and maximum available 300% passed.
- Full every-state × every-viewport × every-theme screenshot Cartesian matrix:
  NOT VERIFIED. The row-level matrix records the bounded coverage completed.
