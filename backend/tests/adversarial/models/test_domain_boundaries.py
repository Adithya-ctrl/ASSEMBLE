"""Deterministic boundary matrices for the frozen domain models.

These cases exercise the model boundary itself. They intentionally do not
call the solver: a malformed domain must be rejected before expensive
reasoning can begin.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.fixture import fresh_demo_fixture
from app.models import (
    ActionPreconditions,
    AddCapabilityEffect,
    AddPersonEffect,
    AddResourceQuantityEffect,
    CatalystAction,
    CommunityState,
    DemoFixture,
    InitiativeBlueprint,
    OrganisationBlock,
    PersonBlock,
    PersonCapabilityPrecondition,
    ResourceBlock,
    ResourceRequirement,
    RoleRequirement,
    SpaceBlock,
    TimeSlot,
    VenueRequirement,
    WillingLearnerPrecondition,
    occupied_slots,
)


def _person_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "PERSON",
        "name": "Person",
        "organisation_id": "ORG",
        "capabilities": [],
        "languages": [],
        "willing_to_learn": [],
        "available_slots": ["SAT_10"],
        "max_contribution_slots": 1,
    }
    payload.update(overrides)
    return payload


def _space_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "SPACE",
        "name": "Space",
        "organisation_id": "ORG",
        "available_slots": ["SAT_10"],
        "capacity": 1,
        "features": [],
    }
    payload.update(overrides)
    return payload


def _resource_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "RESOURCE",
        "name": "Resource",
        "organisation_id": "ORG",
        "quantity": 1,
        "available_slots": ["SAT_10"],
        "shareable": True,
    }
    payload.update(overrides)
    return payload


def _role_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "ROLE",
        "label": "Role",
        "required_capabilities": [],
        "required_languages": [],
        "allow_shared_person": False,
    }
    payload.update(overrides)
    return payload


def _initiative_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "INITIATIVE",
        "name": "Initiative",
        "roles": [_role_payload()],
        "venue": {"minimum_capacity": 0, "required_features": []},
        "resources": [],
        "candidate_start_slots": ["SAT_10"],
        "duration_slots": 1,
    }
    payload.update(overrides)
    return payload


def _action_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "ACTION",
        "name": "Action",
        "cost": 0,
        "preconditions": {},
        "effects": [
            {
                "type": "add_capability",
                "person_id": "PERSON",
                "capability_id": "digital_support",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _community_payload() -> dict[str, object]:
    return fresh_demo_fixture().community.model_dump(mode="json")


def _fixture_payload() -> dict[str, object]:
    return fresh_demo_fixture().model_dump(mode="json")


def _model_for_stable_id(model_name: str, value: object) -> object:
    if model_name == "organisation":
        return OrganisationBlock.model_validate({"id": value, "name": "Organisation"})
    if model_name == "person":
        return PersonBlock.model_validate(_person_payload(id=value))
    if model_name == "space":
        return SpaceBlock.model_validate(_space_payload(id=value))
    if model_name == "resource":
        return ResourceBlock.model_validate(_resource_payload(id=value))
    if model_name == "role":
        return RoleRequirement.model_validate(_role_payload(id=value))
    if model_name == "initiative":
        return InitiativeBlueprint.model_validate(_initiative_payload(id=value))
    if model_name == "action":
        return CatalystAction.model_validate(_action_payload(id=value))
    if model_name == "state":
        return CommunityState.model_validate({"state_id": value})
    raise AssertionError(f"unknown stable-ID case {model_name}")


STABLE_ID_MODELS = (
    "organisation",
    "person",
    "space",
    "resource",
    "role",
    "initiative",
    "action",
    "state",
)

VALID_STABLE_IDS = ("A", "ABC", "A_1")
INVALID_STABLE_IDS = (
    "abc",
    "1ABC",
    "_ABC",
    "A-B",
    "A B",
    "A/../B",
    "AÉ",
    "😀",
    "A\nB",
    "",
    None,
    1,
    True,
)


@pytest.mark.parametrize("model_name", STABLE_ID_MODELS, ids=lambda value: f"{value}-id")
@pytest.mark.parametrize("value", VALID_STABLE_IDS, ids=lambda value: f"valid-{value}")
def test_stable_id_matrix_accepts_declared_alphabet(model_name: str, value: str) -> None:
    _model_for_stable_id(model_name, value)


@pytest.mark.parametrize("model_name", STABLE_ID_MODELS, ids=lambda value: f"{value}-id")
@pytest.mark.parametrize("value", INVALID_STABLE_IDS, ids=lambda value: f"invalid-{value!r}")
def test_stable_id_matrix_rejects_malformed_values(model_name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _model_for_stable_id(model_name, value)


def test_stable_id_extreme_length_is_rejected_at_the_model_boundary() -> None:
    with pytest.raises(ValidationError):
        _model_for_stable_id("organisation", "A" + "B" * 4096)


@pytest.mark.parametrize("collection", ("organisations", "people", "spaces", "resources"))
def test_community_rejects_duplicate_block_ids(collection: str) -> None:
    payload = _community_payload()
    payload[collection].append(deepcopy(payload[collection][0]))  # type: ignore[index]
    with pytest.raises(ValidationError, match="duplicate"):
        CommunityState.model_validate(payload)


def test_initiative_rejects_duplicate_role_ids() -> None:
    payload = _initiative_payload()
    payload["roles"].append(deepcopy(payload["roles"][0]))  # type: ignore[index]
    with pytest.raises(ValidationError, match="duplicate"):
        InitiativeBlueprint.model_validate(payload)


@pytest.mark.parametrize("collection", ("initiatives", "actions"))
def test_fixture_rejects_duplicate_top_level_ids(collection: str) -> None:
    payload = _fixture_payload()
    payload[collection].append(deepcopy(payload[collection][0]))  # type: ignore[index]
    with pytest.raises(ValidationError, match="duplicate"):
        DemoFixture.model_validate(payload)


CAPABILITY_MODELS = (
    "person_capabilities",
    "person_willing_to_learn",
    "space_features",
    "role_required_capabilities",
    "venue_required_features",
    "action_capability_effect",
    "person_capability_precondition",
    "learner_capability_precondition",
)

VALID_CAPABILITIES = ("a", "digital_support", "digital2")
INVALID_CAPABILITIES = (
    "Digital_support",
    "1digital",
    "_digital",
    "digital-support",
    "digital support",
    "DIGITAL_SUPPORT",
    "aÉ",
    "😀",
    "",
    None,
    True,
)


def _model_for_capability(model_name: str, value: object) -> object:
    if model_name == "person_capabilities":
        return PersonBlock.model_validate(_person_payload(capabilities=[value]))
    if model_name == "person_willing_to_learn":
        return PersonBlock.model_validate(_person_payload(willing_to_learn=[value]))
    if model_name == "space_features":
        return SpaceBlock.model_validate(_space_payload(features=[value]))
    if model_name == "role_required_capabilities":
        return RoleRequirement.model_validate(_role_payload(required_capabilities=[value]))
    if model_name == "venue_required_features":
        return VenueRequirement.model_validate(
            {"minimum_capacity": 0, "required_features": [value]}
        )
    if model_name == "action_capability_effect":
        return AddCapabilityEffect.model_validate(
            {"type": "add_capability", "person_id": "PERSON", "capability_id": value}
        )
    if model_name == "person_capability_precondition":
        return PersonCapabilityPrecondition.model_validate(
            {"person_id": "PERSON", "capability_id": value}
        )
    if model_name == "learner_capability_precondition":
        return WillingLearnerPrecondition.model_validate(
            {"person_id": "PERSON", "capability_id": value}
        )
    raise AssertionError(f"unknown capability case {model_name}")


@pytest.mark.parametrize("model_name", CAPABILITY_MODELS, ids=lambda value: value)
@pytest.mark.parametrize("value", VALID_CAPABILITIES, ids=lambda value: f"valid-{value}")
def test_capability_id_matrix_accepts_declared_lowercase_values(model_name: str, value: str) -> None:
    _model_for_capability(model_name, value)


@pytest.mark.parametrize("model_name", CAPABILITY_MODELS, ids=lambda value: value)
@pytest.mark.parametrize("value", INVALID_CAPABILITIES, ids=lambda value: f"invalid-{value!r}")
def test_capability_id_matrix_rejects_malformed_values(model_name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _model_for_capability(model_name, value)


def test_display_text_does_not_declare_a_capability() -> None:
    person = PersonBlock.model_validate(
        _person_payload(name="digital_support", capabilities=[])
    )
    assert person.capabilities == set()


def test_duplicate_capability_entries_have_explicit_set_semantics() -> None:
    person = PersonBlock.model_validate(
        _person_payload(capabilities=["digital_support", "digital_support"])
    )
    assert person.capabilities == {"digital_support"}


LANGUAGE_MODELS = ("person_languages", "role_required_languages")
VALID_LANGUAGES = ("en", "ar")
INVALID_LANGUAGES = (
    "EN",
    "e",
    "eng",
    "1a",
    " en",
    "a ",
    "aÉ",
    "😀",
    "",
    None,
    True,
)


def _model_for_language(model_name: str, value: object) -> object:
    if model_name == "person_languages":
        return PersonBlock.model_validate(_person_payload(languages=[value]))
    if model_name == "role_required_languages":
        return RoleRequirement.model_validate(_role_payload(required_languages=[value]))
    raise AssertionError(f"unknown language case {model_name}")


@pytest.mark.parametrize("model_name", LANGUAGE_MODELS, ids=lambda value: value)
@pytest.mark.parametrize("value", VALID_LANGUAGES, ids=lambda value: f"valid-{value}")
def test_language_code_matrix_is_exactly_two_lowercase_letters(
    model_name: str, value: str
) -> None:
    _model_for_language(model_name, value)


@pytest.mark.parametrize("model_name", LANGUAGE_MODELS, ids=lambda value: value)
@pytest.mark.parametrize("value", INVALID_LANGUAGES, ids=lambda value: f"invalid-{value!r}")
def test_language_code_matrix_rejects_unmatched_values(model_name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _model_for_language(model_name, value)


def test_duplicate_language_entries_have_explicit_set_semantics() -> None:
    person = PersonBlock.model_validate(_person_payload(languages=["en", "en"]))
    assert person.languages == {"en"}


@pytest.mark.parametrize(
    ("field", "model_factory"),
    [
        (
            "max_contribution_slots",
            lambda value: PersonBlock.model_validate(
                _person_payload(
                    available_slots=["SAT_10", "SAT_11", "SAT_12", "SAT_13"],
                    max_contribution_slots=value,
                )
            ),
        ),
        ("capacity", lambda value: SpaceBlock.model_validate(_space_payload(capacity=value))),
        ("quantity", lambda value: ResourceBlock.model_validate(_resource_payload(quantity=value))),
        (
            "minimum_capacity",
            lambda value: VenueRequirement.model_validate(
                {"minimum_capacity": value, "required_features": []}
            ),
        ),
        (
            "resource_quantity",
            lambda value: ResourceRequirement.model_validate(
                {"resource_id": "RESOURCE", "quantity": value}
            ),
        ),
        (
            "effect_quantity",
            lambda value: AddResourceQuantityEffect.model_validate(
                {"type": "add_resource_quantity", "resource_id": "RESOURCE", "quantity": value}
            ),
        ),
        ("action_cost", lambda value: CatalystAction.model_validate(_action_payload(cost=value))),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
@pytest.mark.parametrize("value", (1.0, "1", True), ids=lambda value: f"wrong-{value!r}")
def test_bounded_integer_fields_reject_numeric_coercion(
    field: str, model_factory, value: object
) -> None:
    del field
    with pytest.raises(ValidationError):
        model_factory(value)


@pytest.mark.parametrize(
    ("model_factory", "bad_value"),
    [
        (
            lambda value: PersonBlock.model_validate(
                _person_payload(max_contribution_slots=value)
            ),
            0,
        ),
        (
            lambda value: PersonBlock.model_validate(
                _person_payload(max_contribution_slots=value)
            ),
            -1,
        ),
        (
            lambda value: PersonBlock.model_validate(
                _person_payload(
                    available_slots=["SAT_10", "SAT_11"],
                    max_contribution_slots=value,
                )
            ),
            3,
        ),
        (lambda value: SpaceBlock.model_validate(_space_payload(capacity=value)), -1),
        (lambda value: ResourceBlock.model_validate(_resource_payload(quantity=value)), -1),
        (
            lambda value: ResourceRequirement.model_validate(
                {"resource_id": "RESOURCE", "quantity": value}
            ),
            0,
        ),
        (
            lambda value: ResourceRequirement.model_validate(
                {"resource_id": "RESOURCE", "quantity": value}
            ),
            -1,
        ),
        (
            lambda value: AddResourceQuantityEffect.model_validate(
                {"type": "add_resource_quantity", "resource_id": "RESOURCE", "quantity": value}
            ),
            0,
        ),
        (lambda value: CatalystAction.model_validate(_action_payload(cost=value)), -1),
        (
            lambda value: VenueRequirement.model_validate(
                {"minimum_capacity": value, "required_features": []}
            ),
            -1,
        ),
    ],
    ids=lambda value: repr(value) if isinstance(value, int) else None,
)
def test_numeric_domain_minimums_and_cross_field_bounds_reject_invalid_values(
    model_factory, bad_value: int
) -> None:
    with pytest.raises(ValidationError):
        model_factory(bad_value)


def test_person_contribution_boundary_accepts_exact_availability_and_rejects_one_above() -> None:
    exact = PersonBlock.model_validate(
        _person_payload(
            available_slots=[slot.value for slot in TimeSlot],
            max_contribution_slots=len(TimeSlot),
        )
    )
    assert exact.max_contribution_slots == len(TimeSlot)
    with pytest.raises(ValidationError, match="exceeds"):
        PersonBlock.model_validate(
            _person_payload(
                available_slots=[slot.value for slot in TimeSlot],
                max_contribution_slots=len(TimeSlot) + 1,
            )
        )


@pytest.mark.parametrize(
    "value", (0, 1, "true", "false"), ids=lambda value: f"wrong-shareable-{value!r}"
)
def test_resource_shareability_rejects_non_boolean_primitives(value: object) -> None:
    with pytest.raises(ValidationError):
        ResourceBlock.model_validate(_resource_payload(shareable=value))


@pytest.mark.parametrize(
    ("candidate_start_slots", "duration_slots"),
    [
        (["SAT_10"], 1),
        (["SAT_10"], len(TimeSlot)),
        (["SAT_13"], 1),
        ([slot.value for slot in TimeSlot], 1),
    ],
    ids=("first-slot", "full-horizon", "last-slot", "all-starts"),
)
def test_time_matrix_accepts_declared_starts_that_fit_the_horizon(
    candidate_start_slots: list[str], duration_slots: int
) -> None:
    InitiativeBlueprint.model_validate(
        _initiative_payload(
            candidate_start_slots=candidate_start_slots,
            duration_slots=duration_slots,
        )
    )


@pytest.mark.parametrize(
    ("candidate_start_slots", "duration_slots", "message"),
    [
        (["SAT_99"], 1, "enum"),
        (["SAT_10", "SAT_10"], 1, "duplicate"),
        (["SAT_13"], 2, "time horizon"),
        (["SAT_10"], 0, "greater than or equal"),
        (["SAT_10"], len(TimeSlot) + 1, "less than or equal"),
        ([], 1, "at least 1 item"),
    ],
    ids=(
        "unknown-slot",
        "duplicate-start",
        "overflow-by-one",
        "zero-duration",
        "duration-over-horizon",
        "zero-starts",
    ),
)
def test_time_matrix_rejects_unknown_duplicate_or_out_of_range_values(
    candidate_start_slots: list[str], duration_slots: int, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        InitiativeBlueprint.model_validate(
            _initiative_payload(
                candidate_start_slots=candidate_start_slots,
                duration_slots=duration_slots,
            )
        )


@pytest.mark.parametrize("value", ("2", 2.0, True), ids=lambda value: f"wrong-duration-{value!r}")
def test_duration_rejects_numeric_coercion(value: object) -> None:
    with pytest.raises(ValidationError):
        InitiativeBlueprint.model_validate(_initiative_payload(duration_slots=value))


def test_occupied_slots_is_contiguous_and_does_not_truncate_overflow() -> None:
    assert occupied_slots(TimeSlot.SAT_11, 2) == (TimeSlot.SAT_11, TimeSlot.SAT_12)
    with pytest.raises(ValueError, match="horizon"):
        occupied_slots(TimeSlot.SAT_13, 2)


@pytest.mark.parametrize(
    ("field", "model_factory", "limit", "values"),
    [
        (
            "person capabilities",
            lambda values: PersonBlock.model_validate(_person_payload(capabilities=values)),
            32,
            [f"cap_{index:02d}" for index in range(33)],
        ),
        (
            "person willingness",
            lambda values: PersonBlock.model_validate(_person_payload(willing_to_learn=values)),
            32,
            [f"learn_{index:02d}" for index in range(33)],
        ),
        (
            "person languages",
            lambda values: PersonBlock.model_validate(_person_payload(languages=values)),
            16,
            [f"a{chr(97 + index)}" for index in range(17)],
        ),
        (
            "person availability",
            lambda values: PersonBlock.model_validate(
                _person_payload(available_slots=values, max_contribution_slots=1)
            ),
            4,
            [slot.value for slot in TimeSlot] + ["SAT_14"],
        ),
        (
            "space features",
            lambda values: SpaceBlock.model_validate(_space_payload(features=values)),
            32,
            [f"feature_{index:02d}" for index in range(33)],
        ),
        (
            "space availability",
            lambda values: SpaceBlock.model_validate(_space_payload(available_slots=values)),
            4,
            [slot.value for slot in TimeSlot] + ["SAT_14"],
        ),
        (
            "role capabilities",
            lambda values: RoleRequirement.model_validate(
                _role_payload(required_capabilities=values)
            ),
            32,
            [f"role_cap_{index:02d}" for index in range(33)],
        ),
        (
            "role languages",
            lambda values: RoleRequirement.model_validate(_role_payload(required_languages=values)),
            16,
            [f"b{chr(97 + index)}" for index in range(17)],
        ),
        (
            "initiative roles",
            lambda values: InitiativeBlueprint.model_validate(_initiative_payload(roles=values)),
            32,
            [_role_payload(id=f"ROLE_{index:02d}") for index in range(33)],
        ),
        (
            "initiative resources",
            lambda values: InitiativeBlueprint.model_validate(_initiative_payload(resources=values)),
            64,
            [
                {"resource_id": f"RESOURCE_{index:02d}", "quantity": 1}
                for index in range(65)
            ],
        ),
        (
            "initiative candidate starts",
            lambda values: InitiativeBlueprint.model_validate(
                _initiative_payload(candidate_start_slots=values, duration_slots=1)
            ),
            4,
            [slot.value for slot in TimeSlot] + ["SAT_14"],
        ),
        (
            "person preconditions",
            lambda values: ActionPreconditions.model_validate({"person_capabilities": values}),
            64,
            [
                {"person_id": f"PERSON_{index:02d}", "capability_id": "support"}
                for index in range(65)
            ],
        ),
        (
            "learner preconditions",
            lambda values: ActionPreconditions.model_validate({"willing_learners": values}),
            64,
            [
                {"person_id": f"PERSON_{index:02d}", "capability_id": "support"}
                for index in range(65)
            ],
        ),
        (
            "space preconditions",
            lambda values: ActionPreconditions.model_validate({"space_availability": values}),
            64,
            [
                {"space_id": f"SPACE_{index:02d}", "slots": ["SAT_10"]}
                for index in range(65)
            ],
        ),
        (
            "action effects",
            lambda values: CatalystAction.model_validate(_action_payload(effects=values)),
            64,
            [
                {
                    "type": "add_capability",
                    "person_id": "PERSON",
                    "capability_id": f"cap_{index:02d}",
                }
                for index in range(65)
            ],
        ),
    ],
    ids=(
        "person-capabilities",
        "person-willingness",
        "person-languages",
        "person-availability",
        "space-features",
        "space-availability",
        "role-capabilities",
        "role-languages",
        "initiative-roles",
        "initiative-resources",
        "initiative-starts",
        "person-preconditions",
        "learner-preconditions",
        "space-preconditions",
        "action-effects",
    ),
)
def test_nested_collection_ceiling_matrix(
    field: str, model_factory, limit: int, values: list[object]
) -> None:
    del field
    # The same deterministic fixture is checked just below, at max - 1, max,
    # and max + 1. The over-limit case must fail before any domain reasoning.
    with pytest.raises(ValidationError):
        model_factory(values[: limit + 1])
    model_factory(values[:limit])
    if limit > 1:
        model_factory(values[: limit - 1])


@pytest.mark.parametrize("collection", ("organisations", "people", "spaces", "resources"))
@pytest.mark.parametrize("size_kind", ("max_minus_one", "max", "max_plus_one"))
def test_community_collection_ceiling_matrix(collection: str, size_kind: str) -> None:
    limits = {"organisations": 32, "people": 128, "spaces": 32, "resources": 64}
    limit = limits[collection]
    size = {"max_minus_one": limit - 1, "max": limit, "max_plus_one": limit + 1}[size_kind]
    payload = _community_payload()
    template = deepcopy(payload[collection][0])  # type: ignore[index]
    original = deepcopy(payload[collection])  # type: ignore[index]
    payload[collection] = original if collection == "organisations" else []
    start_index = len(payload[collection])  # type: ignore[arg-type]
    for index in range(start_index, size):
        item = deepcopy(template)
        item["id"] = f"{collection.upper()}_{index:03d}"
        payload[collection].append(item)  # type: ignore[union-attr]
    if size_kind == "max_plus_one":
        with pytest.raises(ValidationError):
            CommunityState.model_validate(payload)
    else:
        CommunityState.model_validate(payload)


@pytest.mark.parametrize("collection", ("initiatives", "actions"))
@pytest.mark.parametrize("size_kind", ("max_minus_one", "max", "max_plus_one"))
def test_fixture_top_level_collection_ceiling_matrix(collection: str, size_kind: str) -> None:
    limit = 32
    size = {"max_minus_one": limit - 1, "max": limit, "max_plus_one": limit + 1}[size_kind]
    payload = _fixture_payload()
    template = deepcopy(payload[collection][0])  # type: ignore[index]
    payload[collection] = []
    for index in range(size):
        item = deepcopy(template)
        item["id"] = f"{collection.upper()}_{index:03d}"
        payload[collection].append(item)  # type: ignore[union-attr]
    if size_kind == "max_plus_one":
        with pytest.raises(ValidationError):
            DemoFixture.model_validate(payload)
    else:
        DemoFixture.model_validate(payload)


def test_all_action_effect_variants_are_discriminated_without_text_inference() -> None:
    person_effect = AddPersonEffect.model_validate(
        {
            "type": "add_person",
            "person": _person_payload(id="NEW_PERSON", name="New person"),
        }
    )
    resource_effect = AddResourceQuantityEffect.model_validate(
        {"type": "add_resource_quantity", "resource_id": "RESOURCE", "quantity": 1}
    )
    capability_effect = AddCapabilityEffect.model_validate(
        {"type": "add_capability", "person_id": "PERSON", "capability_id": "support"}
    )
    assert person_effect.person.id == "NEW_PERSON"
    assert resource_effect.quantity == 1
    assert capability_effect.capability_id == "support"
    with pytest.raises(ValidationError):
        CatalystAction.model_validate(
            _action_payload(
                effects=[
                    {
                        "type": "add_capability",
                        "person_id": "PERSON",
                        "capability_id": "Support",
                    }
                ]
            )
        )


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (OrganisationBlock, {"id": "ORG", "name": "Organisation"}),
        (PersonBlock, _person_payload()),
        (SpaceBlock, _space_payload()),
        (ResourceBlock, _resource_payload()),
        (RoleRequirement, _role_payload()),
        (InitiativeBlueprint, _initiative_payload()),
        (ActionPreconditions, {}),
        (CatalystAction, _action_payload()),
        (CommunityState, {"state_id": "S0"}),
    ],
    ids=(
        "organisation",
        "person",
        "space",
        "resource",
        "role",
        "initiative",
        "preconditions",
        "action",
        "community",
    ),
)
def test_domain_models_forbid_unknown_fields(model_type, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate({**payload, "unknown_field": "reject-me"})


def test_nested_unknown_fields_are_rejected_before_reference_checks() -> None:
    payload = _community_payload()
    payload["people"][0]["unknown_field"] = "reject-me"  # type: ignore[index]
    with pytest.raises(ValidationError, match="extra"):
        CommunityState.model_validate(payload)


@pytest.mark.parametrize(
    ("capabilities", "languages", "allow_shared_person"),
    [
        ([], [], False),
        (["support"], [], False),
        ([], ["en"], False),
        (["support"], ["en"], False),
        (["support", "facilitation"], ["ar", "en"], True),
    ],
    ids=("empty", "capability-only", "language-only", "both", "multi-shared"),
)
def test_role_combination_matrix_preserves_declared_requirements(
    capabilities: list[str], languages: list[str], allow_shared_person: bool
) -> None:
    role = RoleRequirement.model_validate(
        _role_payload(
            required_capabilities=capabilities,
            required_languages=languages,
            allow_shared_person=allow_shared_person,
        )
    )
    assert role.required_capabilities == set(capabilities)
    assert role.required_languages == set(languages)
    assert role.allow_shared_person is allow_shared_person


@pytest.mark.parametrize("value", (0, 1, "true", None), ids=lambda value: f"share-{value!r}")
def test_role_sharing_flag_rejects_non_boolean_primitives(value: object) -> None:
    with pytest.raises(ValidationError):
        RoleRequirement.model_validate(_role_payload(allow_shared_person=value))
