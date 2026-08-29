# Technical differentiation reference

ASSEMBLE exposes three backend-only counterfactual analyses. They reuse the
accepted deterministic compiler, solver, canonical witness validator, action
effects, and Project trust boundary; they do not create Projects or
operational successor states.

The normative field and invariant definitions are in the
[`technical-differentiation-api.md`](../../contracts/technical-differentiation-api.md)
contract. The design rationale is recorded in
[`ADR 0007`](../adr/0007-structural-resilience-and-recompilation.md).

## Common request boundary

Each request includes `base_community` as an exact proof of authoritative S0
and an ordered, unique `catalyst_path` of zero to two authoritative action
IDs. Stress and recompile also include `initiative_id`; recompile includes one
server-issued `perturbation_id`.

The server compares the submitted state ID, parent state ID, and canonical
content with fresh authoritative S0. It then reconstructs the analysis source
from its own S0 and action catalogue. Client-supplied witnesses, objectives,
assignments, patches, scenario states, perturbation details, and action
catalogues are not accepted.

## `POST /api/stress-test`

The Structural Stress Test solves a feasible baseline, generates the complete
canonical witness-derived perturbation catalogue, applies each one-fact
counterfactual change, and re-solves the initiative.

Perturbation kinds are:

- `MAKE_ASSIGNED_PERSON_UNAVAILABLE`: the selected person remains present and
  only `available_slots` changes from a non-empty list to `[]`;
- `MAKE_SELECTED_VENUE_UNAVAILABLE`: the selected space remains present and
  only `available_slots` changes from a non-empty list to `[]`;
- `REDUCE_AVAILABLE_RESOURCE`: the resource and requirement remain unchanged
  except that the authoritative resource quantity becomes exactly
  `required_quantity - 1`.

The full catalogue has a hard ceiling of 20. Exceeding it returns
`422 PERTURBATION_CATALOGUE_TOO_LARGE` before any scenario solve and without a
partial ratio. On success, the response counts are derived from all outcomes;
`UNKNOWN` is reported but excluded from the resilience denominator.

`RESILIENT` requires the same role-person map, venue, start slot, and burden.
Any feasible change is `DEGRADED`, `INFEASIBLE` is `CRITICAL`, and an
unresolved solve is `UNKNOWN`. The production Basic and trained Clinic fixture
catalogues are intentionally all-critical with resilience `0.0`; the API does
not invent richer fixture outcomes.

## `POST /api/recompile`

The Minimum-Disruption Recompiler accepts only a perturbation ID from the
canonical catalogue. Stage 1 rebuilds the normal constraints without the
default burden objective, minimises changed baseline role assignments, and
proves a scalar only when CP-SAT returns `OPTIMAL`. It exposes no assignment
witness or assembly trace.

Stage 1 `FEASIBLE` or `UNKNOWN` makes the overall result `UNKNOWN`, leaves the
minimum null, and prevents Stage 2. After an `OPTIMAL` Stage 1, Stage 2 builds
a fresh model, fixes the change count to the independently checked scalar,
and installs the compiler's shared normal burden objective. Its sole exposed
feasible witness must pass the unchanged canonical validator. Stage 2 may
return `FEASIBLE`, but secondary burden is claimed optimal only for
`OPTIMAL`.

The production trained-Basic recovery replaces unavailable PRIYA with LEO,
preserves SAM, proves one changed assignment, and returns burden 24.

## `POST /api/frontier`

The Capability Frontier evaluates every authoritative action independently
from the same reconstructed source and solves every initiative before and
after that candidate. It is explicitly a one-action frontier, not an action
sequence planner.

Only applicable actions with complete decisive baseline and after-action
coverage enter ranking or Pareto analysis. `UNKNOWN` is never counted as a
gain or loss. If incomplete coverage could change the winner,
`highest_leverage_action_id` is null and the explanation records the
uncertainty. No-applicable-actions and zero-unlock outcomes are ordinary HTTP
200 analyses.

In S0, training unlocks Clinic and is highest leverage; borrowing laptops
unlocks none but remains Pareto-efficient because it costs less; the two
recruitment actions are dominated. After training, the training action is
inapplicable and no remaining action unlocks another initiative, so highest
leverage is null.

## Counterfactual identity and errors

Stress and recompile scenario IDs begin `CF_STRESS_V1_`; frontier scenario IDs
begin `CF_FRONTIER_V1_`. Each is a domain-separated digest bound to the exact
source content and canonical counterfactual specification/content. These IDs
are not operational `S...` state IDs and carry no Project-consumable lineage.

Forged bases return `409 COMMUNITY_STATE_MISMATCH`; a non-feasible stress or
recompile baseline returns `409 BASELINE_NOT_FEASIBLE`; unknown perturbations
return `404 INVALID_PERTURBATION`. Strict request failures remain
`422 INVALID_REQUEST`, and invalid analyser output fails closed as
`500 ANALYSER_CONTRACT_ERROR`. Valid counterfactual `INFEASIBLE` or `UNKNOWN`
results remain HTTP 200 analysis responses.

## Solver-call ceilings

- Stress: at most 601 calls (one baseline, 20 scenario solves, and up to 29
  bounded explanation calls for each infeasible scenario).
- Recompile: at most 32 calls (baseline, Stage 1, optional Stage 2, and up to
  29 bounded explanation calls for an infeasible terminal stage).
- Frontier: `initiatives * (1 + applicable actions)`, at most 1056 under the
  32-initiative and 32-action ceilings. Inapplicable actions require no solve.

For the production fixture, S0 frontier performs 15 calls (three baseline plus
four actions times three initiatives); after training it performs 12 because
the training action is inapplicable.
