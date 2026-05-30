import pytest

from app.domain.solution import Solution
from app.validation import InvariantError, validate
from tests.conftest import make_assignment


def test_validation_catches_resource_overlap(example_a_problem):
    "Hand-crafted overlap on the same resource is rejected."
    bad = Solution(assignments=(
        make_assignment("P-100", 1, "fill", "Fill-2",
                        "2025-11-03T08:00:00", "2025-11-03T08:30:00"),
        make_assignment("P-101", 1, "fill", "Fill-2",
                        "2025-11-03T08:15:00", "2025-11-03T08:50:00"),
    ))
    with pytest.raises(InvariantError, match="overlap"):
        validate(example_a_problem, bad)


def test_validation_catches_precedence_violation(example_a_problem):
    "Step 2 starting before step 1 ends is rejected."
    bad = Solution(assignments=(
        make_assignment("P-100", 1, "fill", "Fill-2",
                        "2025-11-03T08:00:00", "2025-11-03T08:30:00"),
        make_assignment("P-100", 2, "label", "Label-1",
                        "2025-11-03T08:20:00", "2025-11-03T08:40:00"),  # starts before fill ends
    ))
    with pytest.raises(InvariantError, match="precedence"):
        validate(example_a_problem, bad)


def test_validation_passes_on_legitimate_schedule(example_a_problem):
    "Sanity check: real solver output should validate clean."
    from app.solvers.cpsat import solve

    solution = solve(example_a_problem)
    validate(example_a_problem, solution)  # should not raise