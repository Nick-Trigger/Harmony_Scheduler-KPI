"""Solution validator.

Walks every registered constraint's `validate` method against the final
Solution.
"""

from app.constraints.base import InvariantError, all_constraints
from app.domain.problem import SchedulingProblem
from app.domain.solution import Solution

# Re-export so callers that import InvariantError from here still work.
__all__ = ["InvariantError", "validate"]


def validate(problem: SchedulingProblem, solution: Solution) -> None:
    """Run all registered constraint validators against the solution."""
    for constraint in all_constraints():
        constraint.validate(solution, problem)