from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import compiler as compiler_module
from app.api_models import (
    AnalyseRequest,
    AnalyseResponse,
    ErrorResponse,
    ExplainRequest,
    ExplainResponse,
    InitiativeAnalysisResult,
    PlanRequest,
    PlanResponse,
    TransitionRequest,
    TransitionResponse,
    UnlockRequest,
    UnlockResponse,
)
from app.fixture import load_demo_fixture
from app.errors import AnalyserContractError
from app.main import app
from app.project_models import CreateProjectResponse
from app.solver import replay_assignment


ROOT = Path(__file__).parents[2]
EXAMPLES = json.loads((ROOT / "contracts/examples/api_examples.json").read_text(encoding="utf-8"))


def _community() -> dict[str, object]:
    return load_demo_fixture().community.model_dump(mode="json")


def _actions() -> list[dict[str, object]]:
    return [action.model_dump(mode="json") for action in load_demo_fixture().actions]


def _assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    parsed = ErrorResponse.model_validate(response.json())
    assert parsed.error.code == code


def _project_payload(initiative_id: str, catalyst_path: list[str]) -> dict[str, object]:
    return {
        "base_community": _community(),
        "initiative_id": initiative_id,
        "catalyst_path": catalyst_path,
        "title": "Saturday community digital support",
        "short_description": "A solver-verified community service assembled from shared local capacity.",
        "objective": "Deliver accessible digital help with every operational dependency verified.",
    }


def test_request_examples_validate_against_fixture() -> None:
    requests = EXAMPLES["requests"]
    AnalyseRequest.model_validate({"community": _community(), **requests["analyse"]})
    ExplainRequest.model_validate({"community": _community(), **requests["explain"]})
    UnlockRequest.model_validate({"community": _community(), "actions": _actions(), **requests["unlock"]})
    PlanRequest.model_validate({"community": _community(), "actions": _actions(), **requests["plan"]})
    TransitionRequest.model_validate({"community": _community(), "actions": _actions(), **requests["transition"]})


def test_response_examples_validate() -> None:
    responses = EXAMPLES["responses"]
    AnalyseResponse.model_validate(responses["analyse"])
    ExplainResponse.model_validate(responses["explain"])
    UnlockResponse.model_validate(responses["unlock"])
    PlanResponse.model_validate(responses["plan"])
    ErrorResponse.model_validate(responses["error"])


@pytest.mark.parametrize("status", ["INFEASIBLE", "UNKNOWN"])
@pytest.mark.parametrize("unsafe_field", ["objective_value", "assignments", "assembly_trace"])
def test_nonfeasible_status_rejects_objective_and_witness(status: str, unsafe_field: str) -> None:
    payload = deepcopy(EXAMPLES["responses"]["analyse"]["results"][1])
    payload["status"] = status
    if unsafe_field == "objective_value":
        payload[unsafe_field] = 1
    elif unsafe_field == "assignments":
        payload[unsafe_field] = [{"role_instance_id": "DIGITAL_HELPER", "person_id": "LEO"}]
    else:
        payload[unsafe_field] = [{
            "requirement_kind": "role",
            "requirement_id": "DIGITAL_HELPER",
            "selected_ids": ["LEO"],
            "facts": {},
        }]
    with pytest.raises(ValidationError, match="must not contain"):
        InitiativeAnalysisResult.model_validate(payload)


@pytest.mark.parametrize("missing_field", ["objective_value", "assignments", "assembly_trace"])
def test_feasible_status_requires_objective_and_complete_witness(missing_field: str) -> None:
    payload = deepcopy(EXAMPLES["responses"]["analyse"]["results"][0])
    payload["status"] = "FEASIBLE"
    payload[missing_field] = None if missing_field == "objective_value" else []
    with pytest.raises(ValidationError, match="require"):
        InitiativeAnalysisResult.model_validate(payload)


def test_transition_example_validates_with_immutable_successor() -> None:
    predecessor = load_demo_fixture().community
    successor_payload = deepcopy(predecessor.model_dump(mode="json"))
    successor_payload["state_id"] = "S1"
    successor_payload["parent_state_id"] = "S0"
    people = {person["id"]: person for person in successor_payload["people"]}
    people["PRIYA"]["capabilities"].append("digital_support")
    people["SAM"]["capabilities"].append("digital_support")
    parsed = TransitionResponse.model_validate({
        **EXAMPLES["responses"]["transition_overlay"],
        "successor_state": successor_payload,
    })
    assert parsed.predecessor_state_id == "S0"
    assert "digital_support" not in predecessor.people[1].capabilities


def test_health_demo_and_cors() -> None:
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok", "solver": "ortools-cp-sat"}
    demo = client.get("/api/demo")
    assert demo.status_code == 200
    assert demo.json()["fixture_version"] == "assemble-demo-v1"

    preflight = client.options(
        "/api/analyse",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_analyse_uses_real_solver_counts_and_replayable_witness() -> None:
    fixture = load_demo_fixture()
    response = TestClient(app).post(
        "/api/analyse",
        json={
            "community": _community(),
            "initiative_ids": ["BASIC_WORKSHOP", "MULTILINGUAL_CLINIC", "REPAIR_SHARE"],
        },
    )
    assert response.status_code == 200
    parsed = AnalyseResponse.model_validate(response.json())
    assert (parsed.compile.decision_variables, parsed.compile.hard_constraints) == (20, 30)
    results = {result.initiative_id: result for result in parsed.results}
    assert (results["BASIC_WORKSHOP"].status, results["BASIC_WORKSHOP"].objective_value) == ("OPTIMAL", 24)
    assert results["MULTILINGUAL_CLINIC"].status == "INFEASIBLE"
    assert results["REPAIR_SHARE"].status == "INFEASIBLE"
    basic = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    assert replay_assignment(fixture.community, basic, results["BASIC_WORKSHOP"])


def test_analyse_compiles_each_requested_initiative_exactly_once(monkeypatch) -> None:
    compiled_ids: list[str] = []
    original = compiler_module.compile_initiative

    def counting_compile(community, initiative, **kwargs):
        compiled_ids.append(initiative.id)
        return original(community, initiative, **kwargs)

    monkeypatch.setattr(compiler_module, "compile_initiative", counting_compile)
    response = TestClient(app).post(
        "/api/analyse",
        json={
            "community": _community(),
            "initiative_ids": ["BASIC_WORKSHOP", "MULTILINGUAL_CLINIC", "REPAIR_SHARE"],
        },
    )

    assert response.status_code == 200
    assert compiled_ids == ["BASIC_WORKSHOP", "MULTILINGUAL_CLINIC", "REPAIR_SHARE"]


def test_explain_reports_solver_confirmed_helper_shortage() -> None:
    response = TestClient(app).post(
        "/api/explain",
        json={"community": _community(), "initiative_id": "MULTILINGUAL_CLINIC"},
    )
    assert response.status_code == 200
    parsed = ExplainResponse.model_validate(response.json())
    assert parsed.status == "INFEASIBLE"
    helper_facts = [
        fact
        for requirement_set in parsed.blocking_requirement_sets
        if "role_capability" in requirement_set.groups
        for fact in requirement_set.facts
        if fact.capability == "digital_support"
    ]
    assert any((fact.required, fact.available) == (3, 1) for fact in helper_facts)
    assert all("resource_quantity" not in item.groups for item in parsed.blocking_requirement_sets)


def test_real_unlock_transition_plan_and_successor_verification_journey() -> None:
    client = TestClient(app)
    community = _community()
    actions = _actions()
    target = "MULTILINGUAL_CLINIC"

    unlock = client.post(
        "/api/unlock",
        json={"community": community, "initiative_id": target, "actions": actions},
    )
    assert unlock.status_code == 200
    unlock_result = UnlockResponse.model_validate(unlock.json())
    assert unlock_result.interventions == ["TRAIN_DIGITAL_HELPERS"]
    assert (unlock_result.total_cost, unlock_result.catalogue_size, unlock_result.candidate_paths_evaluated) == (2, 4, 16)

    plan = client.post(
        "/api/plan",
        json={
            "community": community,
            "initiative_id": target,
            "actions": actions,
            "max_depth": 2,
            "max_expanded_states": 20,
        },
    )
    assert plan.status_code == 200
    plan_result = PlanResponse.model_validate(plan.json())
    assert plan_result.path == ["TRAIN_DIGITAL_HELPERS"]
    assert (plan_result.target_status_before, plan_result.target_status_after) == ("INFEASIBLE", "OPTIMAL")

    transition = client.post(
        "/api/transition",
        json={"community": community, "action_id": "TRAIN_DIGITAL_HELPERS", "actions": actions},
    )
    assert transition.status_code == 200
    transition_result = TransitionResponse.model_validate(transition.json())
    assert transition_result.predecessor_state_id == "S0"
    assert transition_result.successor_state.parent_state_id == "S0"
    assert transition_result.diff.added_capabilities == {
        "PRIYA": ["digital_support"],
        "SAM": ["digital_support"],
    }
    assert "digital_support" not in load_demo_fixture().community.people[1].capabilities

    verified = client.post(
        "/api/analyse",
        json={
            "community": transition_result.successor_state.model_dump(mode="json"),
            "initiative_ids": [target],
        },
    )
    assert verified.status_code == 200
    verified_result = AnalyseResponse.model_validate(verified.json()).results[0]
    assert (verified_result.status, verified_result.objective_value) == ("OPTIMAL", 48)


def test_create_basic_project_from_real_base_state_proof() -> None:
    response = TestClient(app).post(
        "/api/projects/from-plan",
        json=_project_payload("BASIC_WORKSHOP", []),
    )
    assert response.status_code == 201
    parsed = CreateProjectResponse.model_validate(response.json())
    assert parsed.verification.status == "OPTIMAL"
    assert parsed.project.status == "READY"
    assert parsed.project.catalyst_path == []
    assert parsed.project.base_state_id == parsed.project.verified_state_id == "S0"
    assert parsed.project.host_organisation_id == parsed.project.venue.organisation_id
    assert "owner_organisation_id" not in response.json()["project"]


def test_create_clinic_project_replays_authoritative_action_and_verifies_successor() -> None:
    response = TestClient(app).post(
        "/api/projects/from-plan",
        json=_project_payload("MULTILINGUAL_CLINIC", ["TRAIN_DIGITAL_HELPERS"]),
    )
    assert response.status_code == 201
    parsed = CreateProjectResponse.model_validate(response.json())
    assert parsed.verification.status == "OPTIMAL"
    assert parsed.project.status == "READY"
    assert parsed.project.catalyst_path == ["TRAIN_DIGITAL_HELPERS"]
    assert parsed.project.verified_state_id != "S0"
    assert parsed.project.host_organisation_id == parsed.project.venue.organisation_id
    assert "owner_organisation_id" not in response.json()["project"]
    assert {item.person_id for item in parsed.project.operational_assignments} == {
        "LEO", "PRIYA", "SAM", "AMIRA"
    }


@pytest.mark.parametrize(
    ("initiative_id", "path"),
    [
        ("MULTILINGUAL_CLINIC", []),
        ("MULTILINGUAL_CLINIC", ["BORROW_TWO_LAPTOPS"]),
        ("REPAIR_SHARE", []),
    ],
)
def test_create_project_rejects_nonfeasible_proof_without_project_object(
    initiative_id: str,
    path: list[str],
) -> None:
    response = TestClient(app).post(
        "/api/projects/from-plan",
        json=_project_payload(initiative_id, path),
    )
    _assert_error(response, 409, "PROJECT_PLAN_NOT_FEASIBLE")
    assert "project" not in response.json()


def test_create_project_path_validation_uses_stable_errors() -> None:
    client = TestClient(app)
    unknown = client.post(
        "/api/projects/from-plan",
        json=_project_payload("BASIC_WORKSHOP", ["UNKNOWN_ACTION"]),
    )
    _assert_error(unknown, 404, "INVALID_REFERENCE")

    too_long = client.post(
        "/api/projects/from-plan",
        json=_project_payload(
            "MULTILINGUAL_CLINIC",
            ["TRAIN_DIGITAL_HELPERS", "RECRUIT_HELPER_A", "RECRUIT_HELPER_B"],
        ),
    )
    _assert_error(too_long, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("mutation", ["omit_path", "extra_field"])
def test_create_project_request_is_strict_and_requires_explicit_path(mutation: str) -> None:
    payload = _project_payload("BASIC_WORKSHOP", [])
    if mutation == "omit_path":
        del payload["catalyst_path"]
    else:
        payload["client_readiness"] = "READY"
    response = TestClient(app).post("/api/projects/from-plan", json=payload)
    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("mutation", ["capability", "quantity", "availability", "lineage"])
def test_create_project_rejects_forged_base_state_before_solver(mutation: str) -> None:
    payload = _project_payload("MULTILINGUAL_CLINIC", [])
    community = payload["base_community"]
    assert isinstance(community, dict)
    if mutation == "capability":
        community["people"][1]["capabilities"].append("digital_support")
        community["people"][2]["capabilities"].append("digital_support")
    elif mutation == "quantity":
        community["resources"][0]["quantity"] += 1
    elif mutation == "availability":
        community["spaces"][0]["available_slots"].remove("SAT_12")
    else:
        community["parent_state_id"] = "S_FAKE_PARENT"
    assert community["state_id"] == "S0"
    response = TestClient(app).post("/api/projects/from-plan", json=payload)
    _assert_error(response, 409, "COMMUNITY_STATE_MISMATCH")
    assert "project" not in response.json()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("short_description", "                     "),
        ("objective", "                     "),
    ],
)
def test_create_project_rejects_whitespace_only_metadata(field: str, value: str) -> None:
    payload = _project_payload("BASIC_WORKSHOP", [])
    payload[field] = value
    response = TestClient(app).post("/api/projects/from-plan", json=payload)
    _assert_error(response, 422, "INVALID_REQUEST")


def test_create_project_normalizes_metadata_before_storage_and_identity() -> None:
    payload = _project_payload("BASIC_WORKSHOP", [])
    payload["title"] = "  Saturday community digital support  "
    response = TestClient(app).post("/api/projects/from-plan", json=payload)
    assert response.status_code == 201
    parsed = CreateProjectResponse.model_validate(response.json())
    assert parsed.project.title == "Saturday community digital support"


def test_invalid_ids_catalogue_mismatch_and_validation_use_stable_errors() -> None:
    client = TestClient(app)
    unknown_initiative = client.post(
        "/api/analyse",
        json={"community": _community(), "initiative_ids": ["UNKNOWN_INITIATIVE"]},
    )
    _assert_error(unknown_initiative, 404, "INVALID_REFERENCE")

    unknown_action = client.post(
        "/api/transition",
        json={"community": _community(), "action_id": "UNKNOWN_ACTION", "actions": _actions()},
    )
    _assert_error(unknown_action, 404, "INVALID_REFERENCE")

    changed_actions = _actions()
    changed_actions[0]["cost"] = 999
    mismatch = client.post(
        "/api/unlock",
        json={"community": _community(), "initiative_id": "MULTILINGUAL_CLINIC", "actions": changed_actions},
    )
    _assert_error(mismatch, 422, "ACTION_CATALOGUE_MISMATCH")

    malformed = client.post("/api/analyse", json={})
    _assert_error(malformed, 422, "INVALID_REQUEST")
    assert "detail" not in malformed.json()


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("get", "/api/not-a-route", 404, "ROUTE_NOT_FOUND"),
        ("get", "/api/analyse", 405, "METHOD_NOT_ALLOWED"),
    ],
)
def test_framework_http_errors_use_the_frozen_envelope(
    method: str,
    path: str,
    status: int,
    code: str,
) -> None:
    response = getattr(TestClient(app), method)(path)

    _assert_error(response, status, code)
    assert "detail" not in response.json()
    assert response.json()["error"]["details"] == {
        "method": method.upper(),
        "path": path,
    }


def test_unlock_rejects_an_already_feasible_target() -> None:
    response = TestClient(app).post(
        "/api/unlock",
        json={
            "community": _community(),
            "initiative_id": "BASIC_WORKSHOP",
            "actions": _actions(),
        },
    )

    _assert_error(response, 409, "ALREADY_FEASIBLE")


def test_training_action_reapplication_is_rejected_without_a_noop_state() -> None:
    client = TestClient(app)
    first = client.post(
        "/api/transition",
        json={
            "community": _community(),
            "action_id": "TRAIN_DIGITAL_HELPERS",
            "actions": _actions(),
        },
    )
    assert first.status_code == 200

    repeated = client.post(
        "/api/transition",
        json={
            "community": first.json()["successor_state"],
            "action_id": "TRAIN_DIGITAL_HELPERS",
            "actions": _actions(),
        },
    )

    _assert_error(repeated, 409, "ACTION_ALREADY_APPLIED")


@pytest.mark.parametrize("invalid_cap", [True, False, "20", 20.0])
def test_plan_expansion_cap_requires_a_strict_integer(invalid_cap: object) -> None:
    response = TestClient(app).post(
        "/api/plan",
        json={
            "community": _community(),
            "initiative_id": "MULTILINGUAL_CLINIC",
            "actions": _actions(),
            "max_depth": 2,
            "max_expanded_states": invalid_cap,
        },
    )

    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("collection", ["organisations", "people", "spaces", "resources"])
def test_analyse_rejects_community_collections_above_explicit_limits(collection: str) -> None:
    limits = {"organisations": 32, "people": 128, "spaces": 32, "resources": 64}
    community = _community()
    template = deepcopy(community[collection][0])
    while len(community[collection]) <= limits[collection]:
        item = deepcopy(template)
        item["id"] = f"EXTRA_{collection.upper()}_{len(community[collection]):03d}"
        community[collection].append(item)

    response = TestClient(app).post(
        "/api/analyse",
        json={"community": community, "initiative_ids": ["BASIC_WORKSHOP"]},
    )

    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("field", ["capabilities", "willing_to_learn"])
def test_analyse_rejects_person_capability_sets_above_limit(field: str) -> None:
    community = _community()
    community["people"][0][field] = [f"cap_{index:02d}" for index in range(33)]

    response = TestClient(app).post(
        "/api/analyse",
        json={"community": community, "initiative_ids": ["BASIC_WORKSHOP"]},
    )

    _assert_error(response, 422, "INVALID_REQUEST")


def test_analyse_rejects_person_language_sets_above_limit() -> None:
    community = _community()
    community["people"][0]["languages"] = [f"a{letter}" for letter in "abcdefghijklmnopq"]

    response = TestClient(app).post(
        "/api/analyse",
        json={"community": community, "initiative_ids": ["BASIC_WORKSHOP"]},
    )

    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("overflow", ["actions", "preconditions", "effects"])
def test_unlock_rejects_action_contract_collections_above_limits(overflow: str) -> None:
    actions = _actions()
    if overflow == "actions":
        template = deepcopy(actions[0])
        actions = []
        for index in range(33):
            action = deepcopy(template)
            action["id"] = f"ACTION_{index:02d}"
            actions.append(action)
    elif overflow == "preconditions":
        actions[0]["preconditions"]["person_capabilities"] = [
            {"person_id": "PRIYA", "capability_id": "digital_support"}
            for _ in range(65)
        ]
    else:
        actions[0]["effects"] = [deepcopy(actions[0]["effects"][0]) for _ in range(65)]

    response = TestClient(app).post(
        "/api/unlock",
        json={
            "community": _community(),
            "initiative_id": "MULTILINGUAL_CLINIC",
            "actions": actions,
        },
    )

    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize(
    ("route", "target", "payload"),
    [
        (
            "/api/analyse",
            "app.main.analyse_compiled_initiatives",
            lambda: {"community": _community(), "initiative_ids": ["BASIC_WORKSHOP"]},
        ),
        (
            "/api/explain",
            "app.main.explain_infeasibility",
            lambda: {"community": _community(), "initiative_id": "MULTILINGUAL_CLINIC"},
        ),
        (
            "/api/unlock",
            "app.main.find_minimum_unlock",
            lambda: {
                "community": _community(),
                "initiative_id": "MULTILINGUAL_CLINIC",
                "actions": _actions(),
            },
        ),
        (
            "/api/plan",
            "app.main.plan_catalyst",
            lambda: {
                "community": _community(),
                "initiative_id": "MULTILINGUAL_CLINIC",
                "actions": _actions(),
                "max_depth": 2,
                "max_expanded_states": 20,
            },
        ),
        (
            "/api/projects/from-plan",
            "app.main.create_project_from_plan",
            lambda: _project_payload("BASIC_WORKSHOP", []),
        ),
    ],
)
def test_solver_backed_routes_translate_analyser_contract_breaches(
    monkeypatch,
    route: str,
    target: str,
    payload,
) -> None:
    def breach(*_args, **_kwargs):
        raise AnalyserContractError("malformed decoded witness")

    monkeypatch.setattr(target, breach)
    response = TestClient(app).post(route, json=payload())
    _assert_error(response, 500, "ANALYSER_CONTRACT_ERROR")
    assert "project" not in response.json()


def test_openapi_contains_frozen_core_routes() -> None:
    assert set(app.openapi()["paths"]) == {
        "/api/health", "/api/demo", "/api/analyse", "/api/explain",
        "/api/unlock", "/api/plan", "/api/transition", "/api/projects/from-plan",
    }
