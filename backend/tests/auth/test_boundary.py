from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.boundary import AuthBoundaryMiddleware
from app.auth.config import AuthSettings


def _client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    settings = AuthSettings(database_path=tmp_path / "auth.sqlite3")
    app.add_middleware(AuthBoundaryMiddleware, settings=settings)

    @app.post("/api/auth/echo")
    async def echo(payload: dict[str, object]) -> dict[str, object]:
        return payload

    @app.post("/api/unrelated")
    async def unrelated(payload: dict[str, object]) -> dict[str, object]:
        return payload

    return TestClient(app)


def test_actual_body_limit_rejects_oversized_declared_and_streamed_bodies(tmp_path: Path) -> None:
    client = _client(tmp_path)
    oversized = '{"unknown":"' + ("x" * (16 * 1024)) + '"}'
    declared = client.post(
        "/api/auth/echo",
        content=oversized,
        headers={"Content-Type": "application/json", "Content-Length": str(len(oversized))},
    )
    assert declared.status_code == 422
    assert declared.json()["error"]["code"] == "INVALID_REQUEST"

    def chunks():
        yield b'{"unknown":"'
        yield b"x" * (16 * 1024)
        yield b'"}'

    streamed = client.post(
        "/api/auth/echo",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )
    assert streamed.status_code == 422
    assert streamed.json()["error"]["code"] == "INVALID_REQUEST"


def test_body_limit_is_scoped_to_auth_routes(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/unrelated",
        json={"large": "x" * (17 * 1024)},
    )
    assert response.status_code == 200


def test_unsafe_auth_routes_require_json_and_reject_cross_site_browser_headers(tmp_path: Path) -> None:
    client = _client(tmp_path)
    missing_json = client.post("/api/auth/echo", content="{}")
    assert (missing_json.status_code, missing_json.json()["error"]["code"]) == (
        415,
        "UNSUPPORTED_MEDIA_TYPE",
    )

    bad_origin = client.post(
        "/api/auth/echo",
        json={},
        headers={"Origin": "https://evil.example"},
    )
    assert (bad_origin.status_code, bad_origin.json()["error"]["code"]) == (
        403,
        "BROWSER_ORIGIN_REJECTED",
    )

    bad_fetch = client.post(
        "/api/auth/echo",
        json={},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert bad_fetch.status_code == 403

    allowed = client.post(
        "/api/auth/echo",
        json={"ok": True},
        headers={"Origin": "http://localhost:3000", "Sec-Fetch-Site": "same-origin"},
    )
    assert allowed.json() == {"ok": True}
    assert allowed.headers["cache-control"] == "no-store"


def test_non_browser_client_without_origin_is_allowed(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/api/auth/echo", json={"ok": True})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_near_prefix_routes_fall_through_to_stable_not_found(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in ("/api/authentic", "/api/communities-v2", "/api/invitations-old"):
        response = client.post(path, content="not-json")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


def test_real_auth_path_segment_remains_boundary_scoped(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/api/auth/echo", content="not-json")
    assert (response.status_code, response.json()["error"]["code"]) == (
        415,
        "UNSUPPORTED_MEDIA_TYPE",
    )
