from __future__ import annotations

import pytest

from app.api_models import SolverStatus
from app.errors import AnalyserContractError
from app.fixture import load_demo_fixture
from app.project_models import CreateProjectRequest
from app.projects import CommunityStateMismatch, ProjectPlanNotFeasible, create_project_from_plan
from app.solver import solve_initiative


def _request(initiative_id: str, path: list[str]) -> CreateProjectRequest:
    return CreateProjectRequest(
        base_community=load_demo_fixture().community.model_copy(deep=True),
        initiative_id=initiative_id,
        catalyst_path=path,
        title="Saturday community digital support",
        short_description="A solver-verified community service assembled from shared local capacity.",
        objective="Deliver accessible digital help with every operational dependency verified.",
    )


def _initiative(initiative_id: str):
    return next(item for item in load_demo_fixture().initiatives if item.id == initiative_id)


def _create(request: CreateProjectRequest):
    fixture = load_demo_fixture()
    return create_project_from_plan(
        request,
        _initiative(request.initiative_id),
        fixture.actions,
        fixture.community,
    )


def test_already_feasible_base_state_creates_project_with_empty_path() -> None:
    fixture = load_demo_fixture()
    result = _create(_request("BASIC_WORKSHOP", []))

    assert result.verification.status == "OPTIMAL"
    assert result.project.status == "READY"
    assert result.project.catalyst_path == []
    assert result.project.catalyst_outputs == []
    assert result.project.base_state_id == result.project.verified_state_id == "S0"
    assert result.project.venue.venue_id == "LIBRARY_ROOM"
    assert result.project.host_organisation_id == "LOCAL_LIBRARY"
    assert result.project.host_organisation_name == "Local Library"
    assert result.project.host_organisation_id == result.project.venue.organisation_id
    assert result.project.schedule.occupied_slots == ["SAT_11", "SAT_12"]
    assert {item.person_id for item in result.project.operational_assignments} == {"LEO", "SAM"}
    assert result.project.resources[0].quantity_required == 4
    assert result.project.readiness.missing == []
    assert result.project.created_at == result.project.updated_at


def test_successor_path_is_replayed_and_project_uses_real_solver_witness() -> None:
    fixture = load_demo_fixture()
    result = _create(_request("MULTILINGUAL_CLINIC", ["TRAIN_DIGITAL_HELPERS"]))

    assert result.verification.status == "OPTIMAL"
    assert result.project.status == "READY"
    assert result.project.base_state_id == "S0"
    assert result.project.verified_state_id != "S0"
    assert result.project.catalyst_path == ["TRAIN_DIGITAL_HELPERS"]
    assert result.project.catalyst_outputs[0].diff.added_capabilities == {
        "PRIYA": ["digital_support"],
        "SAM": ["digital_support"],
    }
    assert len(result.project.operational_assignments) == 4
    assert result.project.supported_languages == ["ar", "en"]
    assignments = {item.role_id: item for item in result.project.operational_assignments}
    assert assignments["DIGITAL_HELPER_1"].person_languages == ["en"]
    assert assignments["DIGITAL_HELPER_2"].person_languages == ["en"]
    assert assignments["DIGITAL_HELPER_3"].person_languages == ["en"]
    assert assignments["ARABIC_SUPPORT"].person_languages == ["ar", "en"]
    assert assignments["ARABIC_SUPPORT"].matched_languages == ["ar"]
    assert result.project.accessibility_requirements == ["wheelchair_accessible"]
    assert result.project.host_organisation_id == "LOCAL_LIBRARY"
    assert result.project.host_organisation_id == result.project.venue.organisation_id
    assert all(check.ready for check in result.project.readiness.checks)


@pytest.mark.parametrize(
    ("initiative_id", "path"),
    [
        ("MULTILINGUAL_CLINIC", []),
        ("REPAIR_SHARE", []),
        ("MULTILINGUAL_CLINIC", ["BORROW_TWO_LAPTOPS"]),
    ],
)
def test_nonfeasible_or_wrong_plan_emits_no_project(initiative_id: str, path: list[str]) -> None:
    fixture = load_demo_fixture()
    with pytest.raises(ProjectPlanNotFeasible):
        _create(_request(initiative_id, path))


def test_project_identity_is_stable_for_same_plan_and_metadata() -> None:
    fixture = load_demo_fixture()
    request = _request("BASIC_WORKSHOP", [])
    first = _create(request)
    second = _create(request)
    assert first.project.id == second.project.id
    assert first.project.source_plan_id == second.project.source_plan_id


def test_metadata_changes_project_identity_but_not_source_plan_identity() -> None:
    first_request = _request("BASIC_WORKSHOP", [])
    second_request = _request("BASIC_WORKSHOP", [])
    second_request.title = "A different public project title"
    first = _create(first_request)
    second = _create(second_request)
    assert first.project.id != second.project.id
    assert first.project.source_plan_id == second.project.source_plan_id


def test_authoritative_path_change_changes_source_plan_identity() -> None:
    baseline = _create(_request("BASIC_WORKSHOP", []))
    successor = _create(_request("BASIC_WORKSHOP", ["BORROW_TWO_LAPTOPS"]))
    assert baseline.verification.status == successor.verification.status == "OPTIMAL"
    assert baseline.project.source_plan_id != successor.project.source_plan_id


def test_project_creation_rejects_changed_content_with_same_state_label() -> None:
    changed = _request("BASIC_WORKSHOP", [])
    changed.base_community.resources[0].quantity += 1
    assert changed.base_community.state_id == "S0"
    with pytest.raises(CommunityStateMismatch):
        _create(changed)


def test_duplicate_path_is_rejected_before_replay() -> None:
    fixture = load_demo_fixture()
    with pytest.raises(ValueError, match="duplicate"):
        _create(_request("MULTILINGUAL_CLINIC", ["TRAIN_DIGITAL_HELPERS", "TRAIN_DIGITAL_HELPERS"]))


def test_project_creation_emits_no_project_for_invalid_feasible_witness(monkeypatch) -> None:
    fixture = load_demo_fixture()
    initiative = _initiative("BASIC_WORKSHOP")
    invalid = solve_initiative(fixture.community, initiative).model_copy(deep=True)
    assert invalid.status is SolverStatus.OPTIMAL
    invalid.objective_value = 999
    monkeypatch.setattr("app.projects.solve_initiative", lambda *_: invalid)

    with pytest.raises(AnalyserContractError):
        _create(_request("BASIC_WORKSHOP", []))
