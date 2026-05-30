"""confitest.py

Creates test fixtures for the scheduling problem.
"""

import json
from pathlib import Path

import pytest

from app.adapters.client_a import parse_request
from app.domain.problem import SchedulingProblem
from app.domain.solution import Assignment, Solution
from datetime import datetime


DATA = Path(__file__).parent / "example_data"


@pytest.fixture
def example_a_payload() -> dict:
    "The spec's full Client A example as a raw dict."
    with (DATA / "example_a.json").open() as f:
        return json.load(f)


@pytest.fixture
def example_a_problem(example_a_payload) -> SchedulingProblem:
    "The spec's full example, parsed into the canonical domain model."
    return parse_request(example_a_payload)


def make_assignment(
    product_id: str,
    step_index: int,
    capability: str,
    resource_id: str,
    start: str,
    end: str,
) -> Assignment:
    "Test helper for hand-building Assignments from ISO strings."
    return Assignment(
        product_id=product_id,
        step_index=step_index,
        capability=capability,
        resource_id=resource_id,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
    )