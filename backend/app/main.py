"""Integrated ASSEMBLE HTTP API backed by the real solver and planner."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api_models import (
    AnalyseRequest,
    AnalyseResponse,
    ExplainRequest,
    ExplainResponse,
    PlanRequest,
    PlanResponse,
    TransitionRequest,
    TransitionResponse,
    UnlockRequest,
    UnlockResponse,
)
from app.explain import AnalyserContractError, explain_infeasibility
from app.fixture import fresh_demo_fixture, load_demo_fixture
from app.interventions import (
    ActionAlreadyApplied,
    AlreadyFeasible,
    NoUnlockPath,
    TransitionError,
    find_minimum_unlock,
    transition_state,
)
from app.models import CatalystAction, InitiativeBlueprint
from app.planner import NoPlanFound, plan_catalyst
from app.solver import analyse_initiatives, build_compile_summary, solve_initiative


app = FastAPI(title="ASSEMBLE API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


class ApiProblem(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def _error(status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


@app.exception_handler(ApiProblem)
async def api_problem_handler(_: Request, exc: ApiProblem) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    issues = [
        {
            "location": ".".join(str(part) for part in issue["loc"]),
            "message": issue["msg"],
            "type": issue["type"],
        }
        for issue in exc.errors()
    ]
    return _error(422, "INVALID_REQUEST", "The request does not match the frozen API contract.", {"issues": issues})


@app.exception_handler(StarletteHTTPException)
async def framework_http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return _error(
            404,
            "ROUTE_NOT_FOUND",
            "The requested API route does not exist.",
            {"method": request.method, "path": request.url.path},
        )
    if exc.status_code == 405:
        return _error(
            405,
            "METHOD_NOT_ALLOWED",
            "The requested method is not allowed for this API route.",
            {"method": request.method, "path": request.url.path},
        )
    return _error(
        exc.status_code,
        "HTTP_ERROR",
        "The API could not complete the request.",
        {"method": request.method, "path": request.url.path},
    )


def _initiative(initiative_id: str) -> InitiativeBlueprint:
    for initiative in load_demo_fixture().initiatives:
        if initiative.id == initiative_id:
            return initiative
    raise ApiProblem(
        404,
        "INVALID_REFERENCE",
        "The request references an unknown initiative.",
        {"initiative_id": initiative_id},
    )


def _initiatives(initiative_ids: Sequence[str]) -> list[InitiativeBlueprint]:
    if len(initiative_ids) != len(set(initiative_ids)):
        raise ApiProblem(
            422,
            "INVALID_REQUEST",
            "initiative_ids must not contain duplicates.",
            {"initiative_ids": list(initiative_ids)},
        )
    return [_initiative(initiative_id) for initiative_id in initiative_ids]


def _authoritative_actions(provided: Sequence[CatalystAction]) -> list[CatalystAction]:
    provided_ids = [action.id for action in provided]
    if len(provided_ids) != len(set(provided_ids)):
        raise ApiProblem(
            422,
            "INVALID_ACTION_CATALOGUE",
            "The intervention catalogue contains duplicate action IDs.",
            {"action_ids": provided_ids},
        )

    authoritative = list(load_demo_fixture().actions)
    expected = {action.id: action.model_dump(mode="json") for action in authoritative}
    received = {action.id: action.model_dump(mode="json") for action in provided}
    if received != expected:
        raise ApiProblem(
            422,
            "ACTION_CATALOGUE_MISMATCH",
            "The intervention catalogue does not match the disclosed server catalogue.",
            {
                "expected_action_ids": sorted(expected),
                "received_action_ids": sorted(received),
            },
        )
    return [action.model_copy(deep=True) for action in authoritative]


def _translate_reasoning_error(exc: Exception) -> ApiProblem:
    if isinstance(exc, ActionAlreadyApplied):
        return ApiProblem(409, "ACTION_ALREADY_APPLIED", str(exc))
    if isinstance(exc, AlreadyFeasible):
        return ApiProblem(409, "ALREADY_FEASIBLE", str(exc))
    if isinstance(exc, TransitionError):
        return ApiProblem(409, "TRANSITION_NOT_ALLOWED", str(exc))
    if isinstance(exc, NoUnlockPath):
        return ApiProblem(422, "NO_UNLOCK_PATH", str(exc))
    if isinstance(exc, NoPlanFound):
        return ApiProblem(422, "NO_PLAN_FOUND", str(exc))
    if isinstance(exc, AnalyserContractError):
        return ApiProblem(500, "ANALYSER_CONTRACT_ERROR", "The solver analyser returned an invalid result.")
    return ApiProblem(422, "INVALID_REQUEST", str(exc))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "solver": "ortools-cp-sat"}


@app.get("/api/demo")
def demo() -> dict[str, object]:
    return fresh_demo_fixture().model_dump(mode="json")


@app.post("/api/analyse", response_model=AnalyseResponse)
def analyse(request: AnalyseRequest) -> AnalyseResponse:
    initiatives = _initiatives(request.initiative_ids)
    return AnalyseResponse(
        compile=build_compile_summary(request.community, initiatives),
        results=analyse_initiatives(request.community, initiatives),
    )


@app.post("/api/explain", response_model=ExplainResponse)
def explain(request: ExplainRequest) -> ExplainResponse:
    try:
        return explain_infeasibility(request.community, _initiative(request.initiative_id), solve_initiative)
    except (AnalyserContractError, ValueError) as exc:
        raise _translate_reasoning_error(exc) from exc


@app.post("/api/unlock", response_model=UnlockResponse)
def unlock(request: UnlockRequest) -> UnlockResponse:
    actions = _authoritative_actions(request.actions)
    try:
        return find_minimum_unlock(
            request.community,
            _initiative(request.initiative_id),
            actions,
            solve_initiative,
        )
    except (AlreadyFeasible, AnalyserContractError, NoUnlockPath, TransitionError, ValueError) as exc:
        raise _translate_reasoning_error(exc) from exc


@app.post("/api/transition", response_model=TransitionResponse)
def transition(request: TransitionRequest) -> TransitionResponse:
    actions = _authoritative_actions(request.actions)
    if request.action_id not in {action.id for action in actions}:
        raise ApiProblem(
            404,
            "INVALID_REFERENCE",
            "The request references an unknown action.",
            {"action_id": request.action_id},
        )
    try:
        return transition_state(request.community, request.action_id, actions)
    except (ActionAlreadyApplied, TransitionError, ValueError) as exc:
        raise _translate_reasoning_error(exc) from exc


@app.post("/api/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    actions = _authoritative_actions(request.actions)
    try:
        return plan_catalyst(
            request.community,
            _initiative(request.initiative_id),
            actions,
            solve_initiative,
            max_depth=request.max_depth,
            max_expanded_states=request.max_expanded_states,
        )
    except (AnalyserContractError, NoPlanFound, TransitionError, ValueError) as exc:
        raise _translate_reasoning_error(exc) from exc
