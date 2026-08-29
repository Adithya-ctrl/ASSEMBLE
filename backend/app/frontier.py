"""Authoritative one-action capability frontier analysis.

The frontier is deliberately a small orchestration layer around the frozen
state-reconstruction, transition, and solver/replay seams.  It does not
reimplement any domain predicates: applicability and state changes come from
``app.interventions`` and feasible solver witnesses are checked by the
canonical validator in ``app.solver``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from app.analysis_state import reconstruct_authoritative_state
from app.api_models import (
    CapabilityFrontierRequest,
    CapabilityFrontierResponse,
    FrontierActionResult,
    InitiativeAnalysisResult,
    SolverStatus,
)
from app.errors import AnalyserContractError
from app.explain import AnalysisCallable, call_analyser, coerce_status
from app.interventions import (
    TransitionError,
    apply_action,
    can_apply_action,
    canonical_state_hash,
    canonical_state_payload,
)
from app.models import CatalystAction, CommunityState, InitiativeBlueprint
from app.solver import solve_initiative, validate_analysis_witness


_DECISIVE_STATUSES = frozenset(
    {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE, SolverStatus.INFEASIBLE}
)
_FEASIBLE_STATUSES = frozenset({SolverStatus.OPTIMAL, SolverStatus.FEASIBLE})
_SCENARIO_NAMESPACE = "CF_FRONTIER_V1"


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Internal immutable facts used for ranking and uncertainty analysis."""

    action: CatalystAction
    result: FrontierActionResult
    after_statuses: Mapping[str, SolverStatus]

    @property
    def complete(self) -> bool:
        return self.result.decisive_coverage_complete

    @property
    def newly_feasible_count(self) -> int:
        return len(self.result.newly_feasible_initiatives)

    @property
    def ranking_key(self) -> tuple[int, int, str]:
        return (-self.newly_feasible_count, self.action.cost, self.action.id)


def _canonical_value(value: Any) -> Any:
    """Canonicalise JSON-compatible values for a deterministic receipt ID."""

    if isinstance(value, Mapping):
        return {str(key): _canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_canonical_value(item) for item in value]
        return sorted(
            values,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _scenario_receipt(
    source: CommunityState,
    action: CatalystAction,
    scenario: CommunityState,
) -> tuple[str, str]:
    """Return the domain-separated scenario ID and canonical content hash.

    ``state_id_for`` is intentionally not used here.  A frontier scenario is
    a counterfactual analysis receipt, not an operational successor that may
    be consumed by project execution.  Identity and parent metadata are
    excluded from the content hash by ``canonical_state_hash``.
    """

    source_hash = canonical_state_hash(source)
    scenario_content = canonical_state_payload(scenario)
    scenario_content_hash = canonical_state_hash(scenario)
    payload = {
        "namespace": _SCENARIO_NAMESPACE,
        "source_content_hash": source_hash,
        "action": action.model_dump(mode="json"),
        "counterfactual_content": scenario_content,
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest().upper()
    scenario_id = f"{_SCENARIO_NAMESPACE}_{digest}"

    # Recompute from the exact final content before returning the receipt.  A
    # namespace prefix alone is not proof of binding to this source/action
    # pair or to the resulting state content.
    receipt_payload = {
        "namespace": _SCENARIO_NAMESPACE,
        "source_content_hash": canonical_state_hash(source),
        "action": action.model_dump(mode="json"),
        "counterfactual_content": canonical_state_payload(scenario),
    }
    receipt_digest = hashlib.sha256(
        _canonical_json(receipt_payload).encode("utf-8")
    ).hexdigest().upper()
    receipt_id = f"{_SCENARIO_NAMESPACE}_{receipt_digest}"
    if receipt_id != scenario_id:
        raise AnalyserContractError(
            "frontier scenario identity receipt does not match final content"
        )
    return scenario_id, scenario_content_hash


def _model_snapshot(model: Any) -> str:
    """Capture a stable, exact model payload for the immutability proof."""

    if hasattr(model, "model_dump"):
        model = model.model_dump(mode="json")

    def snapshot_value(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): snapshot_value(value[key])
                for key in sorted(value, key=str)
            }
        if isinstance(value, (set, frozenset)):
            values = [snapshot_value(item) for item in value]
            return sorted(
                values,
                key=lambda item: json.dumps(
                    item, sort_keys=True, separators=(",", ":")
                ),
            )
        if isinstance(value, (list, tuple)):
            # Lists are deliberately not sorted: the immutability proof must
            # notice even an otherwise-semantic declaration reorder.
            return [snapshot_value(item) for item in value]
        return value

    return json.dumps(
        snapshot_value(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _assert_input_immutability(
    request: CapabilityFrontierRequest,
    request_base_snapshot: str,
    authoritative_base: CommunityState,
    authoritative_base_snapshot: str,
    authoritative_actions: Sequence[CatalystAction],
    authoritative_action_snapshots: Sequence[str],
    initiatives: Sequence[InitiativeBlueprint],
    initiative_snapshots: Sequence[str],
) -> None:
    """Fail closed if any caller-owned request/authority model was mutated."""

    if _model_snapshot(request.base_community) != request_base_snapshot:
        raise AnalyserContractError(
            "frontier analysis mutated the supplied base community"
        )
    if _model_snapshot(authoritative_base) != authoritative_base_snapshot:
        raise AnalyserContractError(
            "frontier analysis mutated the authoritative base community"
        )
    if [
        _model_snapshot(action) for action in authoritative_actions
    ] != list(authoritative_action_snapshots):
        raise AnalyserContractError(
            "frontier analysis mutated the authoritative action catalogue"
        )
    if [
        _model_snapshot(initiative) for initiative in initiatives
    ] != list(initiative_snapshots):
        raise AnalyserContractError(
            "frontier analysis mutated the initiative catalogue"
        )


def _result_model_or_error(
    raw_result: object,
    *,
    initiative: InitiativeBlueprint,
    status: SolverStatus,
    context: str,
) -> InitiativeAnalysisResult:
    """Coerce a complete witness result, or raise the stable contract error."""

    if isinstance(raw_result, InitiativeAnalysisResult):
        result = raw_result
    elif isinstance(raw_result, Mapping):
        try:
            result = InitiativeAnalysisResult.model_validate(raw_result)
        except (TypeError, ValueError) as exc:
            raise AnalyserContractError(
                f"feasible analyser result for {initiative.id} at {context} "
                "does not contain a valid witness"
            ) from exc
    else:
        raise AnalyserContractError(
            f"feasible analyser result for {initiative.id} at {context} "
            "does not contain a complete witness"
        )

    if result.initiative_id != initiative.id or result.status is not status:
        raise AnalyserContractError(
            f"analyser result for {initiative.id} at {context} has a mismatched "
            "identity or status"
        )
    return result


def _raw_nonfeasible_has_witness(raw_result: object) -> bool:
    """Detect a forged objective/witness on a status-only non-feasible result."""

    if isinstance(raw_result, InitiativeAnalysisResult):
        return bool(
            raw_result.objective_value is not None
            or raw_result.assignments
            or raw_result.assembly_trace
        )
    if isinstance(raw_result, Mapping):
        return any(
            raw_result.get(name) not in (None, [], {}, ())
            for name in ("objective_value", "assignments", "assembly_trace")
        )
    return any(
        getattr(raw_result, name, None) not in (None, [], {}, ())
        for name in ("objective_value", "assignments", "assembly_trace")
    )


def _analyse_one(
    state: CommunityState,
    initiative: InitiativeBlueprint,
    analyser: AnalysisCallable | None,
    *,
    context: str,
) -> SolverStatus:
    """Run one isolated analysis and validate every feasible witness."""

    # The analyser receives an isolated copy.  Validation receives a second
    # clean copy so a third-party analyser cannot make its own mutations part
    # of the proof being checked.
    analysis_state = state.model_copy(deep=True)
    analysis_initiative = initiative.model_copy(deep=True)
    validation_state = state.model_copy(deep=True)
    validation_initiative = initiative.model_copy(deep=True)
    analysis_state_snapshot = _model_snapshot(analysis_state)
    analysis_initiative_snapshot = _model_snapshot(analysis_initiative)
    try:
        raw_result = call_analyser(analyser, analysis_state, analysis_initiative)
        status = coerce_status(raw_result)
    except AnalyserContractError as exc:
        if (
            _model_snapshot(analysis_state) != analysis_state_snapshot
            or _model_snapshot(analysis_initiative) != analysis_initiative_snapshot
        ):
            raise AnalyserContractError(
                f"authoritative analyser mutated its input for {initiative.id} at {context}"
            ) from exc
        raise
    except Exception as exc:
        if (
            _model_snapshot(analysis_state) != analysis_state_snapshot
            or _model_snapshot(analysis_initiative) != analysis_initiative_snapshot
        ):
            raise AnalyserContractError(
                f"authoritative analyser mutated its input for {initiative.id} at {context}"
            ) from exc
        raise AnalyserContractError(
            f"authoritative analyser failed for {initiative.id} at {context}"
        ) from exc

    if (
        _model_snapshot(analysis_state) != analysis_state_snapshot
        or _model_snapshot(analysis_initiative) != analysis_initiative_snapshot
    ):
        raise AnalyserContractError(
            f"authoritative analyser mutated its input for {initiative.id} at {context}"
        )

    if status in _FEASIBLE_STATUSES:
        result = _result_model_or_error(
            raw_result,
            initiative=validation_initiative,
            status=status,
            context=context,
        )
        try:
            valid = validate_analysis_witness(
                validation_state,
                validation_initiative,
                result,
            )
        except Exception as exc:
            raise AnalyserContractError(
                f"feasible analyser result for {initiative.id} at {context} "
                "could not be replayed"
            ) from exc
        if not valid:
            raise AnalyserContractError(
                f"feasible analyser result for {initiative.id} at {context} "
                "failed canonical replay"
            )
    elif status not in {SolverStatus.INFEASIBLE, SolverStatus.UNKNOWN}:
        # Defensive branch for future enum members: unknown statuses must not
        # silently enter ranking semantics.
        raise AnalyserContractError(
            f"analyser returned unsupported status {status!r} for {initiative.id}"
        )
    elif _raw_nonfeasible_has_witness(raw_result):
        raise AnalyserContractError(
            f"non-feasible analyser result for {initiative.id} at {context} "
            "must not contain an objective or witness"
        )

    # A model-shaped non-feasible result still needs to identify the initiative
    # and agree with its coerced status.  Status-only mappings remain a useful
    # test seam for UNKNOWN/INFEASIBLE outcomes.
    if isinstance(raw_result, InitiativeAnalysisResult):
        if (
            raw_result.initiative_id != initiative.id
            or raw_result.status is not status
        ):
            raise AnalyserContractError(
                f"analyser result for {initiative.id} at {context} has a mismatched "
                "identity or status"
            )
    elif isinstance(raw_result, Mapping) and "initiative_id" in raw_result:
        if str(raw_result["initiative_id"]) != initiative.id:
            raise AnalyserContractError(
                f"analyser result for {initiative.id} at {context} has a mismatched identity"
            )
    return status


def _baseline_buckets(
    initiatives: Sequence[InitiativeBlueprint],
    statuses: Mapping[str, SolverStatus],
) -> tuple[list[str], list[str], list[str]]:
    buildable: list[str] = []
    blocked: list[str] = []
    unknown: list[str] = []
    for initiative in initiatives:
        status = statuses[initiative.id]
        if status in _FEASIBLE_STATUSES:
            buildable.append(initiative.id)
        elif status is SolverStatus.INFEASIBLE:
            blocked.append(initiative.id)
        else:
            unknown.append(initiative.id)
    return sorted(buildable), sorted(blocked), sorted(unknown)


def _upper_bound_newly_feasible(
    baseline_statuses: Mapping[str, SolverStatus],
    after_statuses: Mapping[str, SolverStatus],
) -> int:
    """Return a sound upper bound for an incompletely observed candidate."""

    return sum(
        baseline_statuses[initiative_id] in {
            SolverStatus.INFEASIBLE,
            SolverStatus.UNKNOWN,
        }
        and after_statuses[initiative_id]
        in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE, SolverStatus.UNKNOWN}
        for initiative_id in baseline_statuses
    )


def _could_incomplete_candidate_beat(
    candidate: _Candidate,
    winner: _Candidate | None,
    baseline_statuses: Mapping[str, SolverStatus],
) -> bool:
    """Use upper-bound count followed by the frozen cost/ID tie-break."""

    upper_bound = _upper_bound_newly_feasible(
        baseline_statuses,
        candidate.after_statuses,
    )
    if upper_bound <= 0:
        return False
    if winner is None:
        return True
    winner_count = winner.newly_feasible_count
    if upper_bound > winner_count:
        return True
    if upper_bound < winner_count:
        return False
    return (candidate.action.cost, candidate.action.id) < (
        winner.action.cost,
        winner.action.id,
    )


def _pareto_candidates(candidates: Sequence[_Candidate]) -> list[_Candidate]:
    efficient: list[_Candidate] = []
    for candidate in candidates:
        dominated = any(
            other is not candidate
            and other.newly_feasible_count >= candidate.newly_feasible_count
            and other.action.cost <= candidate.action.cost
            and (
                other.newly_feasible_count > candidate.newly_feasible_count
                or other.action.cost < candidate.action.cost
            )
            for other in candidates
        )
        if not dominated:
            efficient.append(candidate)
    return sorted(efficient, key=lambda item: item.ranking_key)


def _ranking_explanation(
    *,
    applicable_count: int,
    complete_candidates: Sequence[_Candidate],
    winner: _Candidate | None,
    uncertainty: bool,
) -> str:
    if applicable_count == 0:
        return (
            "No authoritative action is applicable in the reconstructed source "
            "state; no frontier candidate was ranked."
        )
    if uncertainty:
        return (
            "The highest-leverage action is withheld because incomplete decisive "
            "coverage could change the winner under honest upper bounds and the "
            "cost/ID tie-break."
        )
    if not complete_candidates:
        return (
            "No applicable action has complete decisive coverage, so no action is "
            "ranked; unresolved UNKNOWN outcomes cannot support a leverage claim."
        )
    if winner is None:
        return (
            "Complete applicable actions unlock no additional initiatives; highest "
            "leverage is intentionally null. UNKNOWN outcomes are excluded from claims."
        )
    return (
        "Complete actions rank by newly feasible initiatives descending, then cost "
        f"ascending, then action ID; {winner.action.id} unlocks "
        f"{winner.newly_feasible_count} initiative(s). UNKNOWN outcomes are excluded."
    )


def evaluate_capability_frontier(
    request: CapabilityFrontierRequest,
    initiatives: Sequence[InitiativeBlueprint],
    authoritative_base: CommunityState,
    authoritative_actions: Sequence[CatalystAction],
    analyser: AnalysisCallable | None = solve_initiative,
) -> CapabilityFrontierResponse:
    """Evaluate every authoritative action exactly once from one source state."""

    # Snapshot all caller-owned models before any work.  All solver/transition
    # calls below receive deep copies; the snapshots are checked on every
    # normal return, including the no-applicable-actions domain outcome.
    request_base_snapshot = _model_snapshot(request.base_community)
    authoritative_base_snapshot = _model_snapshot(authoritative_base)
    actions_snapshot = tuple(
        action.model_copy(deep=True) for action in authoritative_actions
    )
    action_snapshots = tuple(_model_snapshot(action) for action in authoritative_actions)
    initiative_snapshot = tuple(
        initiative.model_copy(deep=True) for initiative in initiatives
    )
    initiative_input_snapshots = tuple(
        _model_snapshot(initiative) for initiative in initiatives
    )

    initiative_ids = [initiative.id for initiative in initiative_snapshot]
    if len(initiative_ids) != len(set(initiative_ids)):
        raise ValueError("initiative catalogue contains duplicate IDs")
    action_ids = [action.id for action in actions_snapshot]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("authoritative action catalogue contains duplicate IDs")

    # The reconstruction boundary verifies request S0 identity/content and
    # replays only the requested authoritative path from a fresh copy.
    source_state = reconstruct_authoritative_state(
        request.base_community,
        request.catalyst_path,
        authoritative_base.model_copy(deep=True),
        tuple(action.model_copy(deep=True) for action in actions_snapshot),
    )
    source_snapshot = source_state.model_copy(deep=True)

    baseline_statuses: dict[str, SolverStatus] = {}
    for initiative in initiative_snapshot:
        baseline_statuses[initiative.id] = _analyse_one(
            source_snapshot,
            initiative,
            analyser,
            context="baseline",
        )
    buildable_ids, blocked_ids, unknown_ids = _baseline_buckets(
        initiative_snapshot,
        baseline_statuses,
    )

    candidates: list[_Candidate] = []
    action_results: list[FrontierActionResult] = []
    applicable_count = 0

    for action in actions_snapshot:
        action_for_eval = action.model_copy(deep=True)
        source_for_action = source_snapshot.model_copy(deep=True)
        # ``can_apply_action`` validates only the source copy.  No action is
        # ever probed against another candidate's successor state.
        if not can_apply_action(source_for_action, action_for_eval):
            action_results.append(
                FrontierActionResult(
                    source_state_id=source_snapshot.state_id,
                    action_id=action.id,
                    action_name=action.name,
                    cost=action.cost,
                    applicable=False,
                    decisive_coverage_complete=False,
                    explanation=(
                        "Action is not applicable in the reconstructed source "
                        "state; it was not applied and produced no analyses."
                    ),
                )
            )
            continue

        applicable_count += 1
        try:
            successor, diff = apply_action(source_for_action, action_for_eval)
        except (TransitionError, ValueError) as exc:
            # Applicability and application must agree.  A disagreement is an
            # analyser/transition contract failure, not a normal result.
            raise AnalyserContractError(
                f"authoritative action {action.id} changed applicability between "
                "validation and application"
            ) from exc

        scenario = successor.model_copy(deep=True)
        # A frontier scenario is not an operational successor.  Preserve
        # the source's parent metadata while assigning a separate,
        # versioned receipt ID below.
        scenario.parent_state_id = source_snapshot.parent_state_id
        scenario_state_id, scenario_content_hash = _scenario_receipt(
            source_snapshot,
            action_for_eval,
            scenario,
        )
        scenario.state_id = scenario_state_id

        after_statuses: dict[str, SolverStatus] = {}
        for initiative in initiative_snapshot:
            after_statuses[initiative.id] = _analyse_one(
                scenario,
                initiative,
                analyser,
                context=f"action {action.id}",
            )

        newly_feasible = sorted(
            initiative.id
            for initiative in initiative_snapshot
            if baseline_statuses[initiative.id] is SolverStatus.INFEASIBLE
            and after_statuses[initiative.id] in _FEASIBLE_STATUSES
        )
        lost_feasible = sorted(
            initiative.id
            for initiative in initiative_snapshot
            if baseline_statuses[initiative.id] in _FEASIBLE_STATUSES
            and after_statuses[initiative.id] is SolverStatus.INFEASIBLE
        )
        unresolved = sorted(
            initiative.id
            for initiative in initiative_snapshot
            if baseline_statuses[initiative.id] is SolverStatus.UNKNOWN
            or after_statuses[initiative.id] is SolverStatus.UNKNOWN
        )
        decisive_complete = not unresolved
        result = FrontierActionResult(
            source_state_id=source_snapshot.state_id,
            action_id=action.id,
            action_name=action.name,
            cost=action.cost,
            applicable=True,
            scenario_state_id=scenario_state_id,
            scenario_content_hash=scenario_content_hash,
            newly_feasible_initiatives=newly_feasible,
            lost_feasible_initiatives=lost_feasible,
            unknown_initiatives=unresolved,
            total_feasible_after=sum(
                status in _FEASIBLE_STATUSES for status in after_statuses.values()
            ),
            produced_diff=diff.model_copy(deep=True),
            statuses_after=dict(after_statuses),
            decisive_coverage_complete=decisive_complete,
            explanation=(
                "Action was applicable from the reconstructed source state and "
                + (
                    "has complete decisive coverage."
                    if decisive_complete
                    else "has unresolved UNKNOWN analysis coverage."
                )
            ),
        )
        candidate = _Candidate(
            action=action.model_copy(deep=True),
            result=result,
            after_statuses=dict(after_statuses),
        )
        candidates.append(candidate)
        action_results.append(result)

    complete_candidates = [candidate for candidate in candidates if candidate.complete]
    ranked_complete = sorted(complete_candidates, key=lambda item: item.ranking_key)
    complete_unlocking = [
        candidate
        for candidate in ranked_complete
        if candidate.newly_feasible_count > 0
    ]
    exact_winner = complete_unlocking[0] if complete_unlocking else None

    uncertainty = any(
        not candidate.complete
        and _could_incomplete_candidate_beat(
            candidate,
            exact_winner,
            baseline_statuses,
        )
        for candidate in candidates
    )
    # If there is no complete unlocking action, an incomplete candidate
    # with a positive upper bound could create the first winner.
    highest = None if uncertainty or exact_winner is None else exact_winner.action.id

    pareto = _pareto_candidates(complete_candidates)
    explanation = _ranking_explanation(
        applicable_count=applicable_count,
        complete_candidates=complete_candidates,
        winner=exact_winner,
        uncertainty=uncertainty,
    )
    response = CapabilityFrontierResponse(
        source_state_id=source_snapshot.state_id,
        baseline_statuses=dict(baseline_statuses),
        baseline_buildable_ids=buildable_ids,
        baseline_blocked_ids=blocked_ids,
        baseline_unknown_ids=unknown_ids,
        action_results=action_results,
        pareto_action_ids=[candidate.action.id for candidate in pareto],
        highest_leverage_action_id=highest,
        ranking_explanation=explanation,
        uncertainty_could_change_winner=uncertainty,
    )

    _assert_input_immutability(
        request,
        request_base_snapshot,
        authoritative_base,
        authoritative_base_snapshot,
        authoritative_actions,
        action_snapshots,
        initiatives,
        initiative_input_snapshots,
    )
    return response


__all__ = ["evaluate_capability_frontier"]
