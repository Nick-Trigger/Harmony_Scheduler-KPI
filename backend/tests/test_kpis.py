"'"

from app.domain.solution import Solution
from app.kpis import compute_kpis
from tests.conftest import make_assignment


def test_kpi_tardiness_for_known_schedule(example_a_problem):
    "Hand-built single-product schedule: tardiness math is exact."
    # P-100 is due 12:30. We finish it at 13:00 -> 30 min tardy.
    solution = Solution(
        assignments=(
            make_assignment(
                "P-100",
                1,
                "fill",
                "Fill-2",
                "2025-11-03T12:00:00",
                "2025-11-03T12:30:00",
            ),
            make_assignment(
                "P-100",
                2,
                "label",
                "Label-1",
                "2025-11-03T12:30:00",
                "2025-11-03T12:50:00",
            ),
            make_assignment(
                "P-100",
                3,
                "pack",
                "Pack-1",
                "2025-11-03T12:50:00",
                "2025-11-03T13:05:00",
            ),
        )
    )

    kpis = compute_kpis(example_a_problem, solution)
    # P-100 due 12:30, ends 13:05 -> 35 min tardy.
    # Other products have no assignments here, so they contribute 0.
    assert kpis["tardiness_minutes"] == 35


def test_kpi_changeover_counts_only_family_transitions(example_a_problem):
    "Same-family back-to-back ops contribute zero changeovers."
    # Two standard products consecutively on Fill-2 -> 0 changeovers.
    solution = Solution(
        assignments=(
            make_assignment(
                "P-100",
                1,
                "fill",
                "Fill-2",  # standard
                "2025-11-03T08:00:00",
                "2025-11-03T08:30:00",
            ),
            make_assignment(
                "P-102",
                1,
                "fill",
                "Fill-2",  # standard
                "2025-11-03T08:30:00",
                "2025-11-03T08:55:00",
            ),
        )
    )
    kpis = compute_kpis(example_a_problem, solution)
    assert kpis["changeover_count"] == 0
    assert kpis["changeover_minutes"] == 0


def test_kpi_makespan_is_span_of_assignments():
    """Makespan = latest end - earliest start (in minutes)."""
    from app.domain.problem import (
        ChangeoverMatrix,
        Horizon,
        Operation,
        Product,
        Resource,
        SchedulingProblem,
        SolverSettings,
        WorkingWindow,
    )
    from datetime import datetime

    # Minimal one-product problem (just enough for compute_kpis).
    problem = SchedulingProblem(
        horizon=Horizon(start=datetime(2025, 1, 1, 8), end=datetime(2025, 1, 1, 16)),
        resources=(
            Resource(
                id="R1",
                capabilities=frozenset({"x"}),
                working_windows=(
                    WorkingWindow(
                        start=datetime(2025, 1, 1, 8), end=datetime(2025, 1, 1, 16)
                    ),
                ),
            ),
        ),
        products=(
            Product(
                id="P1",
                family="f",
                due=datetime(2025, 1, 1, 16),
                route=(Operation(capability="x", duration_minutes=60),),
            ),
        ),
        changeover_matrix=ChangeoverMatrix(values={}),
        settings=SolverSettings(time_limit_seconds=1, objective_mode="min_tardiness"),
    )
    solution = Solution(
        assignments=(
            make_assignment(
                "P1", 1, "x", "R1", "2025-01-01T09:00:00", "2025-01-01T10:00:00"
            ),
        )
    )
    kpis = compute_kpis(problem, solution)
    assert kpis["makespan_minutes"] == 60
