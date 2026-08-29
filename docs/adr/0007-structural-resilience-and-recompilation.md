# ADR 0007: Structural resilience and recompilation are counterfactual analyses

- Status: Accepted for the M7 backend implementation
- Date: 2026-08-29

## Context

The accepted ASSEMBLE core deterministically compiles bounded community data,
solves initiative feasibility, validates canonical witnesses, applies
authoritative catalyst actions, and creates Projects only from verified
operational plans. Stress testing, minimum-disruption recovery, and capability
comparison need those semantics without weakening the existing contracts or
turning analytical branches into operational successors.

## Decision

Implement three additive analyses:

1. Structural Stress Test generates the complete canonical witness-derived
   catalogue, applies exactly one availability fact per scenario, and reports
   resilience over decisive outcomes only.
2. Minimum-Disruption Recompiler uses a private lexicographic solve: Stage 1
   proves the minimum role changes only when `OPTIMAL`; Stage 2 fixes that
   scalar and reuses the normal shared burden objective and unchanged witness
   validator.
3. Capability Frontier evaluates one authoritative action at a time from the
   same source, tracks every initiative status, and ranks only candidates with
   complete decisive coverage.

All requests cross the same authoritative boundary: verify exact submitted
S0 identity, parent metadata, and canonical content; discard it; then replay
an ordered unique authoritative action path of length zero to two from a fresh
S0 copy.

Analytical branches receive versioned `CF_STRESS_V1_` or `CF_FRONTIER_V1_`
receipt IDs bound to source content and counterfactual inputs/content. They do
not enter operational parent/successor lineage and cannot be consumed as
Project states.

## Consequences

- The accepted default compiler objective and all legacy API schemas retain
  their behavior. The compiler gains only an additive objective-control seam
  and an exported normal burden expression.
- Every exposed feasible witness still passes the existing canonical burden
  validator. Stage 1 never exposes an initiative witness.
- Person and venue blocks remain present when unavailable, preserving model
  references; resource requirements remain unchanged.
- Catalogue overflow, forged bases, invalid references, and invalid analyser
  output fail closed with stable errors. Analytical infeasibility, UNKNOWN,
  no-applicable-actions, and zero-unlock remain normal results where specified.
- Frontier results are deliberately one-action comparisons; multi-action
  sequencing remains the planner's responsibility.

## Rejected alternatives

- Deleting selected people or venues: this would disturb referential integrity
  and change more than one availability fact.
- Client-selected perturbations or truncation: this could forge scenarios or
  alter the resilience denominator.
- Treating `FEASIBLE` Stage 1 as a proven minimum: CP-SAT has not proved the
  minimum in that status.
- Making the canonical witness validator objective-agnostic: exposed normal
  results must continue to prove the accepted burden objective.
- Ranking candidates with UNKNOWN coverage: unresolved outcomes could change
  the winner and must remain explicit.

See the
[`technical differentiation contract`](../../contracts/technical-differentiation-api.md)
and the
[`technical differentiation reference`](../reference/technical-differentiation.md).
