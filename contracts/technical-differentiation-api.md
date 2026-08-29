# Technical differentiation API contract

This additive contract defines the backend-only Structural Stress Test,
Minimum-Disruption Recompiler, and one-action Capability Frontier. Existing
routes and schemas remain unchanged.

## Shared trust boundary

Every request supplies the complete base community only so the server can
verify it against authoritative S0. The server compares identity, lineage, and
canonical content, then discards the supplied content and reconstructs the
analysis state from a fresh authoritative S0 copy plus an ordered, unique,
authoritative catalyst path of length zero to two. Client witnesses,
assignments, objectives, readiness, state lineage, perturbations, and action
catalogues are never trusted.

All new collections have explicit ceilings. Catalyst paths contain at most two
unique IDs; initiatives and actions retain their existing fixture ceilings;
the full server-generated perturbation catalogue contains at most 20 entries.
There is no client-selected perturbation truncation.

Solver work is bounded by those collections and the existing seven diagnostic
requirement groups. Stress performs at most 601 solver calls: one baseline,
20 scenario solves, and at most 29 bounded explanation calls for each of 20
infeasible scenarios. Recompile performs at most 32 calls: baseline, Stage 1,
optional Stage 2, and at most 29 explanation calls for an infeasible terminal
stage. Frontier performs `initiatives * (1 + applicable actions)` calls, at
most 1056 (`32 * 33`); inapplicable actions are not solved.

Every `FEASIBLE` or `OPTIMAL` witness is checked by the existing canonical
validator. A validation failure is `ANALYSER_CONTRACT_ERROR`. `INFEASIBLE` and
`UNKNOWN` carry no objective or witness.

## Counterfactual perturbations

`POST /api/stress-test` accepts authoritative-base proof, one initiative ID,
and a catalyst path. A fresh verified witness deterministically generates:

- one `MAKE_ASSIGNED_PERSON_UNAVAILABLE` entry per distinct selected person;
- one `MAKE_SELECTED_VENUE_UNAVAILABLE` entry;
- one `REDUCE_AVAILABLE_RESOURCE` entry per required resource.

Person and venue loss clear only the selected block's `available_slots`
field and are described as becoming unavailable, never removed. The block
remains present, preserving referential integrity. Resource
degradation keeps the ResourceBlock and initiative requirement unchanged and
sets available quantity to `max(0, required quantity - 1)`. Each scenario is
a deep copy that changes exactly one declared availability fact.

Counterfactuals are not operational successors. They retain no normal
parent/successor relationship and return `source_state_id`, `perturbation_id`,
and a deterministic counterfactual `scenario_state_id`. Scenario identity uses
a versioned, domain-separated canonical hash over the source state's canonical
content hash, the canonical perturbation specification, and canonical
perturbed content with identity/parent fields excluded. It never hashes a
recursively self-including `state_id` and cannot collide with the operational
transition state-ID namespace. The counterfactual state's internal parent
field is not exposed or described as operational lineage. Authoritative S0 and
the reconstructed source state remain unchanged.

Catalogue order and perturbation identity are deterministic across reruns.
Entries use fixed type order, then stable target ID, and bind to the source
state's canonical content hash. Duplicate selected people collapse to one
person-loss entry. Before any re-solve, a structural delta assertion compares
canonical payloads and proves that only the intended person's or venue's
`available_slots`, or the intended resource's `quantity`, changed; source
content, source parent metadata, all unrelated entities, and the initiative
requirements remain unchanged.

Perturbation payloads are a typed discriminated union. Person and venue
entries carry exact before/after availability; resource entries carry the
requirement ID, required quantity, and exact before/after available quantity.
An initiative with duplicate authoritative resource requirement IDs fails
closed; the generator never aggregates duplicates or chooses one silently.

The resilience denominator is the full decisive catalogue only:
`OPTIMAL`/`FEASIBLE` survive, `INFEASIBLE` fails, and `UNKNOWN` is reported but
excluded. Objective degradation is `max(0, perturbed burden - baseline
burden)` because lower burden is better.

Stress compares the complete meaningful plan: role-to-person mapping, selected
venue, selected start slot, and burden. `RESILIENT` means all four are
unchanged. Any feasible change is `DEGRADED`; only `INFEASIBLE` is `CRITICAL`,
and only an unresolved solve is `UNKNOWN`. The response may include the signed
objective delta as well as non-negative degradation.

The entire witness-derived catalogue is generated before analysis. If it
exceeds the server constant of 20, the request fails closed with
`PERTURBATION_CATALOGUE_TOO_LARGE`; no entries are truncated, paginated,
sampled, or returned with partial resilience metrics. On success,
`catalogue_size == len(outcomes)` and decisive plus unknown equals the full
catalogue size.

## Minimum-disruption recompilation

`POST /api/recompile` accepts a canonical perturbation ID, never a client
patch. Stage 1 minimises changed baseline role assignments. A minimum is
proven only when Stage 1 is `OPTIMAL`; `FEASIBLE` or `UNKNOWN` fails closed to
an explicit `UNKNOWN` result with no minimum claim and no Stage 2.

Stage 2 fixes the proven minimum-change equality and minimises the compiler's
exported, unchanged burden expression. Stage 2 may return a validated
`FEASIBLE` witness, but it claims optimal secondary burden only when
`OPTIMAL`. An infeasible perturbation is an ordinary HTTP 200 analysis result
with no fabricated replacement witness.

## One-action Capability Frontier

`POST /api/frontier` evaluates each immutable authoritative action at most
once from the reconstructed source state and re-solves every declared
initiative. `UNKNOWN` is tracked and is never counted as newly feasible or
lost. Complete decisive coverage means every baseline initiative status and
every status after that candidate are `OPTIMAL`, `FEASIBLE`, or `INFEASIBLE`.
Only applicable actions with that complete coverage enter leverage ranking or
Pareto analysis.

Frontier action application may reuse the authoritative effect semantics
internally, but the response is a domain-separated counterfactual receipt:
source state ID, action ID, scenario ID, scenario content hash, and diff. It
does not expose an operational predecessor/successor receipt or a
Project-consumable state lineage.

Complete actions rank by newly feasible count descending, cost ascending, and
action ID ascending. Pareto efficiency maximises newly feasible count and
minimises cost. No-applicable-actions and zero-unlock outcomes are ordinary
HTTP 200 analyses. If unresolved outcomes could change the winner,
`highest_leverage_action_id` is null and the response explains the ambiguity.

## Stable failures

Invalid references, duplicate or unavailable paths, forged base content or
lineage, unavailable perturbations, strict-model violations, and analyser
contract failures use the existing stable error envelope. Domain outcomes
such as an infeasible recompile or an empty frontier are not HTTP errors.
Stress or recompile against a non-feasible source plan is a 409
`BASELINE_NOT_FEASIBLE` precondition failure. Mathematically valid scenario or
recompile `INFEASIBLE` and `UNKNOWN` outcomes remain HTTP 200 responses.
