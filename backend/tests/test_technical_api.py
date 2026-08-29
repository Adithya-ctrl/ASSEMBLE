from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api_models import (
    CapabilityFrontierResponse,
    ErrorResponse,
    RecompileResponse,
    SolverStatus,
    StressTestResponse,
)
from app.errors import AnalyserContractError
from app.fixture import fresh_demo_fixture
from app.frontier import _scenario_receipt
from app.interventions import apply_action, canonical_state_hash
from app.main import app
from app.resilience import PerturbationCatalogueTooLarge, apply_canonical_perturbation


CLIENT = TestClient(app)
ROOT = Path(__file__).parents[2]


def _community() -> dict[str, object]:
    return fresh_demo_fixture().community.model_dump(mode="json")


def _assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    parsed = ErrorResponse.model_validate(response.json())
    assert parsed.error.code == code


def _stress_payload(
    initiative_id: str,
    catalyst_path: list[str] | None = None,
) -> dict[str, object]:
    return {
        "base_community": _community(),
        "initiative_id": initiative_id,
        "catalyst_path": catalyst_path or [],
    }


def test_stress_api_serializes_exact_basic_and_clinic_boss_fights() -> None:
    basic_http = CLIENT.post(
        "/api/stress-test",
        json=_stress_payload("BASIC_WORKSHOP"),
    )
    assert basic_http.status_code == 200
    basic = StressTestResponse.model_validate(basic_http.json())
    assert (basic.catalogue_size, basic.decisive_count) == (4, 4)
    assert (basic.survived_count, basic.failed_count, basic.unknown_count) == (0, 4, 0)
    assert basic.resilience_ratio == 0
    assert all(item.status is SolverStatus.INFEASIBLE for item in basic.outcomes)

    clinic_http = CLIENT.post(
        "/api/stress-test",
        json=_stress_payload(
            "MULTILINGUAL_CLINIC",
            ["TRAIN_DIGITAL_HELPERS"],
        ),
    )
    assert clinic_http.status_code == 200
    clinic = StressTestResponse.model_validate(clinic_http.json())
    assert (clinic.catalogue_size, clinic.decisive_count) == (6, 6)
    assert (clinic.survived_count, clinic.failed_count, clinic.unknown_count) == (0, 6, 0)
    assert clinic.resilience_ratio == 0
    helper = next(
        outcome for outcome in clinic.outcomes if outcome.perturbation.target_id == "LEO"
    )
    assert any(
        (fact.required, fact.available, fact.capability, fact.relevant_ids)
        == (3, 2, "digital_support", ["PRIYA", "SAM"])
        for requirement_set in helper.blockers
        for fact in requirement_set.facts
    )


def test_stress_api_receipts_recompute_from_exact_source_spec_and_scenario() -> None:
    fixture = fresh_demo_fixture()
    response = StressTestResponse.model_validate(
        CLIENT.post(
            "/api/stress-test",
            json=_stress_payload("BASIC_WORKSHOP"),
        ).json()
    )
    initiative = next(
        item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP"
    )
    assert response.source_content_hash == canonical_state_hash(fixture.community)
    for outcome in response.outcomes:
        scenario = apply_canonical_perturbation(
            fixture.community,
            initiative,
            outcome.perturbation,
        )
        assert outcome.source_state_id == fixture.community.state_id
        assert outcome.scenario_state_id == scenario.scenario_state_id
        assert outcome.scenario_state_id.startswith("CF_STRESS_V1_")
        assert not outcome.scenario_state_id.startswith("S")


def test_recompile_api_returns_proven_one_change_recovery_and_normal_failure() -> None:
    stress = StressTestResponse.model_validate(
        CLIENT.post(
            "/api/stress-test",
            json=_stress_payload("BASIC_WORKSHOP", ["TRAIN_DIGITAL_HELPERS"]),
        ).json()
    )
    priya = next(
        outcome for outcome in stress.outcomes if outcome.perturbation.target_id == "PRIYA"
    )
    success_http = CLIENT.post(
        "/api/recompile",
        json={
            **_stress_payload("BASIC_WORKSHOP", ["TRAIN_DIGITAL_HELPERS"]),
            "perturbation_id": priya.perturbation_id,
        },
    )
    assert success_http.status_code == 200
    success = RecompileResponse.model_validate(success_http.json())
    assert success.status is SolverStatus.OPTIMAL
    assert success.stage1_status is SolverStatus.OPTIMAL
    assert success.stage2_status is SolverStatus.OPTIMAL
    assert success.minimum_proven is True
    assert success.minimum_assignment_changes == 1
    assert success.changed_assignments == 1
    assert success.preserved_assignments == 1
    assert success.new_result is not None
    assert success.new_result.objective_value == 24
    assert [(item.role_instance_id, item.person_id) for item in success.new_result.assignments] == [
        ("DIGITAL_HELPER", "LEO"),
        ("FACILITATOR", "SAM"),
    ]

    venue = next(
        outcome
        for outcome in stress.outcomes
        if outcome.perturbation.type.value == "MAKE_SELECTED_VENUE_UNAVAILABLE"
    )
    failure_http = CLIENT.post(
        "/api/recompile",
        json={
            **_stress_payload("BASIC_WORKSHOP", ["TRAIN_DIGITAL_HELPERS"]),
            "perturbation_id": venue.perturbation_id,
        },
    )
    assert failure_http.status_code == 200
    failure = RecompileResponse.model_validate(failure_http.json())
    assert failure.status is SolverStatus.INFEASIBLE
    assert failure.new_result is None
    assert failure.minimum_proven is False


def test_frontier_api_serializes_expected_fixture_and_counterfactual_receipts() -> None:
    fixture = fresh_demo_fixture()
    response_http = CLIENT.post(
        "/api/frontier",
        json={"base_community": _community(), "catalyst_path": []},
    )
    assert response_http.status_code == 200
    response = CapabilityFrontierResponse.model_validate(response_http.json())
    assert response.baseline_buildable_ids == ["BASIC_WORKSHOP"]
    assert response.highest_leverage_action_id == "TRAIN_DIGITAL_HELPERS"
    assert response.pareto_action_ids == [
        "TRAIN_DIGITAL_HELPERS",
        "BORROW_TWO_LAPTOPS",
    ]
    for action_result in response.action_results:
        assert action_result.applicable is True
        assert action_result.scenario_state_id is not None
        assert action_result.scenario_state_id.startswith("CF_FRONTIER_V1_")
        assert not action_result.scenario_state_id.startswith("S")
        action = next(item for item in fixture.actions if item.id == action_result.action_id)
        successor, diff = apply_action(fixture.community, action)
        expected_id, expected_hash = _scenario_receipt(
            fixture.community,
            action,
            successor,
        )
        assert action_result.scenario_state_id == expected_id
        assert action_result.scenario_content_hash == expected_hash
        assert action_result.produced_diff == diff

    trained_http = CLIENT.post(
        "/api/frontier",
        json={
            "base_community": _community(),
            "catalyst_path": ["TRAIN_DIGITAL_HELPERS"],
        },
    )
    assert trained_http.status_code == 200
    trained = CapabilityFrontierResponse.model_validate(trained_http.json())
    assert trained.highest_leverage_action_id is None
    assert next(
        item for item in trained.action_results if item.action_id == "TRAIN_DIGITAL_HELPERS"
    ).applicable is False


def test_technical_routes_reject_forged_base_unknown_path_and_client_truncation() -> None:
    forged = _community()
    forged["resources"][0]["quantity"] += 1  # type: ignore[index]
    for route, payload in (
        (
            "/api/stress-test",
            {
                "base_community": forged,
                "initiative_id": "BASIC_WORKSHOP",
                "catalyst_path": [],
            },
        ),
        (
            "/api/recompile",
            {
                "base_community": forged,
                "initiative_id": "BASIC_WORKSHOP",
                "catalyst_path": [],
                "perturbation_id": "FORGED",
            },
        ),
        (
            "/api/frontier",
            {"base_community": forged, "catalyst_path": []},
        ),
    ):
        _assert_error(CLIENT.post(route, json=payload), 409, "COMMUNITY_STATE_MISMATCH")

    _assert_error(
        CLIENT.post(
            "/api/frontier",
            json={"base_community": _community(), "catalyst_path": ["UNKNOWN_ACTION"]},
        ),
        404,
        "INVALID_REFERENCE",
    )
    _assert_error(
        CLIENT.post(
            "/api/stress-test",
            json={**_stress_payload("BASIC_WORKSHOP"), "max_perturbations": 1},
        ),
        422,
        "INVALID_REQUEST",
    )


def test_recompile_invalid_perturbation_and_baseline_precondition_have_stable_errors() -> None:
    _assert_error(
        CLIENT.post(
            "/api/recompile",
            json={
                **_stress_payload("BASIC_WORKSHOP"),
                "perturbation_id": "ASSEMBLE_STRESS_PERTURBATION_V1_FORGED",
            },
        ),
        404,
        "INVALID_PERTURBATION",
    )
    _assert_error(
        CLIENT.post(
            "/api/stress-test",
            json=_stress_payload("REPAIR_SHARE"),
        ),
        409,
        "BASELINE_NOT_FEASIBLE",
    )


def test_catalogue_overflow_and_analyser_contract_fail_closed_at_api(monkeypatch) -> None:
    def overflow(*_args, **_kwargs):
        raise PerturbationCatalogueTooLarge(21)

    monkeypatch.setattr("app.main.run_stress_test", overflow)
    _assert_error(
        CLIENT.post(
            "/api/stress-test",
            json=_stress_payload("BASIC_WORKSHOP"),
        ),
        422,
        "PERTURBATION_CATALOGUE_TOO_LARGE",
    )

    def bad_analyser(*_args, **_kwargs):
        raise AnalyserContractError("mutated analyser input")

    monkeypatch.setattr("app.main.run_stress_test", bad_analyser)
    _assert_error(
        CLIENT.post(
            "/api/stress-test",
            json=_stress_payload("BASIC_WORKSHOP"),
        ),
        500,
        "ANALYSER_CONTRACT_ERROR",
    )


def test_openapi_exposes_all_three_m7_routes_with_response_models() -> None:
    openapi = app.openapi()
    for route in ("/api/stress-test", "/api/recompile", "/api/frontier"):
        assert route in openapi["paths"]
        assert "post" in openapi["paths"][route]
        assert "200" in openapi["paths"][route]["post"]["responses"]


def test_technical_contract_reference_and_adr_match_public_routes_and_bounds() -> None:
    contract = (ROOT / "contracts" / "technical-differentiation-api.md").read_text(
        encoding="utf-8"
    )
    reference = (ROOT / "docs" / "reference" / "technical-differentiation.md").read_text(
        encoding="utf-8"
    )
    adr = (
        ROOT / "docs" / "adr" / "0007-structural-resilience-and-recompilation.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join((contract, reference, adr))
    normalized_contract = " ".join(contract.split())
    normalized_reference = " ".join(reference.split())
    for route in ("/api/stress-test", "/api/recompile", "/api/frontier"):
        assert route in contract
        assert route in reference
    for perturbation in (
        "MAKE_ASSIGNED_PERSON_UNAVAILABLE",
        "MAKE_SELECTED_VENUE_UNAVAILABLE",
        "REDUCE_AVAILABLE_RESOURCE",
    ):
        assert perturbation in combined
    for ceiling in ("at most 601", "at most 32 calls", "at most 1056"):
        assert ceiling in normalized_contract
        assert ceiling in normalized_reference
    assert (
        "No-applicable-actions and zero-unlock outcomes are ordinary HTTP 200 analyses."
        in normalized_contract
    )
    assert "Stage 1 never exposes an initiative witness" in " ".join(adr.split())
