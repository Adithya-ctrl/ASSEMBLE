"""FastAPI registration boundary for the isolated auth subsystem."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth.boundary import AuthBoundaryMiddleware
from app.auth.config import AuthSettings
from app.auth.errors import AuthProblem
from app.auth.models import (
    AuditEventView,
    CommunityCreateRequest,
    CommunityView,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationCreatedView,
    InvitationView,
    LoginRequest,
    MembershipView,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RoleChangeRequest,
    SessionView,
    SignupRequest,
    UserView,
)
from app.auth.service import AuthService, SessionResult
from app.auth.storage import AuthStore, StorageBusyError


ObjectId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]

router = APIRouter()


def _service(request: Request) -> AuthService:
    return request.app.state.assemble_auth_service


def _settings(request: Request) -> AuthSettings:
    return request.app.state.assemble_auth_settings


def _session_token(request: Request) -> str | None:
    return request.cookies.get(_settings(request).cookie_name)


def _client_key(request: Request) -> str:
    # Forwarded headers are intentionally ignored until a trusted-proxy
    # contract exists.  The ASGI server's peer address is authoritative.
    return request.client.host if request.client is not None else "local"


def _set_session_cookie(response: Response, settings: AuthSettings, result: SessionResult) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=result.token,
        max_age=settings.session_ttl_seconds,
        expires=datetime.fromtimestamp(result.expires_at, tz=UTC),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_session_cookie(response: Response, settings: AuthSettings) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/api/auth/signup", response_model=SessionView, status_code=201)
def signup(payload: SignupRequest, request: Request, response: Response) -> SessionView:
    result = _service(request).signup(payload, client_key=_client_key(request))
    _set_session_cookie(response, _settings(request), result)
    return result.session


@router.post("/api/auth/login", response_model=SessionView)
def login(payload: LoginRequest, request: Request, response: Response) -> SessionView:
    result = _service(request).login(payload, client_key=_client_key(request))
    _set_session_cookie(response, _settings(request), result)
    return result.session


@router.get("/api/auth/session", response_model=SessionView)
def current_session(request: Request) -> SessionView:
    return _service(request).session(_session_token(request))


@router.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    _service(request).logout(_session_token(request))
    _clear_session_cookie(response, _settings(request))


@router.post("/api/auth/password", response_model=SessionView)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
) -> SessionView:
    result = _service(request).change_password(
        _session_token(request),
        payload,
        client_key=_client_key(request),
    )
    _set_session_cookie(response, _settings(request), result)
    return result.session


@router.patch("/api/auth/profile", response_model=UserView)
def update_profile(payload: ProfileUpdateRequest, request: Request) -> UserView:
    return _service(request).update_profile(_session_token(request), payload)


@router.post("/api/communities", response_model=CommunityView, status_code=201)
def create_community(payload: CommunityCreateRequest, request: Request) -> CommunityView:
    return _service(request).create_community(_session_token(request), payload)


@router.get("/api/communities", response_model=list[CommunityView])
def list_communities(request: Request) -> list[CommunityView]:
    return _service(request).list_communities(_session_token(request))


@router.get("/api/communities/{community_id}/members", response_model=list[MembershipView])
def list_members(community_id: ObjectId, request: Request) -> list[MembershipView]:
    return _service(request).list_members(_session_token(request), community_id)


@router.patch(
    "/api/communities/{community_id}/members/{user_id}",
    response_model=MembershipView,
)
def change_member_role(
    community_id: ObjectId,
    user_id: ObjectId,
    payload: RoleChangeRequest,
    request: Request,
) -> MembershipView:
    return _service(request).change_member_role(
        _session_token(request),
        community_id,
        user_id,
        payload,
    )


@router.post(
    "/api/communities/{community_id}/invitations",
    response_model=InvitationCreatedView,
    status_code=201,
)
def create_invitation(
    community_id: ObjectId,
    payload: InvitationCreateRequest,
    request: Request,
    response: Response,
) -> InvitationCreatedView:
    result = _service(request).create_invitation(
        _session_token(request),
        community_id,
        payload,
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return result


@router.get(
    "/api/communities/{community_id}/invitations",
    response_model=list[InvitationView],
)
def list_invitations(community_id: ObjectId, request: Request) -> list[InvitationView]:
    return _service(request).list_invitations(_session_token(request), community_id)


@router.post(
    "/api/communities/{community_id}/invitations/{invitation_id}/revoke",
    response_model=InvitationView,
)
def revoke_invitation(
    community_id: ObjectId,
    invitation_id: ObjectId,
    request: Request,
) -> InvitationView:
    return _service(request).revoke_invitation(
        _session_token(request),
        community_id,
        invitation_id,
    )


@router.post("/api/invitations/accept", response_model=MembershipView)
def accept_invitation(payload: InvitationAcceptRequest, request: Request) -> MembershipView:
    return _service(request).accept_invitation(
        _session_token(request),
        payload,
        client_key=_client_key(request),
    )


@router.get(
    "/api/communities/{community_id}/audit-events",
    response_model=list[AuditEventView],
)
def list_audit_events(
    community_id: ObjectId,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AuditEventView]:
    return _service(request).list_audit_events(_session_token(request), community_id, limit)


async def auth_problem_handler(_: Request, exc: AuthProblem) -> JSONResponse:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
        headers=headers,
    )


async def storage_busy_handler(_: Request, __: StorageBusyError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "SERVICE_BUSY",
                "message": "The local identity store is busy. Try again shortly.",
                "details": {},
            }
        },
        headers={"Retry-After": "1"},
    )


async def isolated_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    issues = [
        {
            "location": ".".join(str(part) for part in issue["loc"]),
            "message": issue["msg"],
            "type": issue["type"],
        }
        for issue in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "The request does not match the auth API contract.",
                "details": {"issues": issues},
            }
        },
    )


def install_auth_api(
    app: FastAPI,
    settings: AuthSettings | None = None,
    *,
    clock: Callable[[], int] | None = None,
    token_factory: Callable[[], str] | None = None,
) -> AuthService:
    """Install the isolated routes once and return their service instance."""

    if getattr(app.state, "assemble_auth_installed", False):
        return app.state.assemble_auth_service
    resolved_settings = settings or AuthSettings.from_env()
    now = int(clock()) if clock is not None else int(time.time())
    store = AuthStore(resolved_settings.database_path, now=now)
    service = AuthService(
        store,
        resolved_settings,
        clock=clock,
        token_factory=token_factory,
    )
    app.state.assemble_auth_settings = resolved_settings
    app.state.assemble_auth_service = service
    app.state.assemble_auth_installed = True
    app.add_exception_handler(AuthProblem, auth_problem_handler)
    app.add_exception_handler(StorageBusyError, storage_busy_handler)
    app.add_middleware(AuthBoundaryMiddleware, settings=resolved_settings)
    app.include_router(router)
    return service


def create_auth_app(
    settings: AuthSettings,
    *,
    clock: Callable[[], int] | None = None,
    token_factory: Callable[[], str] | None = None,
) -> FastAPI:
    """Create a focused app for isolated runtime and restart verification."""

    app = FastAPI(title="ASSEMBLE Auth API", version="0.1.0")
    app.add_exception_handler(RequestValidationError, isolated_validation_handler)
    install_auth_api(app, settings, clock=clock, token_factory=token_factory)
    return app


__all__ = ["create_auth_app", "install_auth_api", "router"]
