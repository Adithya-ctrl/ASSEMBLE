"""Minimum-disruption recompilation for one canonical perturbation.

The recompiler deliberately owns only the additional objective used to compare
role assignments.  Eligibility, availability, venue, resource, and
contribution semantics remain in :mod:`app.compiler`; the final witness is
decoded and replayed by :func:`app.solver.solve_compiled`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import importlib
from typing import Any, cast

from ortools.sat.python import cp_model

from app.analysis_state import reconstruct_authoritative_state
from app.api_models import (
    BlockingRequirementSet,
    InitiativeAnalysisResult,
    RecompileRequest,
    RecompileResponse,
    RecompileRoleDiff,
    SolverStatus,
    MAX_PERTURBATIONS,
)
from app.compiler import (
    CompiledInitiative,
    compile_initiative,
)
from app.errors import AnalyserContractError
from app.explain import call_analyser, coerce_status
from app.models import CatalystAction, CommunityState, InitiativeBlueprint
from app.solver import (
    DEFAULT_TIME_LIMIT_SECONDS,
    configure_solver,
    integral_objective_value,
    solve_compiled,
    solve_initiative,
    solver_stats,
    solver_status_from_cp_sat,
    validate_analysis_witness,
)


class InvalidPerturbation(ValueError):
    """Raised when a request does not identify a canonical perturbation."""


class _FallbackBaselineNotFeasible(ValueError):
    """Fallback used while the resilience module is not available."""


class _FallbackPerturbationCatalogueTooLarge(ValueError):
    """Fallback used while the resilience module is not available."""

    def __init__(self, catalogue_size: int) -> None:
        self.catalogue_size = catalogue_size
        super().__init__(
            f"canonical perturbation catalogue contains {catalogue_size} entries; "
            f"the maximum is {MAX_PERTURBATIONS}"
        )


def _resilience_module() -> Any:
    """Load the resilience implementation lazily.

    M7-R and M7-S are developed in parallel.  Keeping this import lazy lets
    focused recompiler tests run against a small monkeypatched module and
    avoids making module import order part of the public contract.
    """

    try:
        return importlib.import_module("app.resilience")
    except ModuleNotFoundError as exc:
        if exc.name != "app.resilience":
            raise
        raise AnalyserContractError("app.resilience is not available") from exc


def _exception_type(name: str, fallback: type[ValueError]) -> type[ValueError]:
    try:
        candidate = getattr(_resilience_module(), name)
    except (AnalyserContractError, AttributeError):
        return fallback
    return candidate if isinstance(candidate, type) else fallback


# Export the canonical error names when resilience.py already provides them;
# the fallback keeps direct imports useful during the parallel M7-S build.
BaselineNotFeasible = _exception_type(
    "BaselineNotFeasible", _FallbackBaselineNotFeasible
)
PerturbationCatalogueTooLarge = _exception_type(
    "PerturbationCatalogueTooLarge", _FallbackPerturbationCatalogueTooLarge
)


AnalysisCallable = Callable[..., object]


def _status(result: object) -> SolverStatus:
    """Coerce a solver result status through the shared analyser seam."""

    return coerce_status(result)


def _model_snapshot(model: Any) -> object:
    """Capture a deterministic enough snapshot for mutation assertions."""

    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model


def _assert_unchanged(
    model: Any,
    snapshot: object,
    *,
    label: str,
) -> None:
    if _model_snapshot(model) != snapshot:
        raise AnalyserContractError(f"recompiler input {label} was mutated")


def _raw_result_has_witness(result: object) -> bool:
    """Detect objective/witness payloads attached to non-feasible results."""

    fields = ("objective_value", "assignments", "assembly_trace")
    if isinstance(result, Mapping):
        return any(result.get(field) not in (None, [], {}, ()) for field in fields)
    return any(
        getattr(result, field, None) not in (None, [], {}, ()) for field in fields
    )


def _isolated_analyser(analyser: AnalysisCallable) -> AnalysisCallable:
    """Wrap an analyser with disposable inputs and independent replay state."""

    def wrapped(
        community: CommunityState,
        initiative: InitiativeBlueprint,
        *,
        relaxed_groups: Sequence[object] = (),
    ) -> object:
        call_source_snapshot = _model_snapshot(community)
        call_initiative_snapshot = _model_snapshot(initiative)
        analysis_source = community.model_copy(deep=True)
        analysis_initiative = initiative.model_copy(deep=True)
        analysis_source_snapshot = _model_snapshot(analysis_source)
        analysis_initiative_snapshot = _model_snapshot(analysis_initiative)
        clean_source = community.model_copy(deep=True)
        clean_initiative = initiative.model_copy(deep=True)
        try:
            raw = call_analyser(
                analyser,
                analysis_source,
                analysis_initiative,
                relaxed_groups=relaxed_groups,
            )
        except AnalyserContractError:
            raise
        except Exception as exc:
            raise AnalyserContractError(
                "authoritative analyser failed during isolated recompile analysis"
            ) from exc
        _assert_unchanged(
            analysis_source,
            analysis_source_snapshot,
            label="analysis state",
        )
        _assert_unchanged(
            analysis_initiative,
            analysis_initiative_snapshot,
            label="analysis initiative",
        )
        _assert_unchanged(community, call_source_snapshot, label="source state")
        _assert_unchanged(initiative, call_initiative_snapshot, label="initiative")

        status = _status(raw)
        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            if isinstance(raw, InitiativeAnalysisResult):
                result = raw
            else:
                try:
                    result = InitiativeAnalysisResult.model_validate(raw)
                except (TypeError, ValueError) as exc:
                    raise AnalyserContractError(
                        "feasible analyser result must contain a complete witness"
                    ) from exc
            if result.initiative_id != initiative.id or result.status is not status:
                raise AnalyserContractError(
                    "feasible analyser result has a mismatched identity or status"
                )
            if not validate_analysis_witness(
                clean_source,
                clean_initiative,
                result,
                relaxed_groups=relaxed_groups,
            ):
                raise AnalyserContractError(
                    f"feasible analyser result for {initiative.id} failed canonical replay"
                )
            return result

        if _raw_result_has_witness(raw):
            raise AnalyserContractError(
                "non-feasible analyser result must not contain an objective or witness"
            )
        return raw

    return wrapped


def _call_baseline_safely(
    analyser: AnalysisCallable,
    source: CommunityState,
    initiative: InitiativeBlueprint,
) -> InitiativeAnalysisResult:
    """Analyse isolated copies and replay against an untouched snapshot."""

    isolated = _isolated_analyser(analyser)
    raw = call_analyser(isolated, source, initiative)
    return _require_baseline_result(
        raw,
        source.model_copy(deep=True),
        initiative.model_copy(deep=True),
    )


def _require_baseline_result(
    result: object,
    community: CommunityState,
    initiative: InitiativeBlueprint,
) -> InitiativeAnalysisResult:
    """Require a complete, canonically replayable baseline witness."""

    status = _status(result)
    if status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        raise BaselineNotFeasible(
            f"baseline initiative {initiative.id} is {status.value}; a feasible baseline is required"
        )
    if not isinstance(result, InitiativeAnalysisResult):
        raise AnalyserContractError(
            "authoritative baseline analyser must return InitiativeAnalysisResult"
        )
    if not validate_analysis_witness(community, initiative, result):
        raise AnalyserContractError(
            f"baseline solver result for {initiative.id} failed canonical replay"
        )
    return result


def _generate_catalogue(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    baseline: InitiativeAnalysisResult,
) -> list[object]:
    resilience = _resilience_module()
    generator = getattr(resilience, "generate_canonical_perturbations", None)
    if not callable(generator):
        raise AnalyserContractError(
            "app.resilience does not expose generate_canonical_perturbations"
        )

    source_snapshot = _model_snapshot(source)
    initiative_snapshot = _model_snapshot(initiative)
    generated = generator(source, initiative, baseline)
    try:
        catalogue = list(cast(Sequence[object], generated))
    except TypeError as exc:
        raise AnalyserContractError(
            "canonical perturbation generator must return a collection"
        ) from exc
    _assert_unchanged(source, source_snapshot, label="source state")
    _assert_unchanged(initiative, initiative_snapshot, label="initiative")
    if len(catalogue) > MAX_PERTURBATIONS:
        catalogue_size = len(catalogue)
        try:
            error = PerturbationCatalogueTooLarge(catalogue_size)
        except TypeError:
            error = PerturbationCatalogueTooLarge(
                f"canonical perturbation catalogue contains {catalogue_size} entries; "
                f"the maximum is {MAX_PERTURBATIONS}"
            )
        raise error
    if not catalogue:
        raise InvalidPerturbation("canonical perturbation catalogue is empty")
    ids: list[str] = []
    for item in catalogue:
        item_id = getattr(item, "id", None)
        if not isinstance(item_id, str):
            raise AnalyserContractError(
                "canonical perturbation catalogue contains an item without an ID"
            )
        ids.append(item_id)
    if len(ids) != len(set(ids)):
        raise InvalidPerturbation("canonical perturbation catalogue contains duplicate IDs")
    return catalogue


def _resolve_perturbation(catalogue: Sequence[object], perturbation_id: str) -> object:
    for perturbation in catalogue:
        if getattr(perturbation, "id", None) == perturbation_id:
            return perturbation
    raise InvalidPerturbation(
        f"perturbation {perturbation_id} is not in the canonical catalogue"
    )


def _apply_perturbation(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    perturbation: object,
) -> CommunityState:
    resilience = _resilience_module()
    applier = getattr(resilience, "apply_canonical_perturbation", None)
    if not callable(applier):
        raise AnalyserContractError(
            "app.resilience does not expose apply_canonical_perturbation"
        )
    source_snapshot = _model_snapshot(source)
    initiative_snapshot = _model_snapshot(initiative)
    applied = applier(source, initiative, perturbation)
    _assert_unchanged(source, source_snapshot, label="source state")
    _assert_unchanged(initiative, initiative_snapshot, label="initiative")
    scenario_type = getattr(resilience, "CounterfactualScenario", None)
    verifier = getattr(resilience, "validate_counterfactual_scenario", None)
    if not isinstance(scenario_type, type) or not callable(verifier):
        raise AnalyserContractError(
            "app.resilience must expose CounterfactualScenario and "
            "validate_counterfactual_scenario"
        )
    if not isinstance(applied, scenario_type):
        raise AnalyserContractError(
            "canonical perturbation applier must return a CounterfactualScenario"
        )
    verified = verifier(source, initiative, perturbation, applied)
    if not isinstance(verified, scenario_type):
        raise AnalyserContractError(
            "counterfactual scenario verifier must return a CounterfactualScenario"
        )
    _assert_unchanged(source, source_snapshot, label="source state")
    _assert_unchanged(initiative, initiative_snapshot, label="initiative")
    return verified.state


def _baseline_assignment_by_role(result: InitiativeAnalysisResult) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for assignment in result.assignments:
        if assignment.role_instance_id in mapping:
            raise AnalyserContractError("baseline witness contains duplicate role assignments")
        mapping[assignment.role_instance_id] = assignment.person_id
    return mapping


def _change_expression(
    compiled: CompiledInitiative,
    baseline_by_role: Mapping[str, str],
) -> Any:
    """Build the one recompiler-specific scalar from compiler variables."""

    terms: list[Any] = []
    for role in compiled.initiative.roles:
        baseline_person = baseline_by_role.get(role.id)
        if baseline_person is None:
            raise AnalyserContractError(
                f"baseline witness has no assignment for role {role.id}"
            )
        variable = compiled.assignment_vars.get((role.id, baseline_person))
        terms.append(1 - variable if variable is not None else 1)
    return sum(terms, 0)


def _selected_change_count(
    compiled: CompiledInitiative,
    solver: cp_model.CpSolver,
    baseline_by_role: Mapping[str, str],
) -> int:
    count = 0
    for role in compiled.initiative.roles:
        baseline_person = baseline_by_role[role.id]
        variable = compiled.assignment_vars.get((role.id, baseline_person))
        if variable is None:
            count += 1
            continue
        value = int(solver.Value(variable))
        if value not in (0, 1):
            raise AnalyserContractError(
                "Stage 1 returned a non-Boolean assignment variable value"
            )
        count += 1 - value
    return count


def _new_solver(
    *,
    time_limit_seconds: float,
    random_seed: int,
    provided: cp_model.CpSolver | None,
) -> cp_model.CpSolver:
    solver = provided or cp_model.CpSolver()
    configure_solver(
        solver,
        time_limit_seconds=time_limit_seconds,
        num_search_workers=1,
        random_seed=random_seed,
    )
    return solver


def _blockers_if_infeasible(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    analyser: AnalysisCallable,
) -> list[BlockingRequirementSet]:
    """Best-effort factual blockers for an ordinary infeasible response."""

    try:
        from app.explain import explain_infeasibility

        community_snapshot = _model_snapshot(community)
        initiative_snapshot = _model_snapshot(initiative)
        explained = explain_infeasibility(
            community.model_copy(deep=True),
            initiative.model_copy(deep=True),
            _isolated_analyser(analyser),
        )
        _assert_unchanged(community, community_snapshot, label="scenario state")
        _assert_unchanged(initiative, initiative_snapshot, label="initiative")
        return list(explained.blocking_requirement_sets)
    except AnalyserContractError as exc:
        # An injected analyser that only supports the ordinary two-argument
        # call cannot serve bounded blocker relaxations.  Preserve the normal
        # infeasible domain result in that case, but never hide an explicit
        # mutation/isolating-input violation.
        if "mutated" in str(exc):
            raise
        return []
    except (TypeError, ValueError, RuntimeError):
        # An infeasible domain outcome remains valid even if an injected test
        # analyser cannot serve the optional bounded explanation seam.
        return []


def _unknown_response(
    *,
    request: RecompileRequest,
    source: CommunityState,
    scenario: CommunityState,
    perturbation: object,
    stage1_status: SolverStatus,
    stage1_stats: Any,
    explanation: str,
) -> RecompileResponse:
    return RecompileResponse(
        initiative_id=request.initiative_id,
        source_state_id=source.state_id,
        perturbation_id=request.perturbation_id,
        scenario_state_id=scenario.state_id,
        perturbation=perturbation,
        status=SolverStatus.UNKNOWN,
        minimum_assignment_changes=None,
        preserved_assignments=None,
        changed_assignments=None,
        role_diffs=[],
        new_result=None,
        blockers=[],
        stage1_status=stage1_status,
        stage1_solver_stats=stage1_stats,
        stage2_status=None,
        stage2_solver_stats=None,
        minimum_proven=False,
        secondary_burden_optimal=False,
        explanation=explanation,
    )


def _ordinary_response(
    *,
    request: RecompileRequest,
    source: CommunityState,
    scenario: CommunityState,
    perturbation: object,
    status: SolverStatus,
    stage1_status: SolverStatus,
    stage1_stats: Any,
    stage2_status: SolverStatus | None,
    stage2_stats: Any | None,
    minimum_changes: int | None,
    minimum_proven: bool,
    secondary_optimal: bool,
    new_result: InitiativeAnalysisResult | None,
    blockers: Sequence[BlockingRequirementSet],
    role_diffs: Sequence[RecompileRoleDiff],
    preserved: int | None,
    changed: int | None,
    explanation: str,
) -> RecompileResponse:
    return RecompileResponse(
        initiative_id=request.initiative_id,
        source_state_id=source.state_id,
        perturbation_id=request.perturbation_id,
        scenario_state_id=scenario.state_id,
        perturbation=perturbation,
        status=status,
        minimum_assignment_changes=minimum_changes,
        preserved_assignments=preserved,
        changed_assignments=changed,
        role_diffs=list(role_diffs),
        new_result=new_result,
        blockers=list(blockers),
        stage1_status=stage1_status,
        stage1_solver_stats=stage1_stats,
        stage2_status=stage2_status,
        stage2_solver_stats=stage2_stats,
        minimum_proven=minimum_proven,
        secondary_burden_optimal=secondary_optimal,
        explanation=explanation,
    )


def recompile_minimum_disruption(
    request: RecompileRequest,
    initiative: InitiativeBlueprint,
    authoritative_base: CommunityState,
    authoritative_actions: Sequence[CatalystAction],
    analyser: AnalysisCallable = solve_initiative,
    *,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    random_seed: int = 0,
    stage1_solver: cp_model.CpSolver | None = None,
    stage2_solver: cp_model.CpSolver | None = None,
) -> RecompileResponse:
    """Recompile one canonical perturbation with a proven two-stage objective.

    The request's base is used only as an exact proof of S0.  The source,
    catalogue, perturbation, and scenario are all reconstructed from
    authoritative inputs before any stage metrics are produced.
    """

    if request.initiative_id != initiative.id:
        raise InvalidPerturbation(
            f"request initiative {request.initiative_id} does not match {initiative.id}"
        )

    source = reconstruct_authoritative_state(
        request.base_community,
        request.catalyst_path,
        authoritative_base,
        authoritative_actions,
    )

    # Baseline proof is deliberately normal and canonical.  A custom
    # analyser can inject status behaviour for focused tests, but cannot avoid
    # the existing witness validator when it claims feasibility.
    baseline = _call_baseline_safely(analyser, source, initiative)
    baseline_by_role = _baseline_assignment_by_role(baseline)

    # Generate and validate the complete catalogue before resolving a target
    # or applying a scenario.  This prevents overflow from returning partial
    # metrics and ensures the client cannot submit a patch/spec of its own.
    catalogue = _generate_catalogue(source, initiative, baseline)
    perturbation = _resolve_perturbation(catalogue, request.perturbation_id)
    scenario = _apply_perturbation(source, initiative, perturbation)

    # Stage 1: no ordinary burden objective is installed.  Its only objective
    # is the scalar number of role assignment changes from the baseline.
    stage1_compiled = compile_initiative(
        scenario,
        initiative,
        objective_mode="none",
    )
    stage1_changes = _change_expression(stage1_compiled, baseline_by_role)
    stage1_compiled.model.Minimize(stage1_changes)
    cp_stage1 = _new_solver(
        time_limit_seconds=time_limit_seconds,
        random_seed=random_seed,
        provided=stage1_solver,
    )
    stage1_code = cp_stage1.Solve(stage1_compiled.model)
    stage1_status = solver_status_from_cp_sat(stage1_code)
    stage1_solver_stats = solver_stats(cp_stage1)

    if stage1_status is SolverStatus.FEASIBLE:
        return _unknown_response(
            request=request,
            source=source,
            scenario=scenario,
            perturbation=perturbation,
            stage1_status=stage1_status,
            stage1_stats=stage1_solver_stats,
            explanation=(
                "Stage 1 returned FEASIBLE without a proof; replacement analysis is UNKNOWN."
            ),
        )
    if stage1_status is SolverStatus.UNKNOWN:
        return _unknown_response(
            request=request,
            source=source,
            scenario=scenario,
            perturbation=perturbation,
            stage1_status=stage1_status,
            stage1_stats=stage1_solver_stats,
            explanation=(
                "Stage 1 returned UNKNOWN without a proof; replacement analysis is UNKNOWN."
            ),
        )
    if stage1_status is SolverStatus.INFEASIBLE:
        blockers = _blockers_if_infeasible(scenario, initiative, analyser)
        return _ordinary_response(
            request=request,
            source=source,
            scenario=scenario,
            perturbation=perturbation,
            status=SolverStatus.INFEASIBLE,
            stage1_status=stage1_status,
            stage1_stats=stage1_solver_stats,
            stage2_status=None,
            stage2_stats=None,
            minimum_changes=None,
            minimum_proven=False,
            secondary_optimal=False,
            new_result=None,
            blockers=blockers,
            role_diffs=[],
            preserved=None,
            changed=None,
            explanation="The perturbation leaves no feasible replacement assignment.",
        )

    # Only CP-SAT OPTIMAL proves the scalar.  Cross-check the rounded solver
    # objective against selected variable values before allowing Stage 2.
    if stage1_status is not SolverStatus.OPTIMAL:  # defensive for future statuses
        return _unknown_response(
            request=request,
            source=source,
            scenario=scenario,
            perturbation=perturbation,
            stage1_status=stage1_status,
            stage1_stats=stage1_solver_stats,
            explanation="Stage 1 returned no proof; replacement analysis is UNKNOWN.",
        )
    minimum_changes = integral_objective_value(cp_stage1)
    if minimum_changes is None or minimum_changes < 0:
        raise AnalyserContractError("Stage 1 returned no integral change objective")
    selected_changes = _selected_change_count(
        stage1_compiled,
        cp_stage1,
        baseline_by_role,
    )
    if minimum_changes != selected_changes:
        raise AnalyserContractError(
            "Stage 1 objective does not match selected assignment variables"
        )

    # Stage 2 rebuilds the strict model from scratch, fixes the proven scalar,
    # and installs exactly the compiler's exported planning-burden objective.
    stage2_compiled = compile_initiative(
        scenario,
        initiative,
        objective_mode="burden",
    )
    stage2_changes = _change_expression(stage2_compiled, baseline_by_role)
    stage2_compiled.model.Add(stage2_changes == minimum_changes)
    cp_stage2 = stage2_solver
    if cp_stage2 is not None:
        # solve_compiled owns its normal solver configuration.  Preconfiguring
        # an injected solver keeps the one-worker deterministic seam explicit.
        configure_solver(
            cp_stage2,
            time_limit_seconds=time_limit_seconds,
            num_search_workers=1,
            random_seed=random_seed,
        )
    stage2_result = solve_compiled(
        stage2_compiled,
        time_limit_seconds=time_limit_seconds,
        num_search_workers=1,
        random_seed=random_seed,
        solver=cp_stage2,
    )
    stage2_status = _status(stage2_result)
    stage2_solver_stats = stage2_result.solver_stats

    if stage2_status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        blockers = (
            _blockers_if_infeasible(scenario, initiative, analyser)
            if stage2_status is SolverStatus.INFEASIBLE
            else []
        )
        explanation = (
            "The perturbation has a proven change bound, but no replacement witness was returned."
            if stage2_status is SolverStatus.INFEASIBLE
            else "Stage 2 returned UNKNOWN; no replacement witness was returned."
        )
        return _ordinary_response(
            request=request,
            source=source,
            scenario=scenario,
            perturbation=perturbation,
            status=stage2_status,
            stage1_status=stage1_status,
            stage1_stats=stage1_solver_stats,
            stage2_status=stage2_status,
            stage2_stats=stage2_solver_stats,
            minimum_changes=minimum_changes,
            minimum_proven=True,
            secondary_optimal=False,
            new_result=None,
            blockers=blockers,
            role_diffs=[],
            preserved=None,
            changed=None,
            explanation=explanation,
        )

    if not isinstance(stage2_result, InitiativeAnalysisResult):
        raise AnalyserContractError(
            "Stage 2 solver must return InitiativeAnalysisResult"
        )
    if not validate_analysis_witness(scenario, initiative, stage2_result):
        raise AnalyserContractError("Stage 2 result failed canonical replay")
    final_by_role = _baseline_assignment_by_role(stage2_result)
    final_changes = sum(
        final_by_role[role.id] != baseline_by_role[role.id]
        for role in initiative.roles
    )
    if final_changes != minimum_changes:
        raise AnalyserContractError(
            "Stage 2 witness does not satisfy the proven assignment-change equality"
        )

    role_diffs = [
        RecompileRoleDiff(
            role_id=role.id,
            before_person_id=baseline_by_role[role.id],
            after_person_id=final_by_role[role.id],
            changed=baseline_by_role[role.id] != final_by_role[role.id],
        )
        for role in initiative.roles
    ]
    changed_count = sum(item.changed for item in role_diffs)
    return _ordinary_response(
        request=request,
        source=source,
        scenario=scenario,
        perturbation=perturbation,
        status=stage2_status,
        stage1_status=stage1_status,
        stage1_stats=stage1_solver_stats,
        stage2_status=stage2_status,
        stage2_stats=stage2_solver_stats,
        minimum_changes=minimum_changes,
        minimum_proven=True,
        secondary_optimal=stage2_status is SolverStatus.OPTIMAL,
        new_result=stage2_result,
        blockers=[],
        role_diffs=role_diffs,
        preserved=len(role_diffs) - changed_count,
        changed=changed_count,
        explanation=(
            "Replacement uses the proven minimum assignment changes and the canonical planning burden."
        ),
    )


__all__ = [
    "BaselineNotFeasible",
    "InvalidPerturbation",
    "PerturbationCatalogueTooLarge",
    "recompile_minimum_disruption",
]
