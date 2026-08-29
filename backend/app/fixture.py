"""Authoritative loader for the deterministic fictional demo fixture."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import DemoFixture


FIXTURE_PATH = Path(__file__).parent / "data" / "demo_fixture.json"


@lru_cache(maxsize=1)
def load_demo_fixture() -> DemoFixture:
    return DemoFixture.model_validate(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def fresh_demo_fixture() -> DemoFixture:
    """Return an independent validated copy so request work cannot mutate the baseline."""

    return load_demo_fixture().model_copy(deep=True)

