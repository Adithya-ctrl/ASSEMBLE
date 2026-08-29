"""Strict request and Project metadata boundary matrices.

The request models are tested without HTTP or solver calls so that malformed
payloads are proven to fail before route dispatch or expensive reasoning.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.api_models import (
    AnalyseRequest,
    CapabilityFrontierRequest,
    ExplainRequest,
    PlanRequest,
    RecompileRequest,
    StressTestRequest,
    TransitionRequest,
    UnlockRequest,
)
from app.fixture import fresh_demo_fixture
from app.project_models import CreateProjectRequest


def _community() -> dict[str, object]:
    return fresh_demo_fixture().community.model_dump(mode="json")


def _actions(count: int) -> list[dict[str, object]]:
    template = fresh_demo_fixture().actions[0].model_dump(mode="json")
    actions: list[dict[str, object]] = []
    for index in range(count):
        action = deepcopy(template)
        action["id"] = f"ACTION_{index:03d}"
        actions.append(action)
    return actions


def _analyse_payload(*, initiative_ids: object = None) -> dict[str, object]:
    return {
        "community": _community(),
        "initiative_ids": ["BASIC_WORKSHOP"] if initiative_ids is None else initiative_ids,
    }


def _explain_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "community": _community(),
        "initiative_id": "BASIC_WORKSHOP",
    }
    payload.update(overrides)
    return payload


def _unlock_payload(*, actions: object = None, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "community": _community(),
        "initiative_id": "MULTILINGUAL_CLINIC",
        "actions": _actions(1) if actions is None else actions,
    }
    payload.update(overrides)
    return payload


def _plan_payload(*, actions: object = None, **overrides: object) -> dict[str, object]:
    payload = _unlock_payload(actions=_actions(1) if actions is None else actions)
    payload.update(overrides)
    return payload


def _transition_payload(*, actions: object = None, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "community": _community(),
        "action_id": "ACTION_000",
        "actions": _actions(1) if actions is None else actions,
    }
    payload.update(overrides)
    return payload


REQUEST_ACTION_MODELS = (
    ("unlock", UnlockRequest, _unlock_payload),
    ("plan", PlanRequest, _plan_payload),
    ("transition", TransitionRequest, _transition_payload),
)


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    REQUEST_ACTION_MODELS,
    ids=("unlock-actions", "plan-actions", "transition-actions"),
)
@pytest.mark.parametrize("size", (0, 1, 32, 33), ids=("empty", "min", "max", "over-max"))
def test_core_request_action_collection_ceiling_matrix(
    label: str, model_type, payload_factory, size: int
) -> None:
    del label
    payload = payload_factory(actions=_actions(size))
    if size in (0, 33):
        with pytest.raises(ValidationError):
            model_type.model_validate(payload)
    else:
        model_type.model_validate(payload)


@pytest.mark.parametrize("size", (0, 1, 32, 33), ids=("empty", "min", "max", "over-max"))
def test_analyse_requested_initiative_collection_ceiling_matrix(size: int) -> None:
    ids = [f"INITIATIVE_{index:03d}" for index in range(size)]
    payload = _analyse_payload(initiative_ids=ids)
    if size in (0, 33):
        with pytest.raises(ValidationError):
            AnalyseRequest.model_validate(payload)
    else:
        AnalyseRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("model_type", "payload_factory", "field"),
    [
        (AnalyseRequest, _analyse_payload, "initiative_ids"),
        (ExplainRequest, _explain_payload, "initiative_id"),
        (UnlockRequest, _unlock_payload, "initiative_id"),
        (PlanRequest, _plan_payload, "initiative_id"),
        (TransitionRequest, _transition_payload, "action_id"),
    ],
    ids=("analyse", "explain", "unlock", "plan", "transition"),
)
@pytest.mark.parametrize(
    "value",
    (None, 1, True, "bad-id", "A-B", "a"),
    ids=lambda value: f"invalid-{value!r}",
)
def test_core_request_id_fields_reject_wrong_primitives_and_id_shapes(
    model_type, payload_factory, field: str, value: object
) -> None:
    payload = payload_factory()
    if field == "initiative_ids":
        payload[field] = [value]
    else:
        payload[field] = value
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    REQUEST_ACTION_MODELS,
    ids=("unlock", "plan", "transition"),
)
@pytest.mark.parametrize(
    "actions",
    (None, {}, {"id": "ACTION"}, "ACTION", [None], [1]),
    ids=lambda value: f"invalid-actions-{value!r}",
)
def test_core_request_action_fields_reject_non_array_or_malformed_entries(
    label: str, model_type, payload_factory, actions: object
) -> None:
    del label
    payload = payload_factory()
    payload["actions"] = actions
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


@pytest.mark.parametrize("value", (0, 1, 3, "2", 2.0, True), ids=lambda value: f"depth-{value!r}")
def test_plan_depth_is_exactly_the_declared_literal_two(value: object) -> None:
    with pytest.raises(ValidationError):
        PlanRequest.model_validate(_plan_payload(max_depth=value))


@pytest.mark.parametrize(
    "value", (0, 21, "20", 20.0, True), ids=lambda value: f"expanded-{value!r}"
)
def test_plan_expanded_state_bound_is_strict_integer_one_to_twenty(value: object) -> None:
    with pytest.raises(ValidationError):
        PlanRequest.model_validate(_plan_payload(max_expanded_states=value))


def test_plan_default_expansion_bound_is_explicit_and_valid() -> None:
    request = PlanRequest.model_validate(_plan_payload())
    assert request.max_depth == 2
    assert request.max_expanded_states == 20


@pytest.mark.parametrize(
    ("model_type", "payload_factory"),
    [
        (AnalyseRequest, _analyse_payload),
        (ExplainRequest, _explain_payload),
        (UnlockRequest, _unlock_payload),
        (PlanRequest, _plan_payload),
        (TransitionRequest, _transition_payload),
    ],
    ids=("analyse", "explain", "unlock", "plan", "transition"),
)
def test_core_requests_forbid_unknown_proof_or_catalogue_fields(model_type, payload_factory) -> None:
    payload = payload_factory()
    payload["objective_value"] = 999
    payload["assignments"] = []
    payload["witness"] = {"status": "OPTIMAL"}
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


def _project_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "base_community": _community(),
        "initiative_id": "BASIC_WORKSHOP",
        "catalyst_path": [],
        "title": "abc",
        "short_description": "x" * 20,
        "objective": "y" * 20,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("length", "expected_valid"),
    [(2, False), (3, True), (4, True), (99, True), (100, True), (101, False)],
    ids=("min-minus-one", "min", "min-plus-one", "max-minus-one", "max", "max-plus-one"),
)
def test_project_title_length_matrix(length: int, expected_valid: bool) -> None:
    payload = _project_payload(title="t" * length)
    if expected_valid:
        assert CreateProjectRequest.model_validate(payload).title == "t" * length
    else:
        with pytest.raises(ValidationError):
            CreateProjectRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field", ("short_description", "objective"), ids=("description", "objective")
)
@pytest.mark.parametrize(
    ("length", "expected_valid"),
    [(19, False), (20, True), (21, True), (279, True), (280, True), (281, False)],
    ids=("min-minus-one", "min", "min-plus-one", "max-minus-one", "max", "max-plus-one"),
)
def test_project_long_text_length_matrix(field: str, length: int, expected_valid: bool) -> None:
    payload = _project_payload(**{field: "x" * length})
    if expected_valid:
        assert getattr(CreateProjectRequest.model_validate(payload), field) == "x" * length
    else:
        with pytest.raises(ValidationError):
            CreateProjectRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field", ("title", "short_description", "objective"), ids=("title", "description", "objective")
)
def test_project_metadata_rejects_whitespace_only_after_normalization(field: str) -> None:
    minimum = 3 if field == "title" else 20
    payload = _project_payload(**{field: " " * minimum})
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(payload)


def test_project_metadata_trims_surrounding_whitespace_before_validation_and_storage() -> None:
    request = CreateProjectRequest.model_validate(
        _project_payload(
            title="\tabc\n",
            short_description="  " + "x" * 20 + "  ",
            objective="\n" + "y" * 20 + "\t",
        )
    )
    assert request.title == "abc"
    assert request.short_description == "x" * 20
    assert request.objective == "y" * 20


@pytest.mark.parametrize(
    "value",
    (None, 1, 1.0, True, [], {}),
    ids=lambda value: f"wrong-metadata-{value!r}",
)
@pytest.mark.parametrize(
    "field", ("title", "short_description", "objective"), ids=("title", "description", "objective")
)
def test_project_metadata_rejects_wrong_primitives(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(_project_payload(**{field: value}))


@pytest.mark.parametrize(
    "value",
    (
        "Saturday 🛠️",
        "RTL \u05d0\u05d1\u05d2",
        "Combining e\u0301",
        "<script>alert(1)</script>" + "x" * 20,
        "<img onerror=alert(1)>" + "x" * 20,
        "DROP TABLE projects;" + "x" * 20,
        "long_unbroken_" + "x" * 260,
    ),
    ids=("emoji", "rtl", "combining", "script", "img-handler", "sql-ish", "unbroken"),
)
def test_project_text_is_bounded_plain_text_and_not_silently_rewritten(value: str) -> None:
    expected = value if len(value) >= 20 else value + "x" * 20
    request = CreateProjectRequest.model_validate(
        _project_payload(
            title="abc",
            short_description=expected,
            objective=expected,
        )
    )
    assert request.short_description == expected
    assert request.objective == expected


@pytest.mark.parametrize(
    "path", ([], ["A"], ["A", "B"], ["A", "B", "C"]), ids=("empty", "one", "two", "three")
)
def test_project_catalyst_path_is_explicitly_bounded_to_zero_through_two(path: list[str]) -> None:
    payload = _project_payload(catalyst_path=path)
    if len(path) > 2:
        with pytest.raises(ValidationError):
            CreateProjectRequest.model_validate(payload)
    else:
        assert CreateProjectRequest.model_validate(payload).catalyst_path == path


@pytest.mark.parametrize("path", (None, {"id": "A"}, [None], ["a-b"]), ids=lambda value: f"invalid-path-{value!r}")
def test_project_catalyst_path_rejects_non_array_or_malformed_ids(path: object) -> None:
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(_project_payload(catalyst_path=path))


def test_project_model_leaves_syntactically_valid_unknown_action_for_domain_resolution() -> None:
    request = CreateProjectRequest.model_validate(_project_payload(catalyst_path=["A"]))
    assert request.catalyst_path == ["A"]


def test_project_request_forbids_client_supplied_derived_proof_fields() -> None:
    payload = _project_payload(
        status="READY",
        readiness={"status": "READY"},
        assignments=[],
        venue={"venue_id": "FORGED"},
        source_plan_id="FORGED_PLAN",
        verification={"status": "OPTIMAL"},
    )
    with pytest.raises(ValidationError):
        CreateProjectRequest.model_validate(payload)


M7_REQUESTS = (
    ("stress", StressTestRequest, lambda path: {
        "base_community": _community(),
        "initiative_id": "BASIC_WORKSHOP",
        "catalyst_path": path,
    }),
    ("recompile", RecompileRequest, lambda path: {
        "base_community": _community(),
        "initiative_id": "BASIC_WORKSHOP",
        "catalyst_path": path,
        "perturbation_id": "PERTURBATION",
    }),
    ("frontier", CapabilityFrontierRequest, lambda path: {
        "base_community": _community(),
        "catalyst_path": path,
    }),
)


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    M7_REQUESTS,
    ids=("stress", "recompile", "frontier"),
)
@pytest.mark.parametrize("size", (0, 1, 2), ids=("empty", "one", "two"))
def test_m7_catalyst_path_matrix_accepts_zero_one_or_two_ids(
    label: str, model_type, payload_factory, size: int
) -> None:
    del label
    path = [f"ACTION_{index:03d}" for index in range(size)]
    request = model_type.model_validate(payload_factory(path))
    assert request.catalyst_path == path


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    M7_REQUESTS,
    ids=("stress", "recompile", "frontier"),
)
def test_m7_catalyst_path_rejects_overflow_and_duplicate_ids(
    label: str, model_type, payload_factory
) -> None:
    del label
    with pytest.raises(ValidationError):
        model_type.model_validate(payload_factory(["ACTION_000", "ACTION_001", "ACTION_002"]))
    with pytest.raises(ValidationError, match="duplicate"):
        model_type.model_validate(payload_factory(["ACTION_000", "ACTION_000"]))


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    M7_REQUESTS,
    ids=("stress", "recompile", "frontier"),
)
@pytest.mark.parametrize(
    "path", (None, {}, [None], [1], ["a-b"]), ids=lambda value: f"invalid-{value!r}"
)
def test_m7_catalyst_path_rejects_wrong_primitives_and_malformed_ids(
    label: str, model_type, payload_factory, path: object
) -> None:
    del label
    with pytest.raises(ValidationError):
        model_type.model_validate(payload_factory(path))


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    M7_REQUESTS,
    ids=("stress", "recompile", "frontier"),
)
def test_m7_models_leave_syntactically_valid_unknown_actions_for_domain_resolution(
    label: str, model_type, payload_factory
) -> None:
    del label
    request = model_type.model_validate(payload_factory(["ACTION_000"]))
    assert request.catalyst_path == ["ACTION_000"]


@pytest.mark.parametrize(
    ("label", "model_type", "payload_factory"),
    M7_REQUESTS,
    ids=("stress", "recompile", "frontier"),
)
def test_m7_requests_forbid_client_analysis_inputs(
    label: str, model_type, payload_factory
) -> None:
    del label
    payload = payload_factory([])
    payload.update(
        {
            "actions": _actions(1),
            "perturbation": {"type": "REDUCE_AVAILABLE_RESOURCE"},
            "scenario_state": {"state_id": "S_FORGED"},
            "objective_value": 999,
            "assignments": [],
            "max_perturbations": 1,
        }
    )
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


def test_m7_stress_request_defaults_to_empty_catalyst_path() -> None:
    payload = _community()
    request = StressTestRequest.model_validate(
        {"base_community": payload, "initiative_id": "BASIC_WORKSHOP"}
    )
    assert request.catalyst_path == []
