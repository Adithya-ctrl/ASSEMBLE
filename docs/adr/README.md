# Architectural decision records

ADRs are the only repository documentation that preserves past decision context. Current behavior belongs in the Diátaxis pages linked from [`../README.md`](../README.md).

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-bounded-deterministic-solver.md) | Accepted | Use a bounded deterministic CP-SAT proof core |
| [0002](0002-projects-from-verified-plans.md) | Accepted | Derive Projects from authoritative replay and fresh solver proof |
| [0003](0003-equivalent-graph-and-list-views.md) | Accepted | Provide equivalent graph and list representations |
| [0004](0004-living-documentation-and-conventional-commits.md) | Accepted | Govern current docs with Diátaxis, ADR history, and Conventional Commits |
| [0005](0005-civic-assembly-table-direction.md) | Accepted | Use the civic Assembly Table direction with evidence-first constraints |
| [0006](0006-local-identity-community-and-invitation-boundary.md) | Accepted | Use local SQLite-backed identity, membership and recipient-bound invitations |
| [0007](0007-structural-resilience-and-recompilation.md) | Accepted | Keep stress, recompilation and capability-frontier results counterfactual and non-operational |

ADRs are append-oriented. If a decision changes, add a new ADR that explicitly supersedes the old one and update current-state documentation to describe only the replacement.
