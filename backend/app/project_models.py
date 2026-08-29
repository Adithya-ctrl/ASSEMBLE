"""Frozen P0-A contracts for solver-derived executable Projects."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.api_models import InitiativeAnalysisResult, StateDiff
from app.models import CommunityState, ContractModel, StableId


class ProjectStatus(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class CreateProjectRequest(ContractModel):
    base_community: CommunityState
    initiative_id: StableId
    catalyst_path: list[StableId] = Field(max_length=2)
    title: str = Field(min_length=3, max_length=100)
    short_description: str = Field(min_length=20, max_length=280)
    objective: str = Field(min_length=20, max_length=280)

    @field_validator("title", "short_description", "objective", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProjectCatalystOutput(ContractModel):
    action_id: StableId
    action_name: str = Field(min_length=1)
    predecessor_state_id: StableId
    successor_state_id: StableId
    diff: StateDiff


class ProjectSchedule(ContractModel):
    start_slot: StableId
    end_slot: StableId
    occupied_slots: list[StableId] = Field(min_length=1)
    duration_slots: int = Field(ge=1)


class ProjectVenue(ContractModel):
    venue_id: StableId
    venue_name: str = Field(min_length=1)
    organisation_id: StableId
    capacity: int = Field(ge=0)
    features: list[str] = Field(default_factory=list)


class ProjectOperationalAssignment(ContractModel):
    role_id: StableId
    role_label: str = Field(min_length=1)
    person_id: StableId
    person_name: str = Field(min_length=1)
    organisation_id: StableId
    organisation_name: str = Field(min_length=1)
    person_capabilities: list[str] = Field(default_factory=list)
    person_languages: list[str] = Field(default_factory=list)
    matched_capabilities: list[str] = Field(default_factory=list)
    matched_languages: list[str] = Field(default_factory=list)
    available_slots: list[StableId] = Field(default_factory=list)


class ProjectResourceAllocation(ContractModel):
    resource_id: StableId
    resource_name: str = Field(min_length=1)
    organisation_id: StableId
    quantity_required: int = Field(ge=1)
    quantity_available: int = Field(ge=0)
    allocated_slots: list[StableId] = Field(min_length=1)
    shareable: bool


class ProjectReadinessCheck(ContractModel):
    check_id: StableId
    label: str = Field(min_length=1)
    ready: bool
    evidence: list[str] = Field(min_length=1)


class ProjectReadiness(ContractModel):
    status: ProjectStatus
    checks: list[ProjectReadinessCheck] = Field(min_length=1)
    missing: list[str] = Field(default_factory=list)


class Project(ContractModel):
    id: StableId
    source_plan_id: StableId
    source_initiative_id: StableId
    source_initiative_name: str = Field(min_length=1)
    title: str = Field(min_length=3, max_length=100)
    short_description: str = Field(min_length=20, max_length=280)
    objective: str = Field(min_length=20, max_length=280)
    status: ProjectStatus
    base_state_id: StableId
    verified_state_id: StableId
    catalyst_path: list[StableId] = Field(default_factory=list, max_length=2)
    catalyst_outputs: list[ProjectCatalystOutput] = Field(default_factory=list, max_length=2)
    host_organisation_id: StableId
    host_organisation_name: str = Field(min_length=1)
    venue: ProjectVenue
    schedule: ProjectSchedule
    operational_assignments: list[ProjectOperationalAssignment] = Field(min_length=1)
    resources: list[ProjectResourceAllocation] = Field(default_factory=list)
    capability_modules: list[str] = Field(default_factory=list)
    accessibility_requirements: list[str] = Field(default_factory=list)
    supported_languages: list[str] = Field(default_factory=list)
    participant_capacity: int = Field(ge=0)
    readiness: ProjectReadiness
    created_at: datetime
    updated_at: datetime


class CreateProjectResponse(ContractModel):
    project: Project
    verification: InitiativeAnalysisResult
