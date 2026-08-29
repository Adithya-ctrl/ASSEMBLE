# B2-G6 documentation and coverage audit

This packet is the read-only GAUNTLET-ABSOLUTE-01 source-of-truth,
documentation-drift and coverage crosswalk audit. Tested source identities are
separate from the later artifact commit identity:

| Item | Value |
| --- | --- |
| Checkout | `/private/tmp/assemble-adversarial-gauntlet` |
| Tested QA source overlay | `a8b9797017668fcc4ae6e9634e2e67d7975ba23d` |
| Tested browser product source | `453c84fc9c05495b1d21b91f505d8179019f296c` |
| Gauntlet specification SHA-256 | `97ab573c7e3b99dcee2f9a0bb9d7e00cb338b0a8714fc81a7604f5ff49b8f1f4` |
| Browser execution | Executed separately on the pinned product source; see the evidence matrix/report |
| Writable scope | `tests/adversarial/audit/**` only |

## Checks

The Python audit has no product imports and performs no writes. It checks:

- immutable tested-source identity constants without a self-referential commit pin;
- API-reference route/method/success parity against Python route decorators (26/26);
- consecutive FR-001–FR-023, NFR-001–NFR-013 and US-001–US-017 inventories;
- complete requirement presence plus populated implementation/evidence rows in `docs/TRACEABILITY.md`;
- all local Markdown links, including ADR links;
- traceability code paths resolve locally;
- the 13 current frontend page files, including Resilience and account routes;
- presence of the 22 claimed adversarial test/evidence category artifacts;
- known superseded current contract claims, with exact source and line evidence.

Run the machine-readable audit from the repository root:

```text
python3 tests/adversarial/audit/run_readonly_audit.py
```

The command prints JSON and exits non-zero for a release-relevant finding. On
the reconciled documentation ancestor the expected result is `status: PASS`
with zero findings. Declared browser/environment gaps remain separately visible
and still prevent the report's exhaustive release statement.

Run the structural wrapper:

```text
pytest -q tests/adversarial/audit/test_readonly_audit.py
```

The wrapper passes the structural checks and requires the machine report to
match the current source findings. It intentionally does not compare the current artifact
commit with a hash embedded inside that same commit, which would be
self-referential. The tested QA and browser source hashes remain explicit and
must be independently checked during integration.

## Closed findings

1. `contracts/api.md:22` says “none of the auth or M7 APIs has a current frontend workflow.” The installed account routes and `/resilience` route contradict that current-state claim. `contracts/auth-api.md:15`, `docs/reference/technical-differentiation.md:3-13`, and `docs/TRACEABILITY.md:25` describe the newer integrated surface.
2. `contracts/technical-differentiation-api.md:5-7` says the current frontend has no surface for the three analyses. `frontend/app/(product)/resilience/page.tsx:1-4` and `frontend/components/resilience/ResilienceIntegration.tsx:193-222` provide that surface.

The control centre repaired these two findings and four adjacent drifts in six
root-owned files with documentation tests 11/11. The authorised documentation
commit is present as a separate ancestor, and the local machine audit now
returns PASS with zero findings.

Historical ADR wording is not treated as current drift: `docs/README.md` assigns superseded architectural decisions to `docs/adr/`. The audit therefore scans current references and contract pointers, while preserving ADRs as history.

## Environment and browser gaps

The audit function itself remains source-only and does not drive the browser.
Separate mounted evidence covers the 37-step Chrome marathon, responsive rows,
screenshots, console/network adjudication, image failure, stale response,
hostile input and bounded performance. Firefox and WebKit/Safari, requested
400% zoom, the full visual Cartesian product, mutation testing, randomized
browser monkey testing and every mounted async/parser/RBAC race permutation
remain not verified. Dependency-backed gates used the authoritative sibling
checkout and are recorded separately from this source-only audit.
