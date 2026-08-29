from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.fixture import fresh_demo_fixture, load_demo_fixture
from app.models import PersonBlock, ResourceBlock, TimeSlot, occupied_slots


def test_frozen_fixture_shape_and_references() -> None:
    fixture = load_demo_fixture()
    assert fixture.fixture_version == "assemble-demo-v1"
    assert len(fixture.community.organisations) == 4
    assert len(fixture.community.people) == 5
    assert len(fixture.community.spaces) == 1
    assert len(fixture.community.resources) == 2
    assert {item.id for item in fixture.initiatives} == {
        "BASIC_WORKSHOP", "MULTILINGUAL_CLINIC", "REPAIR_SHARE"
    }
    assert {item.id for item in fixture.actions} == {
        "TRAIN_DIGITAL_HELPERS", "RECRUIT_HELPER_A",
        "RECRUIT_HELPER_B", "BORROW_TWO_LAPTOPS",
    }


def test_fixture_loader_returns_independent_copy() -> None:
    first = fresh_demo_fixture()
    second = fresh_demo_fixture()
    first.community.people[0].capabilities.add("temporary_test_capability")
    assert "temporary_test_capability" not in second.community.people[0].capabilities


def test_mutable_defaults_do_not_leak() -> None:
    fields = {
        "organisation_id": "ORG",
        "available_slots": {TimeSlot.SAT_10},
        "max_contribution_slots": 1,
    }
    one = PersonBlock(id="ONE", name="One", **fields)
    two = PersonBlock(id="TWO", name="Two", **fields)
    one.capabilities.add("digital_support")
    assert two.capabilities == set()


def test_negative_quantity_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ResourceBlock(
            id="BAD_RESOURCE",
            name="Bad resource",
            organisation_id="ORG",
            quantity=-1,
            available_slots={TimeSlot.SAT_10},
            shareable=True,
        )


def test_invalid_slot_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonBlock(
            id="BAD",
            name="Bad",
            organisation_id="ORG",
            available_slots={"SAT_99"},
            max_contribution_slots=1,
        )


def test_unresolved_fixture_reference_is_rejected() -> None:
    payload = deepcopy(load_demo_fixture().model_dump(mode="json"))
    payload["community"]["people"][0]["organisation_id"] = "MISSING_ORG"
    with pytest.raises(ValidationError, match="missing id MISSING_ORG"):
        type(load_demo_fixture()).model_validate(payload)


def test_declared_time_is_contiguous() -> None:
    assert occupied_slots(TimeSlot.SAT_11, 2) == (TimeSlot.SAT_11, TimeSlot.SAT_12)
    with pytest.raises(ValueError, match="time horizon"):
        occupied_slots(TimeSlot.SAT_13, 2)

