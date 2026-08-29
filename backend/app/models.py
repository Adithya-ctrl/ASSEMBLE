"""Frozen ASSEMBLE domain contracts for the M0 baseline."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StableId = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
CapabilityId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
LanguageCode = Annotated[str, Field(pattern=r"^[a-z]{2}$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeSlot(StrEnum):
    SAT_10 = "SAT_10"
    SAT_11 = "SAT_11"
    SAT_12 = "SAT_12"
    SAT_13 = "SAT_13"


ORDERED_TIME_SLOTS: tuple[TimeSlot, ...] = tuple(TimeSlot)


class OrganisationBlock(ContractModel):
    id: StableId
    name: str = Field(min_length=1)


class PersonBlock(ContractModel):
    id: StableId
    name: str = Field(min_length=1)
    organisation_id: StableId
    capabilities: set[CapabilityId] = Field(default_factory=set)
    languages: set[LanguageCode] = Field(default_factory=set)
    willing_to_learn: set[CapabilityId] = Field(default_factory=set)
    available_slots: set[TimeSlot] = Field(default_factory=set)
    max_contribution_slots: int = Field(ge=1)

    @model_validator(mode="after")
    def contribution_fits_availability(self) -> "PersonBlock":
        if self.max_contribution_slots > len(self.available_slots):
            raise ValueError("max_contribution_slots exceeds available slots")
        return self


class SpaceBlock(ContractModel):
    id: StableId
    name: str = Field(min_length=1)
    organisation_id: StableId
    available_slots: set[TimeSlot] = Field(default_factory=set)
    capacity: int = Field(ge=0)
    features: set[CapabilityId] = Field(default_factory=set)


class ResourceBlock(ContractModel):
    id: StableId
    name: str = Field(min_length=1)
    organisation_id: StableId
    quantity: int = Field(ge=0)
    available_slots: set[TimeSlot] = Field(default_factory=set)
    shareable: bool


class CommunityState(ContractModel):
    state_id: StableId
    parent_state_id: StableId | None = None
    organisations: list[OrganisationBlock] = Field(default_factory=list)
    people: list[PersonBlock] = Field(default_factory=list)
    spaces: list[SpaceBlock] = Field(default_factory=list)
    resources: list[ResourceBlock] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_resolve(self) -> "CommunityState":
        organisation_ids = _unique_ids(self.organisations, "organisation")
        _unique_ids(self.people, "person")
        _unique_ids(self.spaces, "space")
        _unique_ids(self.resources, "resource")
        for item in [*self.people, *self.spaces, *self.resources]:
            _require_reference(item.organisation_id, organisation_ids, f"block {item.id}")
        return self


class RoleRequirement(ContractModel):
    id: StableId
    label: str = Field(min_length=1)
    required_capabilities: set[CapabilityId] = Field(default_factory=set)
    required_languages: set[LanguageCode] = Field(default_factory=set)
    allow_shared_person: bool = False


class VenueRequirement(ContractModel):
    minimum_capacity: int = Field(ge=0)
    required_features: set[CapabilityId] = Field(default_factory=set)


class ResourceRequirement(ContractModel):
    resource_id: StableId
    quantity: int = Field(ge=1)


class InitiativeBlueprint(ContractModel):
    id: StableId
    name: str = Field(min_length=1)
    roles: list[RoleRequirement] = Field(default_factory=list)
    venue: VenueRequirement
    resources: list[ResourceRequirement] = Field(default_factory=list)
    candidate_start_slots: list[TimeSlot] = Field(min_length=1)
    duration_slots: int = Field(ge=1, le=len(ORDERED_TIME_SLOTS))

    @model_validator(mode="after")
    def valid_time_and_roles(self) -> "InitiativeBlueprint":
        _unique_ids(self.roles, f"role in {self.id}")
        if len(set(self.candidate_start_slots)) != len(self.candidate_start_slots):
            raise ValueError(f"initiative {self.id} has duplicate candidate starts")
        for start in self.candidate_start_slots:
            occupied_slots(start, self.duration_slots)
        return self


class PersonCapabilityPrecondition(ContractModel):
    person_id: StableId
    capability_id: CapabilityId


class WillingLearnerPrecondition(ContractModel):
    person_id: StableId
    capability_id: CapabilityId


class SpaceAvailabilityPrecondition(ContractModel):
    space_id: StableId
    slots: set[TimeSlot] = Field(default_factory=set)


class ActionPreconditions(ContractModel):
    person_capabilities: list[PersonCapabilityPrecondition] = Field(default_factory=list)
    willing_learners: list[WillingLearnerPrecondition] = Field(default_factory=list)
    space_availability: list[SpaceAvailabilityPrecondition] = Field(default_factory=list)


class AddCapabilityEffect(ContractModel):
    type: Literal["add_capability"]
    person_id: StableId
    capability_id: CapabilityId


class AddPersonEffect(ContractModel):
    type: Literal["add_person"]
    person: PersonBlock


class AddResourceQuantityEffect(ContractModel):
    type: Literal["add_resource_quantity"]
    resource_id: StableId
    quantity: int = Field(ge=1)


ActionEffect = Annotated[
    AddCapabilityEffect | AddPersonEffect | AddResourceQuantityEffect,
    Field(discriminator="type"),
]


class CatalystAction(ContractModel):
    id: StableId
    name: str = Field(min_length=1)
    cost: int = Field(ge=0)
    preconditions: ActionPreconditions = Field(default_factory=ActionPreconditions)
    effects: list[ActionEffect] = Field(min_length=1)


class DemoFixture(ContractModel):
    fixture_version: str = Field(pattern=r"^assemble-demo-v[0-9]+$")
    community: CommunityState
    initiatives: list[InitiativeBlueprint] = Field(min_length=1)
    actions: list[CatalystAction] = Field(min_length=1)

    @model_validator(mode="after")
    def all_references_resolve(self) -> "DemoFixture":
        _unique_ids(self.initiatives, "initiative")
        _unique_ids(self.actions, "action")
        people = {item.id: item for item in self.community.people}
        spaces = {item.id: item for item in self.community.spaces}
        resources = {item.id: item for item in self.community.resources}
        organisations = {item.id for item in self.community.organisations}
        for initiative in self.initiatives:
            for requirement in initiative.resources:
                _require_reference(requirement.resource_id, resources, f"initiative {initiative.id}")
        for action in self.actions:
            for requirement in action.preconditions.person_capabilities:
                _require_reference(requirement.person_id, people, f"action {action.id}")
            for requirement in action.preconditions.willing_learners:
                _require_reference(requirement.person_id, people, f"action {action.id}")
            for requirement in action.preconditions.space_availability:
                _require_reference(requirement.space_id, spaces, f"action {action.id}")
            for effect in action.effects:
                if isinstance(effect, AddCapabilityEffect):
                    _require_reference(effect.person_id, people, f"action {action.id}")
                elif isinstance(effect, AddPersonEffect):
                    _require_reference(effect.person.organisation_id, organisations, f"action {action.id}")
                else:
                    _require_reference(effect.resource_id, resources, f"action {action.id}")
        return self


def occupied_slots(start: TimeSlot, duration_slots: int) -> tuple[TimeSlot, ...]:
    start_index = ORDERED_TIME_SLOTS.index(start)
    end_index = start_index + duration_slots
    if end_index > len(ORDERED_TIME_SLOTS):
        raise ValueError("occupied slots extend beyond the declared time horizon")
    return ORDERED_TIME_SLOTS[start_index:end_index]


def _unique_ids(items: list[object], label: str) -> set[str]:
    ids = [getattr(item, "id") for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {label} id")
    return set(ids)


def _require_reference(reference: str, available: object, context: str) -> None:
    if reference not in available:  # type: ignore[operator]
        raise ValueError(f"{context} references missing id {reference}")

