"""Practice Set P: bounded HTTP abuse against the non-auth API surface.

These tests deliberately exercise the integrated FastAPI application through
``TestClient``.  Auth, community, and invitation routes are excluded: their
method/media/body/namespace boundary belongs to the auth-owned test lane.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.fixture import fresh_demo_fixture
from app.main import app


# This is the exact non-auth inventory from docs/reference/api.md.  Auth,
# community, and invitation paths intentionally do not appear here.
NON_AUTH_ENDPOINTS: dict[str, dict[str, int]] = {
    "/api/health": {"GET": 200},
    "/api/demo": {"GET": 200},
    "/api/analyse": {"POST": 200},
    "/api/explain": {"POST": 200},
    "/api/unlock": {"POST": 200},
    "/api/plan": {"POST": 200},
    "/api/transition": {"POST": 200},
    "/api/projects/from-plan": {"POST": 201},
    "/api/stress-test": {"POST": 200},
    "/api/recompile": {"POST": 200},
    "/api/frontier": {"POST": 200},
}

GET_ROUTES = tuple(path for path, methods in NON_AUTH_ENDPOINTS.items() if "GET" in methods)
POST_ROUTES = tuple(path for path, methods in NON_AUTH_ENDPOINTS.items() if "POST" in methods)
AUTH_NAMESPACE_PREFIXES = ("/api/auth", "/api/communities", "/api/invitations")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _community() -> dict[str, Any]:
    return fresh_demo_fixture().community.model_dump(mode="json")


def _actions() -> list[dict[str, Any]]:
    return [action.model_dump(mode="json") for action in fresh_demo_fixture().actions]


def _project_payload(catalyst_path: list[str] | None = None) -> dict[str, Any]:
    return {
        "base_community": _community(),
        "initiative_id": "BASIC_WORKSHOP",
        "catalyst_path": catalyst_path or [],
        "title": "Saturday community digital support",
        "short_description": "A solver-verified community service assembled from shared local capacity.",
        "objective": "Deliver accessible digital help with every operational dependency verified.",
    }


def _payload(route: str) -> dict[str, Any]:
    if route == "/api/analyse":
        return {"community": _community(), "initiative_ids": ["BASIC_WORKSHOP"]}
    if route == "/api/explain":
        return {"community": _community(), "initiative_id": "MULTILINGUAL_CLINIC"}
    if route == "/api/unlock":
        return {
            "community": _community(),
            "initiative_id": "MULTILINGUAL_CLINIC",
            "actions": _actions(),
        }
    if route == "/api/plan":
        return {
            "community": _community(),
            "initiative_id": "MULTILINGUAL_CLINIC",
            "actions": _actions(),
            "max_depth": 2,
            "max_expanded_states": 20,
        }
    if route == "/api/transition":
        return {
            "community": _community(),
            "action_id": "TRAIN_DIGITAL_HELPERS",
            "actions": _actions(),
        }
    if route == "/api/projects/from-plan":
        return _project_payload()
    if route == "/api/stress-test":
        return {
            "base_community": _community(),
            "initiative_id": "BASIC_WORKSHOP",
            "catalyst_path": [],
        }
    if route == "/api/recompile":
        return {
            "base_community": _community(),
            "initiative_id": "BASIC_WORKSHOP",
            "catalyst_path": [],
            "perturbation_id": "ASSEMBLE_STRESS_PERTURBATION_V1_FORGED",
        }
    if route == "/api/frontier":
        return {"base_community": _community(), "catalyst_path": []}
    raise AssertionError(f"no non-auth payload factory for {route}")


def _assert_error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], dict)
    assert "detail" not in payload
    assert "Traceback" not in response.text


def _assert_method_error(response: Any, method: str, path: str) -> None:
    _assert_error(response, 405, "METHOD_NOT_ALLOWED")
    assert response.json()["error"]["details"] == {"method": method, "path": path}


def _assert_route_error(response: Any, method: str, path: str) -> None:
    _assert_error(response, 404, "ROUTE_NOT_FOUND")
    assert response.json()["error"]["details"] == {"method": method, "path": path}


def test_non_auth_openapi_inventory_and_methods_are_exact() -> None:
    openapi = app.openapi()["paths"]
    observed = {
        path: {method.upper(): operation for method, operation in methods.items()}
        for path, methods in openapi.items()
        if not any(path == prefix or path.startswith(f"{prefix}/") for prefix in AUTH_NAMESPACE_PREFIXES)
    }
    assert set(observed) == set(NON_AUTH_ENDPOINTS)
    assert {path: set(methods) for path, methods in observed.items()} == {
        path: set(methods) for path, methods in NON_AUTH_ENDPOINTS.items()
    }
    assert all(
        not any(path == prefix or path.startswith(f"{prefix}/") for prefix in AUTH_NAMESPACE_PREFIXES)
        for path in NON_AUTH_ENDPOINTS
    )


def test_declared_get_and_post_routes_reach_their_success_contract(client: TestClient) -> None:
    for path in GET_ROUTES:
        response = client.get(path)
        assert response.status_code == NON_AUTH_ENDPOINTS[path]["GET"]
        assert "error" not in response.json()

    for path in POST_ROUTES:
        payload = _payload(path)
        if path == "/api/recompile":
            stress = client.post("/api/stress-test", json=_payload("/api/stress-test"))
            assert stress.status_code == 200, stress.text
            payload["perturbation_id"] = stress.json()["outcomes"][0]["perturbation_id"]
        response = client.post(path, json=payload)
        assert response.status_code == NON_AUTH_ENDPOINTS[path]["POST"], response.text
        assert "error" not in response.json()


@pytest.mark.parametrize("path", NON_AUTH_ENDPOINTS)
def test_inverse_method_is_a_stable_405_for_every_non_auth_route(
    client: TestClient,
    path: str,
) -> None:
    declared = next(iter(NON_AUTH_ENDPOINTS[path]))
    wrong = "POST" if declared == "GET" else "GET"
    response = client.request(wrong, path)
    _assert_method_error(response, wrong, path)


@pytest.mark.parametrize("path", NON_AUTH_ENDPOINTS)
@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH"])
def test_invalid_methods_are_stable_405_for_every_non_auth_route(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    response = client.request(method, path)
    _assert_method_error(response, method, path)


def test_allowed_json_options_preflight_is_not_an_error_envelope(client: TestClient) -> None:
    response = client.options(
        "/api/analyse",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.text == "OK"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-methods"]


@pytest.mark.parametrize("route", POST_ROUTES)
@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/x-www-form-urlencoded", "application/octet-stream", "TEXT/PLAIN"],
)
def test_non_auth_post_routes_reject_unsupported_media_with_stable_error(
    client: TestClient,
    route: str,
    content_type: str,
) -> None:
    response = client.post(route, content=b"{}", headers={"Content-Type": content_type})
    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("route", POST_ROUTES)
def test_non_auth_post_routes_without_content_type_reject_as_invalid_json(
    client: TestClient,
    route: str,
) -> None:
    response = client.post(route, content=b"{}")
    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("route", POST_ROUTES)
@pytest.mark.parametrize("body", [b"", b"not-json", b"{", b'{"community":', b"{} trailing"])
def test_non_auth_post_routes_reject_empty_and_malformed_json(
    client: TestClient,
    route: str,
    body: bytes,
) -> None:
    response = client.post(route, content=body, headers={"Content-Type": "application/json"})
    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("route", POST_ROUTES)
def test_non_auth_request_models_reject_unknown_fields_without_echoing_marker(
    client: TestClient,
    route: str,
) -> None:
    marker = "untrusted-http-extra-marker"
    payload = _payload(route)
    payload["unexpected_field"] = marker
    response = client.post(route, json=payload)
    _assert_error(response, 422, "INVALID_REQUEST")
    assert marker not in response.text


@pytest.mark.parametrize("route", POST_ROUTES)
def test_non_auth_request_models_require_their_required_fields(
    client: TestClient,
    route: str,
) -> None:
    required = {
        "/api/analyse": "initiative_ids",
        "/api/explain": "initiative_id",
        "/api/unlock": "initiative_id",
        "/api/plan": "initiative_id",
        "/api/transition": "action_id",
        "/api/projects/from-plan": "title",
        "/api/stress-test": "initiative_id",
        "/api/recompile": "perturbation_id",
        "/api/frontier": "base_community",
    }[route]
    payload = _payload(route)
    del payload[required]
    response = client.post(route, json=payload)
    _assert_error(response, 422, "INVALID_REQUEST")


def _add_people_overflow(payload: dict[str, Any]) -> None:
    community = payload["community"] if "community" in payload else payload["base_community"]
    template = deepcopy(community["people"][0])
    while len(community["people"]) <= 128:
        extra = deepcopy(template)
        extra["id"] = f"EXTRA_PERSON_{len(community['people']):03d}"
        community["people"].append(extra)


def _overflow_payload(route: str) -> dict[str, Any]:
    payload = _payload(route)
    if route == "/api/analyse":
        payload["initiative_ids"] = [f"INIT_{index:02d}" for index in range(33)]
    elif route in {"/api/unlock", "/api/plan", "/api/transition"}:
        template = deepcopy(payload["actions"][0])
        payload["actions"] = []
        for index in range(33):
            action = deepcopy(template)
            action["id"] = f"ACTION_{index:02d}"
            payload["actions"].append(action)
        if route == "/api/plan":
            payload["max_expanded_states"] = 21
    elif route == "/api/projects/from-plan":
        payload["catalyst_path"] = ["A", "B", "C"]
    elif route in {"/api/stress-test", "/api/recompile", "/api/frontier"}:
        payload["catalyst_path"] = ["A", "B", "C"]
    else:
        _add_people_overflow(payload)
    return payload


@pytest.mark.parametrize("route", POST_ROUTES)
def test_non_auth_declared_collection_or_path_ceiling_rejects_max_plus_one(
    client: TestClient,
    route: str,
) -> None:
    payload = _overflow_payload(route)
    response = client.post(route, json=payload)
    _assert_error(response, 422, "INVALID_REQUEST")


def test_non_auth_nested_community_people_ceiling_rejects_max_plus_one(client: TestClient) -> None:
    for route in POST_ROUTES:
        payload = _payload(route)
        _add_people_overflow(payload)
        response = client.post(route, json=payload)
        _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("field", ["title", "short_description", "objective"])
def test_project_metadata_declared_maximum_rejects_max_plus_one(
    client: TestClient,
    field: str,
) -> None:
    payload = _project_payload()
    payload[field] = "x" * (101 if field == "title" else 281)
    response = client.post("/api/projects/from-plan", json=payload)
    _assert_error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize("path", tuple(NON_AUTH_ENDPOINTS))
def test_query_junk_does_not_change_canonical_non_auth_route_behavior(
    client: TestClient,
    path: str,
) -> None:
    method = next(iter(NON_AUTH_ENDPOINTS[path]))
    if method == "GET":
        canonical = client.get(path)
        variant = client.get(f"{path}?junk=%E2%9C%93&unknown=1")
    else:
        canonical = client.post(path, json={})
        variant = client.post(f"{path}?junk=%E2%9C%93&unknown=1", json={})
    assert variant.status_code == canonical.status_code
    if canonical.status_code >= 400:
        assert variant.json()["error"]["code"] == canonical.json()["error"]["code"]
    else:
        assert variant.json() == canonical.json()


@pytest.mark.parametrize("path", tuple(NON_AUTH_ENDPOINTS))
def test_trailing_slash_resolves_only_to_the_same_non_auth_route(
    client: TestClient,
    path: str,
) -> None:
    method = next(iter(NON_AUTH_ENDPOINTS[path]))
    if method == "GET":
        canonical = client.get(path)
        variant = client.get(f"{path}/")
    else:
        canonical = client.post(path, json={})
        variant = client.post(f"{path}/", json={})
    assert variant.status_code == canonical.status_code
    if canonical.status_code >= 400:
        assert variant.json()["error"]["code"] == canonical.json()["error"]["code"]
    else:
        assert variant.json() == canonical.json()


@pytest.mark.parametrize("method, path", [("GET", path) for path in NON_AUTH_ENDPOINTS])
def test_duplicate_slash_is_a_stable_unknown_route(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    duplicate = path.replace("/api/", "/api//", 1)
    response = client.request(method, duplicate)
    _assert_route_error(response, method, duplicate)


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/api/not-a-route"),
        ("POST", "/api/analyse-v2"),
        ("GET", "/api/healthcheck"),
        ("POST", "/api/projects/from-plan-old"),
        ("POST", "/api/stress-test-v2"),
        ("POST", "/api/recompile-old"),
        ("POST", "/api/frontier-next"),
        ("GET", "/api/demo/extra"),
    ],
)
def test_core_lookalike_routes_are_stable_unknown_routes(
    client: TestClient,
    method: str,
    path: str,
) -> None:
    response = client.request(method, path)
    _assert_route_error(response, method, path)


@pytest.mark.parametrize(
    "route, payload, status, code",
    [
        (
            "/api/analyse",
            {"community": _community(), "initiative_ids": ["NOT_A_REAL_INITIATIVE"]},
            404,
            "INVALID_REFERENCE",
        ),
        ("/api/unlock", {**_payload("/api/unlock"), "initiative_id": "BASIC_WORKSHOP"}, 409, "ALREADY_FEASIBLE"),
        (
            "/api/projects/from-plan",
            {**_project_payload(), "initiative_id": "MULTILINGUAL_CLINIC"},
            409,
            "PROJECT_PLAN_NOT_FEASIBLE",
        ),
        (
            "/api/stress-test",
            {**_payload("/api/stress-test"), "initiative_id": "REPAIR_SHARE"},
            409,
            "BASELINE_NOT_FEASIBLE",
        ),
        (
            "/api/recompile",
            _payload("/api/recompile"),
            404,
            "INVALID_PERTURBATION",
        ),
        (
            "/api/frontier",
            {**_payload("/api/frontier"), "catalyst_path": ["UNKNOWN_ACTION"]},
            404,
            "INVALID_REFERENCE",
        ),
    ],
)
def test_representative_non_auth_domain_statuses_use_stable_envelopes(
    client: TestClient,
    route: str,
    payload: dict[str, Any],
    status: int,
    code: str,
) -> None:
    response = client.post(route, json=payload)
    _assert_error(response, status, code)
