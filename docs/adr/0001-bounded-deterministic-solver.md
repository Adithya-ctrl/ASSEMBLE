# ADR 0001: Bounded deterministic solver core

- Status: Accepted
- Date: 2026-08-29

## Context

The event product needed to make auditable feasibility claims from declared community capacity. A generated narrative or unbounded search could not provide a replayable assignment or safe UNKNOWN behavior.

## Decision

Use a deterministic CP-SAT model with declared variables, hard constraints, a bounded action catalogue, bounded explanation runs, and depth-two catalyst planning. Feasible results require a complete assignment and trace. INFEASIBLE and UNKNOWN results carry no witness.

## Consequences

- Claims remain limited to the submitted bounded model.
- The core works offline without an LLM or cloud provider.
- Explanations and unlocks must replay through the solver.
- Social outcomes outside the declared model are not predicted.
