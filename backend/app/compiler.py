"""Compile ASSEMBLE initiative blueprints into CP-SAT models.

The compiler deliberately keeps the domain small and explicit.  A compiled
model contains a Boolean variable for every role/person candidate that passes
the declared capability and language filters, one variable for every venue,
one for every candidate start, and a ``used`` variable for each person that
can fill at least one role.  All other requirements are encoded as hard
constraints on those variables.

This module does not import the HTTP layer.  The solver can therefore be used
by the API, the explanation worker, and tests without duplicating semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Sequence

from ortools.sat.python import cp_model

from app.models import (
    CommunityState,
    InitiativeBlueprint,
    ORDERED_TIME_SLOTS,
    PersonBlock,
    RoleRequirement,
    SpaceBlock,
    TimeSlot,
    occupied_slots,
)


# These names are also used by the bounded explanation engine.  Keep the
# spelling in one place so a relaxation cannot silently create a different
# model from the authoritative one.
ROLE_CAPABILITY = "role_capability"
LANGUAGE = "language"
AVAILABILITY = "availability"
VENUE_FEATURE = "venue_feature"
VENUE_CAPACITY = "venue_capacity"
RESOURCE_QUANTITY = "resource_quantity"
MAXIMUM_CONTRIBUTION = "maximum_contribution"

REQUIREMENT_GROUPS = frozenset(
    {
        ROLE_CAPABILITY,
        LANGUAGE,
        AVAILABILITY,
        VENUE_FEATURE,
        VENUE_CAPACITY,
        RESOURCE_QUANTITY,
        MAXIMUM_CONTRIBUTION,
    }
)

PLANNING_BURDEN_DISTINCT_PERSON_WEIGHT = 10
PLANNING_BURDEN_ASSIGNMENT_WEIGHT = 2


def normalise_relax_groups(groups: Iterable[str] | None) -> frozenset[str]:
    """Return validated requirement groups used for bounded relaxations.

    Relaxation is intentionally explicit.  A typo must not accidentally turn
    into a broader model, so unknown group names fail at the compiler
    boundary.
    """

    if isinstance(groups, str):
        groups = (groups,)
    normalised = frozenset(str(group) for group in (groups or ()))
    unknown = normalised - REQUIREMENT_GROUPS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown requirement group(s): {names}")
    return normalised


@dataclass(slots=True)
class CompiledInitiative:
    """The complete CP-SAT representation of one initiative.

    The maps are retained so the solution extractor can decode a witness
    directly from solver variables.  They are public on purpose: callers that
    need an evidence receipt can inspect the exact compiled variable names,
    while the HTTP response still contains only stable IDs.
    """

    community: CommunityState
    initiative: InitiativeBlueprint
    model: cp_model.CpModel
    assignment_vars: dict[tuple[str, str], cp_model.IntVar]
    venue_vars: dict[str, cp_model.IntVar]
    start_vars: dict[TimeSlot, cp_model.IntVar]
    used_person_vars: dict[str, cp_model.IntVar]
    contribution_presence_vars: dict[tuple[str, TimeSlot], cp_model.IntVar]
    role_candidates: dict[str, tuple[PersonBlock, ...]]
    occupied_slots_by_start: dict[TimeSlot, tuple[TimeSlot, ...]]
    relaxed_groups: frozenset[str] = field(default_factory=frozenset)

    @property
    def decision_variables(self) -> int:
        """Number of variables in the generated CP-SAT proto."""

        return len(self.model.Proto().variables)

    @property
    def hard_constraints(self) -> int:
        """Number of constraints in the generated CP-SAT proto."""

        return len(self.model.Proto().constraints)

    @property
    def assignment_variable_count(self) -> int:
        return len(self.assignment_vars)

    @property
    def venue_variable_count(self) -> int:
        return len(self.venue_vars)

    @property
    def start_variable_count(self) -> int:
        return len(self.start_vars)

    # Short aliases keep integration code readable while the explicit names
    # above remain the canonical evidence fields.
    @property
    def variable_count(self) -> int:
        return self.decision_variables

    @property
    def constraint_count(self) -> int:
        return self.hard_constraints

    @property
    def assignment_variables(self) -> dict[tuple[str, str], cp_model.IntVar]:
        return self.assignment_vars

    @property
    def venue_variables(self) -> dict[str, cp_model.IntVar]:
        return self.venue_vars

    @property
    def start_variables(self) -> dict[TimeSlot, cp_model.IntVar]:
        return self.start_vars


def planning_burden_expression(compiled: CompiledInitiative) -> cp_model.LinearExpr:
    """Return the one authoritative lower-is-better planning burden expression."""

    return (
        PLANNING_BURDEN_DISTINCT_PERSON_WEIGHT * sum(compiled.used_person_vars.values())
        + PLANNING_BURDEN_ASSIGNMENT_WEIGHT * sum(compiled.assignment_vars.values())
    )


def planning_burden_value(assignments: Iterable[tuple[str, str]]) -> int:
    """Evaluate the compiler burden for decoded ``(role, person)`` pairs."""

    pairs = tuple(assignments)
    return (
        PLANNING_BURDEN_DISTINCT_PERSON_WEIGHT * len({person_id for _, person_id in pairs})
        + PLANNING_BURDEN_ASSIGNMENT_WEIGHT * len(pairs)
    )


def _sorted_people(community: CommunityState) -> list[PersonBlock]:
    return sorted(community.people, key=lambda person: person.id)


def _sorted_spaces(community: CommunityState) -> list[SpaceBlock]:
    return sorted(community.spaces, key=lambda space: space.id)


def _add_exactly_one(model: cp_model.CpModel, variables: Sequence[cp_model.IntVar]) -> None:
    """Add an exact-one constraint, including the empty-domain case."""

    # ``CpModel.Add`` accepts a Python bool.  ``False`` is represented in the
    # proto as an impossible constraint, which gives the solver a real proof
    # of infeasibility when a requirement has no candidates.
    model.Add(sum(variables) == 1)


def _add_false(model: cp_model.CpModel) -> None:
    model.Add(False)


def _person_matches_role(
    person: PersonBlock,
    role: RoleRequirement,
    relaxed_groups: frozenset[str],
) -> bool:
    if ROLE_CAPABILITY not in relaxed_groups and not role.required_capabilities <= person.capabilities:
        return False
    if LANGUAGE not in relaxed_groups and not role.required_languages <= person.languages:
        return False
    return True


def compile_initiative(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relax_groups: Iterable[str] | None = None,
    relaxed_groups: Iterable[str] | None = None,
    objective_mode: Literal["burden", "none"] = "burden",
) -> CompiledInitiative:
    """Compile one initiative into a genuine OR-Tools CP-SAT model.

    ``relax_groups`` is used only by the bounded explanation engine.  The
    ``relaxed_groups`` spelling is accepted as an ergonomic alias for callers
    that describe the model in prose.  Supplying both aliases is rejected if
    they disagree.
    """

    if relax_groups is not None and relaxed_groups is not None:
        first = normalise_relax_groups(relax_groups)
        second = normalise_relax_groups(relaxed_groups)
        if first != second:
            raise ValueError("relax_groups and relaxed_groups disagree")
        groups = first
    else:
        groups = normalise_relax_groups(
            relax_groups if relax_groups is not None else relaxed_groups
        )

    model = cp_model.CpModel()
    assignment_vars: dict[tuple[str, str], cp_model.IntVar] = {}
    role_candidates: dict[str, tuple[PersonBlock, ...]] = {}

    people = _sorted_people(community)
    people_by_id = {person.id: person for person in people}

    # Role/person assignment variables.  Capability and language are domain
    # eligibility predicates; availability is kept as a constraint because it
    # depends on the selected start slot.
    for role in initiative.roles:
        candidates = tuple(
            person
            for person in people
            if _person_matches_role(person, role, groups)
        )
        role_candidates[role.id] = candidates
        for person in candidates:
            assignment_vars[(role.id, person.id)] = model.NewBoolVar(
                f"assign__{role.id}__{person.id}"
            )

    # Venue and start choices are represented even when a candidate is later
    # forced to zero by a hard requirement.  This leaves the model and its
    # compile counts truthful when a negative mutation removes accessibility,
    # capacity, or availability.
    venue_vars: dict[str, cp_model.IntVar] = {
        space.id: model.NewBoolVar(f"venue__{space.id}")
        for space in _sorted_spaces(community)
    }
    start_vars: dict[TimeSlot, cp_model.IntVar] = {
        start: model.NewBoolVar(f"start__{start.value}")
        for start in initiative.candidate_start_slots
    }
    occupied_slots_by_start = {
        start: occupied_slots(start, initiative.duration_slots)
        for start in initiative.candidate_start_slots
    }

    # Every role, venue, and start must be selected exactly once.  Empty role
    # or venue domains therefore become an ordinary CP-SAT INFEASIBLE result.
    for role in initiative.roles:
        _add_exactly_one(
            model,
            [
                assignment_vars[(role.id, person.id)]
                for person in role_candidates[role.id]
            ],
        )
    _add_exactly_one(model, list(venue_vars.values()))
    _add_exactly_one(model, list(start_vars.values()))

    # A venue must satisfy capacity and all declared features.  Availability
    # is conditional on the selected start, just like people and resources.
    for space in _sorted_spaces(community):
        venue = venue_vars[space.id]
        if (
            VENUE_CAPACITY not in groups
            and space.capacity < initiative.venue.minimum_capacity
        ):
            model.Add(venue == 0)
        if (
            VENUE_FEATURE not in groups
            and not initiative.venue.required_features <= space.features
        ):
            model.Add(venue == 0)
        if AVAILABILITY not in groups:
            for start, occupied in occupied_slots_by_start.items():
                if not set(occupied) <= space.available_slots:
                    model.Add(venue + start_vars[start] <= 1)

    # A person cannot fill two simultaneous roles unless either role explicitly
    # permits sharing.  The pairwise constraints are small and make the
    # generated model easy to audit in a technical inspector.
    for left_index, left_role in enumerate(initiative.roles):
        for right_role in initiative.roles[left_index + 1 :]:
            if left_role.allow_shared_person or right_role.allow_shared_person:
                continue
            common_people = set(person.id for person in role_candidates[left_role.id]) & set(
                person.id for person in role_candidates[right_role.id]
            )
            for person_id in sorted(common_people):
                model.Add(
                    assignment_vars[(left_role.id, person_id)]
                    + assignment_vars[(right_role.id, person_id)]
                    <= 1
                )

    # Assignment availability and contribution.  The selected start is a
    # variable, so an assignment is forbidden only for starts whose occupied
    # slots are unavailable to that person.
    person_assignments: dict[str, list[cp_model.IntVar]] = {}
    person_role_assignments: dict[str, list[tuple[RoleRequirement, cp_model.IntVar]]] = {}
    for role in initiative.roles:
        for person in role_candidates[role.id]:
            assignment = assignment_vars[(role.id, person.id)]
            person_assignments.setdefault(person.id, []).append(assignment)
            person_role_assignments.setdefault(person.id, []).append((role, assignment))
            if AVAILABILITY not in groups:
                for start, occupied in occupied_slots_by_start.items():
                    if not set(occupied) <= person.available_slots:
                        model.Add(assignment + start_vars[start] <= 1)

    contribution_presence_vars: dict[tuple[str, TimeSlot], cp_model.IntVar] = {}
    if MAXIMUM_CONTRIBUTION not in groups:
        for person_id, assignments in sorted(person_assignments.items()):
            person = people_by_id[person_id]
            role_assignments = person_role_assignments[person_id]
            # With the default P0 declarations all simultaneous role pairs are
            # disallowed, so contribution is simply duration per assignment.
            # If the blueprint explicitly permits sharing, count unique
            # occupied slots instead of charging the same person twice for one
            # simultaneous presence.
            has_shareable_pair = any(
                left_role.allow_shared_person or right_role.allow_shared_person
                for index, (left_role, _) in enumerate(role_assignments)
                for right_role, _ in role_assignments[index + 1 :]
            )
            if not has_shareable_pair:
                model.Add(
                    sum(initiative.duration_slots * assignment for assignment in assignments)
                    <= person.max_contribution_slots
                )
                continue

            possible_slots = tuple(
                slot
                for slot in ORDERED_TIME_SLOTS
                if any(slot in occupied for occupied in occupied_slots_by_start.values())
            )
            presence: list[cp_model.IntVar] = []
            for slot in possible_slots:
                variable = model.NewBoolVar(f"presence__{person_id}__{slot.value}")
                contribution_presence_vars[(person_id, slot)] = variable
                presence.append(variable)
                starts_covering_slot = [
                    start_var
                    for start, start_var in start_vars.items()
                    if slot in occupied_slots_by_start[start]
                ]
                for assignment in assignments:
                    for start_var in starts_covering_slot:
                        model.Add(assignment + start_var - variable <= 1)
                model.Add(variable <= sum(assignments))
                model.Add(variable <= sum(starts_covering_slot))
            model.Add(sum(presence) <= person.max_contribution_slots)

    # Every resource requirement is a hard fact of the bounded model.  A
    # missing resource is represented as an impossible constraint so malformed
    # or deliberately mutated communities produce INFEASIBLE, not a Python
    # shortcut or a fabricated result.  Relaxing resource_quantity skips only
    # quantity sufficiency; availability remains enforced unless the caller
    # explicitly relaxes AVAILABILITY as well.
    resources_by_id = {resource.id: resource for resource in community.resources}
    for requirement in initiative.resources:
        resource = resources_by_id.get(requirement.resource_id)
        if resource is None:
            # Reference integrity is not a relaxable requirement group.  A
            # missing resource must remain impossible even when both of the
            # resource's ordinary quantity and availability requirements are
            # intentionally omitted for a bounded diagnostic solve.
            _add_false(model)
            continue
        if RESOURCE_QUANTITY not in groups and resource.quantity < requirement.quantity:
            _add_false(model)
        if AVAILABILITY not in groups:
            for start, occupied in occupied_slots_by_start.items():
                if not set(occupied) <= resource.available_slots:
                    model.Add(start_vars[start] == 0)

    # ``used`` variables encode the distinct-person part of the transparent
    # burden objective.  MaxEquality is an exact OR over role assignments.
    used_person_vars: dict[str, cp_model.IntVar] = {}
    for person_id, assignments in sorted(person_assignments.items()):
        used = model.NewBoolVar(f"used__{person_id}")
        model.AddMaxEquality(used, assignments)
        used_person_vars[person_id] = used

    compiled = CompiledInitiative(
        community=community,
        initiative=initiative,
        model=model,
        assignment_vars=assignment_vars,
        venue_vars=venue_vars,
        start_vars=start_vars,
        used_person_vars=used_person_vars,
        contribution_presence_vars=contribution_presence_vars,
        role_candidates=role_candidates,
        occupied_slots_by_start=occupied_slots_by_start,
        relaxed_groups=groups,
    )
    if objective_mode == "burden":
        # Preference violations are not declared by the frozen P0 schema, so
        # the third objective term is exactly zero. The default remains the
        # accepted planning burden objective.
        model.Minimize(planning_burden_expression(compiled))
    elif objective_mode != "none":
        raise ValueError("objective_mode must be 'burden' or 'none'")
    return compiled


def compile_model(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    **kwargs: object,
) -> CompiledInitiative:
    """Compatibility alias for callers that name the operation generically."""

    return compile_initiative(community, initiative, **kwargs)


def compile_initiatives(
    community: CommunityState,
    initiatives: Sequence[InitiativeBlueprint],
    *,
    relax_groups: Iterable[str] | None = None,
) -> list[CompiledInitiative]:
    """Compile a sequence independently, preserving declaration order."""

    groups = normalise_relax_groups(relax_groups)
    return [
        compile_initiative(community, initiative, relax_groups=groups)
        for initiative in initiatives
    ]


def compile_community(
    community: CommunityState,
    initiatives: Sequence[InitiativeBlueprint],
    *,
    relax_groups: Iterable[str] | None = None,
) -> list[CompiledInitiative]:
    """Alias used by the analysis orchestration layer."""

    return compile_initiatives(community, initiatives, relax_groups=relax_groups)
