# Audit documentation before a milestone

Documentation drift is a hard milestone gate. Code, tests, current documentation, traceability, and current status must change together. Do not accept a milestone, create a commit, or push while current docs are stale.

## Layer A — automated structural audit

Run:

```bash
backend/.venv/bin/pytest -q backend/tests/test_documentation.py
backend/.venv/bin/pytest -q backend/tests
```

The deterministic documentation gate checks:

- local Markdown link integrity, including ADRs and the contract pointer;
- documented API route parity with generated OpenAPI;
- required consecutive `FR-###`, `NFR-###`, and `US-###` identifiers;
- user-story mapping to existing requirements;
- current requirements represented in traceability;
- full-feature-parity requirements and evidence at 320 and 1440 CSS pixels;
- current BUILD_STATUS evidence and hold language;
- Conventional Commit and same-change policy wiring;
- required problem, purpose, user, success-criteria, video, and claim-boundary sections;
- absence of known stale contract markers and prohibited overclaims from current-state sources.

A structural pass proves that the documentation system is wired. It does not prove that the prose matches runtime behavior.

## Layer B — human semantic replay

Run the production-like interface and real API, then compare observed behavior and response bodies against:

- [`../../README.md`](../../README.md);
- [`../reference/requirements.md`](../reference/requirements.md);
- [`../tutorials/project-journeys.md`](../tutorials/project-journeys.md);
- [`../reference/api.md`](../reference/api.md) and [`../reference/project-contract.md`](../reference/project-contract.md);
- [`../reference/security-validation.md`](../reference/security-validation.md);
- [`../reference/accessibility.md`](../reference/accessibility.md);
- [`../presentation/project-overview.md`](../presentation/project-overview.md), the timed video and live-demo runbooks, and the judge Q&A;
- [`../../BUILD_STATUS.md`](../../BUILD_STATUS.md).

Replay both Basic empty-path and Clinic successor-path Project journeys. Check every displayed number, status, action, error code, accessibility behavior, absent capability, and presentation statement against the running software. At both 320 and 1440 CSS pixels, compare controls, flows, three editable fields, inventory facts, proof evidence, and Project capabilities; only layout or label presentation may differ. Confirm current pages contain no superseded behavior; architectural history belongs only in ADRs.

## Gate result

- **PASS:** both layers agree with the same build and traceability is complete.
- **HOLD:** any broken link, missing ID, route drift, stale claim, undocumented behavior, incorrect number, absent negative boundary, failed test, or runtime/document discrepancy.

On HOLD, update the implementation, tests, current documentation, traceability, and BUILD_STATUS as one bounded change, then rerun both layers. Never “fix” drift by weakening a deterministic check or moving current behavior into an ADR.
